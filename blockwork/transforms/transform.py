# Copyright 2023, Blockwork, github.com/intuity/blockwork
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import hashlib
import importlib
import json
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import Field, dataclass, fields
from dataclasses import field as dc_field
from enum import Enum, auto
from functools import reduce
from pathlib import Path
from types import EllipsisType, GenericAlias, NoneType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Literal,
    Self,
    TypedDict,
    TypeVar,
    cast,
    dataclass_transform,
    get_origin,
)

from blockwork.common.singleton import Singleton

from ..build.caching import Cache
from ..config.api import ConfigApi
from ..containers.container import Container
from ..context import Context

if TYPE_CHECKING:
    from ..context import Context
    from ..tools import Invocation, Tool, Version
from ..common.complexnamespaces import ReadonlyNamespace


class Medial:
    """
    Medials represent values passed between transforms.
    """

    val: str
    "Medial value"
    _producers: "list[Transform] | None"
    "The transforms that produce this medial"
    _consumers: "list[Transform] | None"
    "The transfoms that consume this medial (implemented but unused)"
    _cached_input_hash: str | None
    "The (cached) hash of this medials inputs"

    def __init__(self, val: str):
        self.val = val
        self._producers = None
        self._consumers = None
        self._cached_input_hash = None

    def __hash__(self) -> int:
        return hash(self.val)

    def __eq__(self, other: "Medial"):
        return isinstance(other, Medial) and (self.val == other.val)

    def bind_consumers(self, consumers: list["Transform"]):
        """
        Bind a list of transform that consume this medial.

        Note:
            - This deliberately binds a list by reference as it is built
              up
            - Currently unused but could be used for graphing later
        """
        if self._consumers is not None:
            raise RuntimeError("Consumers already bound to medial!")
        self._consumers = consumers

    def bind_producers(self, producers: list["Transform"]):
        """
        Bind the transforms that produce this medial.

        Note:
            - This deliberately binds a list by reference as it is built
              up
        """
        if self._producers is not None:
            raise RuntimeError("Producers already bound to medial!")
        if len(producers) > 1:
            raise RuntimeError(f"Medial `{self}` produced by more than one transform `{producers}`")
        self._producers = producers

    def _input_hash(self) -> str:
        """
        Get a hash of the inputs to this medial.

        This can only be used once all transforms in a graph are initialised.
        """
        if self._cached_input_hash is not None:
            return self._cached_input_hash

        if self._producers:
            self._cached_input_hash = self._producers[0]._input_hash()
        else:
            self._cached_input_hash = Cache.hash_content(Path(self.val))

        return self._cached_input_hash

    def __repr__(self):
        return f"<Medial val='{self.val}' hash={self._cached_input_hash}>"

    def _exists(self):
        "Whether the medial exists ahead of time"
        # Assuming it's a path for now (only valid medial currently)
        return Path(self.val).exists()


class Direction(Enum):
    """
    Used to identify if an interface is acting as an input-to or output-from
    a container
    """

    INPUT = auto()
    OUTPUT = auto()

    # Note these is_* methods may seem pointless but it
    # prevents the need to import round
    @property
    def is_input(self):
        return self is Direction.INPUT

    @property
    def is_output(self):
        return self is Direction.OUTPUT


class EnvPolicy(Enum):
    "Controls behaviour when an env variable is already set"

    APPEND = auto()
    """
    Append to the existing value with '`:`' separator.
    """

    PREPEND = auto()
    """
    Prepend to the existing value with '`:`' separator. Note, when a list
    of values `['a','b','c']` is provided the resultant env string will be
    reversed `c:b:a`.
    """

    REPLACE = auto()
    """
    Replace the existing value with the new one. Note, when a list of values
    is provided, this will result in only the last value being used.
    """

    CONFLICT = auto()
    "The default, raise an error if the variable is already set"


TIPrimitive = TypeVar("TIPrimitive", bound="TISerialAny")
TIType = TypeVar("TIType", bound="TIAny")
TIEnvPolicy = Literal["APPEND", "PREPEND", "REPLACE", "CONFLICT"]


class PrimitiveSerializer(Generic[TIPrimitive, TIType]):
    """
    Primitive serialisers are used to serializer interface values.

    And resolve the serialized value against a container.
    """

    @classmethod
    def serialize(cls, token: TIType) -> TIPrimitive:
        raise NotImplementedError

    @classmethod
    def resolve(
        cls, token: TIPrimitive, ctx: Context, container: Container, direction: Direction
    ) -> TIType:
        raise NotImplementedError

    @classmethod
    def default_factory(
        cls, token: type[TIType], name: str, transform: "Transform", field: "IField"
    ) -> TIType:
        field_str = "IN(...)" if field.direction.is_input else "OUT(...)"
        transform_str = type(transform).__name__
        if type(token) is not GenericAlias or (type_str := get_origin(token)) is None:
            type_str = token.__name__
        raise RuntimeError(
            "Can't automatically set default for field for "
            f"{transform_str}: `{name}: {type_str} = {field_str}`"
        )

    @classmethod
    def walk_medials(cls, token: "TIPrimitive") -> Iterable[Medial]:
        yield from []

    @classmethod
    def walk_hashable(cls, token: "TIPrimitive") -> Iterable[Any]:
        yield token


class InterfaceSerializer(PrimitiveSerializer["TISerialAny", "TIAny"], metaclass=Singleton):
    """
    The top level serializer which knows about all others.
    """

    quick_type_map: ClassVar[dict[type, type[PrimitiveSerializer]]] = {}
    slow_type_map: ClassVar[dict[tuple[type, ...], type[PrimitiveSerializer]]] = {}
    key_map: ClassVar[dict[str, type[PrimitiveSerializer]]] = {}

    @classmethod
    def register(cls, key: str, types: tuple[type, ...]) -> Any:
        def inner(serializer: type[PrimitiveSerializer]) -> type[PrimitiveSerializer]:
            for typ in types:
                cls.quick_type_map[typ] = serializer
            cls.slow_type_map[types] = serializer
            cls.key_map[key] = serializer
            return serializer

        return inner

    @classmethod
    def serialize(cls, token: "TIAny") -> "TISerialAny":
        # Try the quick map
        if (serializer := cls.quick_type_map.get(type(token))) is not None:
            return serializer.serialize(token)

        # Try the slow map
        for types, serializer in cls.slow_type_map.items():
            if isinstance(token, types):
                return serializer.serialize(token)

        raise RuntimeError(f"Invalid interface type: `{token}`")

    @classmethod
    def resolve(
        cls, token: "TISerialAny", ctx: Context, container: Container, direction: Direction
    ) -> "TIAny":
        "Resolve a token against a container, binding values in as required"
        if (serializer := cls.key_map.get(token["typ"])) is not None:
            return serializer.resolve(token, ctx, container, direction)
        raise RuntimeError(f"Invalid interface type: `{token}`")

    @classmethod
    def default_factory(
        cls, token: type["TIAny"], name: str, transform: "Transform", field: "IField"
    ) -> "TIAny":
        # If we have a type like list[str], send it to the serializer for list
        if type(token) is not GenericAlias or (map_token := get_origin(token)) is None:
            map_token = token

        # Try the quick map
        if (serializer := cls.quick_type_map.get(map_token)) is not None:
            return serializer.default_factory(token, name, transform, field)

        # Try the slow map
        for types, serializer in cls.slow_type_map.items():
            if issubclass(map_token, types):
                return serializer.default_factory(token, name, transform, field)

        return super().default_factory(token, name, transform, field)

    @classmethod
    def walk_medials(cls, token: "TISerialAny"):
        "Walk over all tokens"
        if (serializer := cls.key_map.get(token["typ"])) is not None:
            yield from serializer.walk_medials(token)
        else:
            raise RuntimeError(f"Invalid interface type: `{token}`")

    @classmethod
    def walk_hashable(cls, token: "TISerialAny") -> Iterable[Any]:
        "Walk over hashable tokens"
        if (serializer := cls.key_map.get(token["typ"])) is not None:
            yield from serializer.walk_hashable(token)
        else:
            raise RuntimeError(f"Invalid interface type: `{token}`")


class IPath:
    """
    An interface primitive that can be used to bind paths to containers
    when Path does not provide enough control.
    """

    def __init__(self, host: Path | str | None, cont: Path | str | None, is_dir=False):
        """
        :param host: The path to map from on the host
        :param cont: The path to map to on the container
        :param is_dir: Whether or not the path is a directory

        If 'host' is provided and 'cont' is None, the container path will
        be generated automatically.

        If 'cont' is provided and 'host' is None, we expose the container path
        but don't perform any binding (useful if a parent directory is bound).
        """
        if host is None and cont is None:
            raise ValueError("Both host path and container path cannot be None!")
        self.host = None if host is None else Path(host)
        self.cont = None if cont is None else Path(cont)
        self.is_dir = is_dir

    def __repr__(self) -> str:
        return f"<IPath frm='{self.host}' to='{self.cont}'>"


@InterfaceSerializer.register("path", (Path, IPath))
class PathSerializer(PrimitiveSerializer["TIPathSerial", "Path | IPath"]):
    @classmethod
    def serialize(cls, token: "Path | IPath") -> "TIPathSerial":
        "Serialize a path into the interface spec format"

        if isinstance(token, Path):
            host_path, cont_path, is_dir = token, None, False
        else:
            host_path, cont_path, is_dir = token.host, token.cont, token.is_dir

        if host_path is not None:
            if not host_path.is_absolute():
                raise RuntimeError(f"Interface paths must be absolute! Got: `{token}`")
            host_path = host_path.resolve().as_posix()

        if cont_path is not None:
            if not cont_path.is_absolute():
                raise RuntimeError(f"Interface paths must be absolute! Got: `{token}`")
            else:
                cont_path = cont_path.resolve().as_posix()

        return {"typ": "path", "host": host_path, "cont": cont_path, "is_dir": is_dir}

    @classmethod
    def resolve(
        cls, token: "TIPathSerial", ctx: Context, container: Container, direction: Direction
    ):
        "Resolve a path against a container, binding value as required"
        if token["host"] is not None:
            # Resolve symlinks in the host path as we can bind the linked path
            # directly. For inputs this must succeed.
            try:
                host_path = Path(token["host"]).resolve(strict=direction.is_input)
            except (FileNotFoundError, RuntimeError) as e:
                # Note runtime error is raised for looped symlinks
                raise ValueError(
                    f"Could not resolve input host path `{token['host']}` to real path!"
                ) from e
            if token["cont"] is None:
                # Resolve to the container based on the unresolved host path
                cont_path = ctx.map_to_container(Path(token["host"]))
            else:
                cont_path = Path(token["cont"])
            readonly = direction.is_input
            if token["is_dir"]:
                container.bind(host_path, cont_path, readonly=readonly, mkdir=True)
            else:
                container.bind(host_path.parent, cont_path.parent, readonly=readonly, mkdir=True)
        else:
            if token["cont"] is None:
                raise ValueError("Both host path and container path cannot be None!")
            cont_path = Path(token["cont"])
        return cont_path

    @classmethod
    def default_factory(
        cls, token: type["TIAny"], name: str, transform: "Transform", field: "IField"
    ) -> "TIAny":
        if field.direction.is_input:
            super().default_factory(token, name, transform, field)  # type: ignore
        return transform.api.path(name)

    @classmethod
    def walk_medials(cls, token: "TIPathSerial"):
        if token["host"] is not None:
            yield Medial(token["host"])

    @classmethod
    def walk_hashable(cls, token: "TIPathSerial"):
        # Omit the paths themselves as they are likely to be generated
        yield {**token, "host": token["host"] is not None, "cont": token["cont"] is not None}


class IEnv:
    """
    An interface primitive which can be used to expose environment variables.
    """

    def __init__(
        self, key: str, val: "TIEnv", policy: EnvPolicy = EnvPolicy.CONFLICT, _wrap: bool = True
    ):
        """
        :param key: The environment variable name
        :param val: The environment variable value, can be a constant value, \
                    a path, or a list thereof. The exposed value for paths \
                    will be container mapped.
        :param policy: The replacement policy when the variable is already set \
                       or when a list is provided.
        :param _wrap: INTERNAL USE ONLY
        """
        for v in val if isinstance(val, list) else [val]:
            if not isinstance(v, str | int | float | None | Path | IPath):
                raise ValueError(
                    f"Value `{val}` is not valid in IEnv, only str, int"
                    " float, None, Path, IPath, and lists thereof are allowed."
                )
        if not isinstance(policy, EnvPolicy):
            raise ValueError(f"Policy `{policy}` is not valid in IEnv, use the EnvPolicy enum.")
        self.key = key
        self.val = val
        self.policy = policy
        # Wrap determines what we expose in the container.
        #   True: An instance of IEnv with key and value.
        #   False: The value only.
        # We use this so that the exposed value always matches the field type, for example:
        #
        #     frm: str = Transform.IN(env="TEST")  # Unwrapped
        #     frm: IEnv = Transform.IN()  # Wrapped
        self._wrap = _wrap

    def __repr__(self) -> str:
        return f"<IEnv key='{self.key}' policy='{self.policy}' value='{self.val}'>"


@InterfaceSerializer.register("env", (IEnv,))
class EnvSerializer(PrimitiveSerializer["TIEnvSerial", "IEnv"]):
    @classmethod
    def serialize(cls, token: "IEnv") -> "TIEnvSerial":
        val = cast(
            TIConstSerial | TIPathSerial | TIEnvListSerial,
            InterfaceSerializer.serialize(token.val),
        )
        return {
            "typ": "env",
            "key": token.key,
            "val": val,
            "policy": token.policy.name,
            "wrap": token._wrap,
        }

    @classmethod
    def walk_medials(cls, token: "TIEnvSerial"):
        yield from InterfaceSerializer.walk_medials(token["val"])

    @classmethod
    def walk_hashable(cls, token: "TIEnvSerial"):
        yield from InterfaceSerializer.walk_hashable(token["val"])
        yield {**token, "val": None}

    @classmethod
    def resolve(
        cls,
        token: "TIEnvSerial",
        ctx: Context,
        container: Container,
        direction: Direction,
    ):
        "Resolve env against a container, binding values in as required"
        key = token["key"]
        val = cast(TIEnv, InterfaceSerializer.resolve(token["val"], ctx, container, direction))
        try:
            policy = EnvPolicy[token["policy"]]
        except KeyError as e:
            raise ValueError(f"Invalid env policy {token['policy']}") from e
        wrap = token["wrap"]

        items = val if isinstance(val, list) else [val]
        for item in items:
            # Don't set env if the value is None
            if item is None:
                continue
            item = str(item)
            match policy:
                case EnvPolicy.APPEND:
                    container.append_env_path(key, item)
                case EnvPolicy.PREPEND:
                    container.prepend_env_path(key, item)
                case EnvPolicy.REPLACE:
                    container.set_env(key, item)
                case EnvPolicy.CONFLICT:
                    current_val = container.get_env(key)
                    if current_val is not None and item != current_val:
                        raise ValueError(
                            f"Can't set `${key}` to `{item}` as it's"
                            f" already set to `{current_val}` and"
                            f" replacement policy is `{policy}`"
                        )
                    container.set_env(key, item)
                case _:
                    raise ValueError(f"Invalid env policy {policy}")
        if wrap:
            return IEnv(key=key, val=val, policy=policy)
        return val


@InterfaceSerializer.register("dict", (dict,))
class DictSerializer(PrimitiveSerializer["TIDictSerial", "dict"]):
    @classmethod
    def serialize(cls, token: dict) -> "TIDictSerial | TIConstSerial":
        """
        Serialize a dict into the interface spec format.

        If every value is constant, the dict is downgraded to constant.
        """
        const = True
        serialized = {}
        for key, value_token in token.items():
            assert isinstance(key, str), "Keys must be string"
            serialized_value = SerialInterface.serialize_token(value_token)
            if serialized_value["typ"] != "const":
                const = False
            serialized[key] = serialized_value
        if const:
            return ConstSerializer.serialize({k: v["val"] for k, v in serialized.items()})
        else:
            return {"typ": "dict", "val": serialized}

    @classmethod
    def resolve(
        cls, token: "TIDictSerial", ctx: Context, container: Container, direction: Direction
    ):
        return {
            k: InterfaceSerializer.resolve(v, ctx, container, direction)
            for k, v in token["val"].items()
        }

    @classmethod
    def walk_medials(cls, token: "TIDictSerial"):
        for value in token["val"].values():
            yield from InterfaceSerializer.walk_medials(value)

    @classmethod
    def walk_hashable(cls, token: "TIDictSerial"):
        for value in token["val"].values():
            yield from InterfaceSerializer.walk_hashable(value)
        yield {**token, "val": None}

    @classmethod
    def default_factory(
        cls, token: type["TIAny"], name: str, transform: "Transform", field: "IField"
    ) -> "TIAny":
        # Default empty list if exactly list type (not a subclass) or list[<type>]
        if token is dict or get_origin(token) is dict:
            return {}
        return super().default_factory(token, name, transform, field)  # type: ignore


@InterfaceSerializer.register("list", (list,))
class ListSerializer(PrimitiveSerializer["TIListSerial", "list"]):
    @classmethod
    def serialize(cls, token: list) -> "TIListSerial | TIConstSerial":
        """
        Serialize a list into the interface spec format

        If every value is constant, the list is downgraded to constant.
        """
        const = True
        serialized = []
        for value_token in token:
            serialized_value = InterfaceSerializer.serialize(value_token)
            if serialized_value["typ"] != "const":
                const = False
            serialized.append(serialized_value)
        if const:
            return ConstSerializer.serialize([v["val"] for v in serialized])
        else:
            return {"typ": "list", "val": serialized}

    @classmethod
    def resolve(
        cls, token: "TIListSerial", ctx: Context, container: Container, direction: Direction
    ):
        return [InterfaceSerializer.resolve(v, ctx, container, direction) for v in token["val"]]

    @classmethod
    def walk_medials(cls, token: "TIListSerial"):
        for value in token["val"]:
            yield from InterfaceSerializer.walk_medials(value)

    @classmethod
    def walk_hashable(cls, token: "TIListSerial"):
        for value in token["val"]:
            yield from InterfaceSerializer.walk_hashable(value)
        yield {**token, "val": None}

    @classmethod
    def default_factory(
        cls, token: type["TIAny"], name: str, transform: "Transform", field: "IField"
    ) -> "TIAny":
        # Default empty list if exactly list type (not a subclass) or list[<type>]
        if token is list or get_origin(token) is list:
            return []
        return super().default_factory(token, name, transform, field)  # type: ignore


@InterfaceSerializer.register("const", (str, int, float, bool, NoneType))
class ConstSerializer(PrimitiveSerializer["TIConstSerial", "TIConstLeaf"]):
    @classmethod
    def serialize(cls, token: "TIConst") -> "TIConstSerial":
        "Serialize a constant value into the interface spec format"
        return {"typ": "const", "val": token}

    @classmethod
    def resolve(
        cls, token: "TIListSerial", ctx: Context, container: Container, direction: Direction
    ):
        return token["val"]


@dataclass_transform(kw_only_default=True)
class IFace:
    FIELD = dc_field

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        # Make subclasses a dataclass
        dataclass(kw_only=True, frozen=True, eq=False, repr=False)(cls)

    def __init__(self, value: "TIAny"):
        raise RuntimeError("Cannot instantiate interface directly, subclass it!")

    def resolve(self) -> "TIAny":
        raise NotImplementedError("IFace`{cls}` must implement a resolve method.")

    @classmethod
    def from_field(cls, transform: "Transform", field: "IField", name: str) -> Self:
        raise NotImplementedError("IFace `{cls}` cannot be auto-resolved as an output field.")


@InterfaceSerializer.register("__never__", (IFace,))
class IFaceSerializer(PrimitiveSerializer["TIConstSerial", "TIConstLeaf"]):
    @classmethod
    def serialize(cls, token: IFace) -> "TISerialAny":
        "Serialize a constant value into the interface spec format"
        return InterfaceSerializer.serialize(token.resolve())

    @classmethod
    def default_factory(
        cls, token: type[IFace], name: str, transform: "Transform", field: "IField"
    ) -> IFace:
        return token.from_field(transform, field, name)


TIConstLeaf = str | int | float | bool | NoneType
TIConst = TIConstLeaf | dict[str, "TIConst"] | Sequence["TIConst"]
TIPrimitives = Path | IEnv | IPath
TIEnv = TIConstLeaf | Path | IPath | Sequence[TIConstLeaf | Path | IPath]


TIAny = TIConstLeaf | TIPrimitives | IFace | Sequence["TIAny"] | dict[str, "TIAny"]
"The valid types for an interface"


class TIConstSerial(TypedDict):
    typ: Literal["const"]
    val: TIConst


class TIListSerial(TypedDict):
    typ: Literal["list"]
    val: Sequence["TISerialAny"]


class TIDictSerial(TypedDict):
    typ: Literal["dict"]
    val: dict[str, "TISerialAny"]


class TIPathSerial(TypedDict):
    typ: Literal["path"]
    host: str | None
    cont: str | None
    is_dir: bool


class TIEnvListSerial(TypedDict):
    typ: Literal["list"]
    val: Sequence[TIConstSerial]


class TIEnvSerial(TypedDict):
    typ: Literal["env"]
    key: str
    val: TIConstSerial | TIPathSerial | TIEnvListSerial
    policy: TIEnvPolicy
    wrap: bool


TISerialAny = (
    TIConstSerial | TIPathSerial | TIListSerial | TIDictSerial | TIEnvListSerial | TIEnvSerial
)
"The JSON-serializable interface specification format"


class SerialInterface:
    """
    Manages transform interfaces in a standard format that is serialisable
    using JSON.
    """

    _cached_input_hash: str | None = None
    "The (cached) hash of this serial interface"

    def __init__(self, value: TISerialAny):
        self.value = value
        "The interface in interface specification format"
        self.medials: list[Medial] = []
        "Medials the interface contains"
        self.scan_medials()

    @classmethod
    def from_interface(cls, token: "TIAny") -> "SerialInterface":
        "Factory to create from an interface"
        return cls(InterfaceSerializer.serialize(token))

    def scan_medials(self):
        "Scan through the serialisable interface and locate any medials"
        for medial in InterfaceSerializer.walk_medials(self.value):
            self.medials.append(medial)

    def resolve(self, ctx: Context, container: Container, direction: Direction):
        "Resolve against a container, binding values in as required"
        return InterfaceSerializer.resolve(self.value, ctx, container, direction)

    @classmethod
    def serialize_token(cls, token: TIAny) -> "TISerialAny":
        "Serialize any valid value into the interface spec format"
        return InterfaceSerializer.serialize(token)

    def _input_hash(self) -> str:
        """
        Get a hash of this serial interface.

        This should only be used when the interface is bound as an input
        """
        if self._cached_input_hash is not None:
            return self._cached_input_hash

        md5 = hashlib.md5()
        # Interface configuration
        for token in InterfaceSerializer.walk_hashable(self.value):
            md5.update(json.dumps(token).encode("utf8"))

        # Interface values from other transforms
        for medial in self.medials:
            md5.update(medial._input_hash().encode("utf8"))

        digest = md5.hexdigest()
        object.__setattr__(self, "_cached_input_hash", digest)
        return digest

    def __repr__(self) -> str:
        return f"<SerialInterface hash='{self._cached_input_hash}'>"


TIField = TypeVar("TIField", bound=TIAny)


class IField(Generic[TIField]):
    "The dataclass-like field type for interfaces"

    def __init__(
        self,
        *,
        init: bool = False,
        default: TIField | EllipsisType = ...,
        default_factory: Callable[[], TIField] | None = None,
        direction: Direction,
        env: str | EllipsisType = ...,
        env_policy: EnvPolicy = EnvPolicy.CONFLICT,
    ):
        self.init = init
        self.default = default
        self.default_factory = default_factory
        if self.default is not ... and self.default_factory is not None:
            raise ValueError("One of default and default_factory may be set, but not both!")
        self.direction = direction
        if direction.is_output and env is not ...:
            raise ValueError("IEnv can only be set for input interfaces")
        self.env = env
        self.env_policy = env_policy

    def resolve(self, transform: "Transform", field: Field[TIField]) -> SerialInterface:
        field_value = getattr(transform, field.name)

        if field_value is self:
            # Value not specified in constructor
            if self.default is not ...:
                # Try static default
                field_value = cast(TIField, self.default)
            elif self.default_factory is not None:
                # Try factoried default
                field_value = self.default_factory()
            else:
                # Try default for type
                field_value = InterfaceSerializer.default_factory(
                    field.type, field.name, transform, self
                )
            # Set the resolved value on the transform
            object.__setattr__(transform, field.name, field_value)

        if self.env is not ...:
            # Note env val is type checked
            interface_value = IEnv(
                key=self.env, val=cast(Any, field_value), policy=self.env_policy, _wrap=False
            )
        else:
            interface_value = field_value

        return SerialInterface.from_interface(interface_value)


def IN(  # noqa: N802
    *,
    default: TIField | EllipsisType = ...,
    default_factory: Callable[[], TIField] | None = None,
    init: bool = True,
    env: str | EllipsisType = ...,
    env_policy: EnvPolicy = EnvPolicy.CONFLICT,
) -> TIField:
    """
    Marks a transform field as an input interface.

    :param init: Whether this field should be set in the constructor. \
                 If false, default or default_factory is required.
    :param default: The default value - don't use for mutable types.
    :param default_factory: A factory for default values - use for mutable types.
    :param env: Additionally expose the interface in the specified environment variable
    :param env_policy: The replacement policy for env if the variable is already defined

    """
    return cast(
        TIField,
        IField(
            init=init,
            default=default,
            default_factory=default_factory,
            direction=Direction.INPUT,
            env=env,
            env_policy=env_policy,
        ),
    )


def OUT(  # noqa: N802
    *,
    init=False,
    default: TIField | EllipsisType = ...,
    default_factory: Callable[[], TIField] | None = None,
    env: str | EllipsisType = ...,
    env_policy: EnvPolicy = EnvPolicy.CONFLICT,
) -> TIField:
    """
    Marks a transform field as an output interface.

    :param init: Whether this field should be set in the constructor.
    :param default: The default value - don't use for mutable types. \
                    The value '...' has special meaning when used \
                    with init=True, allowing the interface to be set \
                    in the costructor, but with an automatic default.
    :param default_factory: A factory for default values - use for mutable types
    :param env: Additionally expose the interface in the specified environment variable
    :param env_policy: The replacement policy for env if the variable is already defined

    """
    return cast(
        TIField,
        IField(
            init=init,
            default=default,
            default_factory=default_factory,
            direction=Direction.OUTPUT,
            env=env,
            env_policy=env_policy,
        ),
    )


class TSerialTransform(TypedDict):
    mod: str
    name: str
    ifaces: dict[str, TISerialAny]


class TSerialTransformResult(TypedDict):
    run_time: float


@dataclass_transform(kw_only_default=True, frozen_default=True, field_specifiers=(IN, OUT))
class Transform:
    """
    Base class for Transforms. Transforms are specified using dataclass
    syntax as follows::

        class Copy(Transform):
            tools = (Bash,)
            frm: Path = Transform.IN()
            to: Path = Transform.OUT()

            def execute(self, ctx, tools):
                yield tools.bash.get_action("cp")(ctx, frm=self.frm, to=self.to)

    """

    # Shortcuts to the field direction specifiers
    IN = IN
    OUT = OUT

    tools: tuple[type["Tool"], ...] = ()
    "Tools which are required for this transform"

    _serial_interfaces: dict[str, tuple[Direction, SerialInterface]]
    "The internal representation of interfaces"

    _cached_input_hash: str | None = None
    "The (cached) hash of this transforms inputs"

    api: ConfigApi

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        # Make subclasses a dataclass
        dataclass(kw_only=True, frozen=True, eq=False, repr=False)(cls)
        # Ensure not defined inline as we rely on transforms being locatable
        if "<locals>" in cls.__qualname__:
            raise RuntimeError(f"Transforms must not be defined inline, got: {cls.__qualname__}")

    def __init__(self):
        raise RuntimeError("Cannot instantiate transform directly, subclass it!")

    def __post_init__(self):
        if getattr(self, "_tf_execute_proxy", False):
            return
        object.__setattr__(self, "api", ConfigApi.current.with_transform(self))
        object.__setattr__(self, "_serial_interfaces", {})
        # Wrapped here since if they are overriden they still
        # must be cached.
        for field in fields(cast(Any, self)):
            if not isinstance(field.default, IField):
                if field.name == "tools":
                    continue
                raise ValueError(
                    "All transform interfaces must be specified with a direction"
                    ", e.g. `myinput: Path = Transform.IN()`"
                )
            ifield = field.default
            self._serial_interfaces[field.name] = (ifield.direction, ifield.resolve(self, field))

    def serialize(self) -> TSerialTransform:
        return {
            "mod": type(self).__module__,
            "name": type(self).__qualname__,
            "ifaces": {k: v[1].value for k, v in self._serial_interfaces.items()},
        }

    def _import_hash(self) -> str:
        return Cache.hash_imported_package(self.__class__.__module__)

    def _input_hash(self) -> str:
        """
        Get a hash of the inputs to this transform.

        This can only be used once all transforms in a graph are initialised.
        """
        if self._cached_input_hash is not None:
            return self._cached_input_hash

        md5 = hashlib.md5()
        md5.update(self._import_hash().encode("utf8"))
        for name, (direction, serial) in self._serial_interfaces.items():
            if direction.is_output:
                continue
            # Interface name
            md5.update(name.encode("utf8"))
            # Interface value
            md5.update(serial._input_hash().encode("utf8"))
        digest = md5.hexdigest()
        object.__setattr__(self, "_cached_input_hash", digest)
        return digest

    @staticmethod
    def deserialize(spec: TSerialTransform) -> "Transform":
        # Get transform module
        mod = importlib.import_module(spec["mod"])
        # Get class from module (using reduce to navigate module namespacing)
        cls: Transform = reduce(getattr, spec["name"].split("."), mod)
        tf = cls.__new__(cls)

        object.__setattr__(tf, "_serial_interfaces", {})
        for field in fields(cast(Any, tf)):
            if not isinstance(field.default, IField):
                if field.name == "tools":
                    continue
                raise ValueError(
                    "All transform interfaces must be specified with a direction"
                    ", e.g. `myinput: Path = Transform.IN()`"
                )
            ifield = field.default
            tf._serial_interfaces[field.name] = (
                ifield.direction,
                SerialInterface(spec["ifaces"][field.name]),
            )
        return tf

    def run(self, ctx: "Context") -> TSerialTransformResult:
        """Run the transform in a container."""
        start = time.time()

        # Create  a container
        # Note need to do this import here to avoid circular import
        from ..foundation import Foundation

        container = Foundation(ctx)

        # Bind tools to container
        tool_instances: dict[str, Version] = {}
        for tool_def in self.tools:
            tool = tool_def()
            tool_instances[tool.name] = tool.default
            container.add_tool(tool)

        # Bind interfaces to container
        interface_values: dict[str, Any] = {}

        # Cast to Any to satisfy type checkers as the base Transform class will
        # not be a dataclass, but subclasses will.
        for field in fields(cast(Any, self)):
            if not isinstance(field.default, IField):
                if field.name == "tools":
                    continue
                raise ValueError(
                    "All transform interfaces must be specified with a direction"
                    ", e.g. `myinput: Path = Transform.IN()`"
                )
            direction, serial = self._serial_interfaces[field.name]
            interface_values[field.name] = serial.resolve(ctx, container, direction)

        tools = ReadonlyNamespace(**tool_instances)

        # Construct transform instance
        cls = type(self)
        tf = cls.__new__(cls)
        object.__setattr__(tf, "_tf_execute_proxy", True)
        tf.__init__(**interface_values)

        for invocation in tf.execute(ctx, tools):
            if exit_code := container.invoke(ctx, invocation) != 0:
                raise RuntimeError(
                    f"Invocation `{invocation}` failed with exit code `{exit_code}`."
                )
        stop = time.time()
        return TSerialTransformResult(run_time=stop - start)

    def execute(
        self, ctx: "Context", tools: ReadonlyNamespace["Version"], iface: ReadonlyNamespace[Any], /
    ) -> Iterable["Invocation"]:
        """
        Execute method to be implemented in subclasses.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{type(self).__name__} hash='{self._cached_input_hash}'>"
