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
from collections.abc import Callable, Generator, Sequence
from dataclasses import Field, dataclass, field, fields
from enum import Enum, auto
from functools import cached_property, reduce
from pathlib import Path
from types import EllipsisType, GenericAlias, NoneType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Literal,
    NoReturn,
    Self,
    TypedDict,
    TypeVar,
    TypeVarTuple,
    Unpack,
    cast,
    dataclass_transform,
    get_origin,
)

from ordered_set import OrderedSet as OSet

from blockwork.common.singleton import Singleton
from blockwork.foundation import Foundation
from blockwork.tools import Tool

from ..build.caching import Cache
from ..config.api import ConfigApi
from ..context import Context

if TYPE_CHECKING:
    from ..context import Context
    from ..tools import Invocation


class Medial:
    """
    Medials represent values passed between transforms.
    """

    val: str
    "Medial value"
    _producers: "OSet[Transform] | None"
    "The transforms that produce this medial"
    _consumers: "OSet[Transform] | None"
    "The transfoms that consume this medial (implemented but unused)"
    _cached_input_hash: str | None
    "The (cached) hash of this medial's inputs"

    def __init__(self, val: str):
        self.val = val
        self._producers = None
        self._consumers = None
        self._cached_input_hash = None

    def __hash__(self) -> int:
        return hash(self.val)

    def __eq__(self, other: object):
        return isinstance(other, Medial) and (self.val == other.val)

    def bind_consumers(self, consumers: OSet["Transform"]):
        """
        Bind a list of transforms that consume this medial.

        Note:
            - This deliberately binds a list by reference as it is built
              up
            - Currently unused but could be used for graphing later
        """
        if self._consumers is None:
            self._consumers = consumers
        elif self._consumers is not consumers:
            raise RuntimeError("Consumers already bound to medial!")

    def bind_producers(self, producers: OSet["Transform"]):
        """
        Bind the transforms that produce this medial.

        Note:
            - This deliberately binds a list by reference as it is built
              up
        """
        if self._producers is None:
            self._producers = producers
        elif self._producers is not producers:
            raise RuntimeError("Producers already bound to medial!")

        if len(producers) > 1:
            raise RuntimeError(f"Medial `{self}` produced by more than one transform `{producers}`")

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
            self._cached_input_hash = self._content_hash()

        return self._cached_input_hash

    def _byte_size(self) -> int:
        """
        Get the size of this medial in bytes
        """
        return Cache.hash_size_content(Path(self.val))[1]

    def _content_hash(self) -> str:
        """
        Get the hash of this medial

        MUST only be used after the transform producing this medial has been
        run or if this medial is a static file.
        """
        return Cache.hash_size_content(Path(self.val))[0]

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
    def serialize(cls, token: TIType) -> "TIPrimitive":
        raise NotImplementedError

    @classmethod
    def resolve(
        cls,
        token: TIPrimitive,
        ctx: Context,
        container: Foundation,
        direction: Direction,
    ) -> "TIAny":
        raise NotImplementedError

    @classmethod
    def default_factory(
        cls, token: type[TIType] | str, name: str, api: ConfigApi, field: "IField"
    ) -> TIType:
        cls.default_error(token, name, api, field)

    @classmethod
    def default_error(
        cls, token: type[TIType] | str, name: str, api: ConfigApi, field: "IField"
    ) -> NoReturn:
        field_str = "IN(...)" if field.direction.is_input else "OUT(...)"
        if api._transform:
            transform_str = type(api._transform).__name__
        else:
            transform_str = "Unknown"
        if isinstance(token, str):
            type_str = token
        elif type(token) is not GenericAlias or (type_str := get_origin(token)) is None:
            type_str = token.__name__
        raise RuntimeError(
            "Can't automatically set default for field for "
            f"{transform_str}: `{name}: {type_str} = {field_str}`"
        )

    @classmethod
    def walk(cls, token: "TIPrimitive", meta: "SerialInterface"):
        meta.update_hash(token)


TISerializer = TypeVar("TISerializer", bound=PrimitiveSerializer[Any, Any])


class InterfaceSerializer(PrimitiveSerializer["TISerialAny", "TIAny"], metaclass=Singleton):
    """
    The top level serializer which knows about all others.
    """

    quick_type_map: ClassVar[dict[type, type[PrimitiveSerializer]]] = {}
    slow_type_map: ClassVar[dict[tuple[type, ...], type[PrimitiveSerializer]]] = {}
    key_map: ClassVar[dict[str, type[PrimitiveSerializer]]] = {}

    @classmethod
    def register(cls, key: str, types: tuple[type, ...]):
        def inner(serializer: type[TISerializer]) -> type[TISerializer]:
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
        cls,
        token: "TISerialAny",
        ctx: Context,
        container: Foundation,
        direction: Direction,
    ) -> "TIAny":
        "Resolve a token against a container, binding values in as required"
        if (serializer := cls.key_map.get(token["typ"])) is not None:
            return serializer.resolve(token, ctx, container, direction)
        raise RuntimeError(f"Invalid interface type: `{token}`")

    @classmethod
    def default_factory(
        cls, token: type["TIAny"] | str, name: str, api: ConfigApi, field: "IField"
    ) -> "TIAny":
        if isinstance(token, str):
            return super().default_factory(token, name, api, field)

        # If we have a type like list[str], send it to the serializer for list
        if type(token) is not GenericAlias or (map_token := get_origin(token)) is None:
            map_token = token

        # Try the quick map
        if (serializer := cls.quick_type_map.get(map_token)) is not None:
            return serializer.default_factory(token, name, api, field)

        # Try the slow map
        for types, serializer in cls.slow_type_map.items():
            if issubclass(map_token, types):
                return serializer.default_factory(token, name, api, field)

        return super().default_factory(token, name, api, field)

    @classmethod
    def walk(cls, token: "TISerialAny", meta: "SerialInterface"):
        "Walk over all tokens"
        if (serializer := cls.key_map.get(token["typ"])) is not None:
            serializer.walk(token, meta)
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
        cls,
        token: "TIPathSerial",
        ctx: Context,
        container: Foundation,
        direction: Direction,
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
            if token["is_dir"] or host_path.name != cont_path.name:
                # If last path component differs for files, we need to bind file
                # directly as we can't bind directory and get file within it
                container.bind(host_path, cont_path, readonly=readonly, mkdir=True)
            else:
                # Otherwise bind the directory above for efficiency
                container.bind(host_path.parent, cont_path.parent, readonly=readonly, mkdir=True)
        else:
            if token["cont"] is None:
                raise ValueError("Both host path and container path cannot be None!")
            cont_path = Path(token["cont"])
        return cont_path

    @classmethod
    def default_factory(
        cls,
        token: type[Path] | type[IPath] | str,
        name: str,
        api: ConfigApi,
        field: "IField",
    ) -> Path | IPath:
        if field.direction.is_input:
            super().default_factory(token, name, api, field)
        return api.path(name)

    @classmethod
    def walk(cls, token: "TIPathSerial", meta: "SerialInterface"):
        if token["host"] is not None:
            meta.update_medials(Medial(token["host"]))
        # Omit the paths themselves as they are likely to be generated
        meta.update_hash(
            {**token, "host": token["host"] is not None, "cont": token["cont"] is not None}
        )


class IEnv:
    """
    An interface primitive which can be used to expose environment variables.
    """

    def __init__(
        self,
        key: str,
        val: "TIEnv",
        policy: EnvPolicy = EnvPolicy.CONFLICT,
        _wrap: bool = True,
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
        serial: TIEnvSerial = {
            "typ": "env",
            "key": token.key,
            "val": val,
            "policy": token.policy.name,
            "wrap": token._wrap,
        }
        return serial

    @classmethod
    def resolve(
        cls,
        token: "TIEnvSerial",
        ctx: Context,
        container: Foundation,
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

    @classmethod
    def walk(cls, token: "TIEnvSerial", meta: "SerialInterface"):
        InterfaceSerializer.walk(token["val"], meta)
        meta.update_hash({**token, "val": None})


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
            serialized_value = InterfaceSerializer.serialize(value_token)
            if serialized_value["typ"] != "const":
                const = False
            serialized[key] = serialized_value
        if const:
            return ConstSerializer.serialize({k: v["val"] for k, v in serialized.items()})
        else:
            return {"typ": "dict", "val": serialized}

    @classmethod
    def resolve(
        cls,
        token: "TIDictSerial",
        ctx: Context,
        container: Foundation,
        direction: Direction,
    ):
        return {
            k: InterfaceSerializer.resolve(v, ctx, container, direction)
            for k, v in token["val"].items()
        }

    @classmethod
    def walk(cls, token: "TIDictSerial", meta: "SerialInterface"):
        for value in token["val"].values():
            InterfaceSerializer.walk(value, meta)
        meta.update_hash({**token, "val": sorted(token["val"].keys())})

    @classmethod
    def default_factory(
        cls, token: type[dict] | str, name: str, api: ConfigApi, field: "IField"
    ) -> dict:
        # Default empty list if exactly list type (not a subclass) or list[<type>]
        if token is dict or get_origin(token) is dict:
            return {}
        return super().default_factory(token, name, api, field)  # type: ignore


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
            return cast(TIListSerial, {"typ": "list", "val": serialized})

    @classmethod
    def resolve(
        cls,
        token: "TIListSerial",
        ctx: Context,
        container: Foundation,
        direction: Direction,
    ):
        return [InterfaceSerializer.resolve(v, ctx, container, direction) for v in token["val"]]

    @classmethod
    def walk(cls, token: "TIListSerial", meta: "SerialInterface"):
        for value in token["val"]:
            InterfaceSerializer.walk(value, meta)
        meta.update_hash({**token, "val": None})

    @classmethod
    def default_factory(
        cls, token: type[list] | str, name: str, api: ConfigApi, field: "IField"
    ) -> list:
        # Default empty list if exactly list type (not a subclass) or list[<type>]
        if token is list or get_origin(token) is list:
            return []
        return super().default_factory(token, name, api, field)  # type: ignore


@InterfaceSerializer.register("const", (str, int, float, bool, NoneType))
class ConstSerializer(PrimitiveSerializer["TIConstSerial", "TIConstLeaf"]):
    @classmethod
    def serialize(cls, token: "TIConst") -> "TIConstSerial":
        "Serialize a constant value into the interface spec format"
        return {"typ": "const", "val": token}

    @classmethod
    def resolve(
        cls,
        token: "TIConstSerial",
        ctx: Context,
        container: Foundation,
        direction: Direction,
    ):
        return cast(TIAny, token["val"])


TIConstLeaf = str | int | float | bool | NoneType
TIConst = TIConstLeaf | dict[str, "TIConst"] | Sequence["TIConst"]
TIPrimitives = Path | IEnv | IPath
TIEnv = TIConstLeaf | Path | IPath | Sequence[TIConstLeaf | Path | IPath]


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


class SerialInterface:
    """
    Manages transform interfaces in a standard format that is serialisable
    using JSON.
    """

    _cached_input_hash: str | None
    "The (cached) hash of this serial interface"

    def __init__(self, value: "TISerialAny", direction: Direction = Direction.INPUT):
        "The interface in interface specification format"
        self.direction = direction
        self.medials = list[Medial]()
        self.tokens = list[Any]()
        self.value = value
        self._cached_input_hash = None
        InterfaceSerializer.walk(self.value, self)

    @classmethod
    def from_interface(
        cls, token: "TIAny", direction: Direction = Direction.INPUT
    ) -> "SerialInterface":
        "Factory to create from an interface"
        return cls(InterfaceSerializer.serialize(token), direction)

    def update_hash(self, *tokens: Any):
        self.tokens += tokens

    def update_medials(self, *medials: Medial):
        self.medials += medials

    def resolve(self, ctx: Context, container: Foundation, direction: Direction):
        "Resolve against a container, binding values in as required"
        return InterfaceSerializer.resolve(self.value, ctx, container, direction)

    def _input_hash(self) -> str:
        """
        Get a hash of this serial interface.

        This should only be used when the interface is bound as an input
        """
        if self._cached_input_hash is not None:
            return self._cached_input_hash

        md5 = hashlib.md5()
        # Interface configuration
        for token in self.tokens:
            md5.update(json.dumps(token).encode("utf8"))

        # Interface values from other transforms
        for medial in self.medials:
            md5.update(medial._input_hash().encode("utf8"))

        digest = md5.hexdigest()
        self._cached_input_hash = digest
        return digest

    def __repr__(self) -> str:
        return f"<SerialInterface hash='{self._cached_input_hash}'>"


TField = TypeVar("TField")


class FieldProtocol(Generic[TField]):
    "The dataclass-like field type for interfaces"

    def resolve(
        self, target: "Transform | IFace", api: ConfigApi, field: Field[TField]
    ) -> SerialInterface:
        "Resolve missing field values and returns a serialisable interface"
        raise NotImplementedError()

    def bind(
        self,
        ctx: Context,
        container: Foundation,
        field: Field[TField],
        token: "TISerialAny",
        direction: Direction,
    ) -> TField:
        "Bind a field value to the container and return the resolved value"
        raise NotImplementedError()


TIField = TypeVar("TIField", bound="TIAny")
TDeriveTuple = TypeVarTuple("TDeriveTuple")
TDeriveSingle = TypeVar("TDeriveSingle")


class IField(FieldProtocol[TIField]):
    "The dataclass-like field type for interfaces"

    def __init__(
        self,
        *,
        init: bool = False,
        default: TIField | EllipsisType = ...,
        default_factory: Callable[[], TIField] | None = None,
        derive: tuple[tuple[Unpack[TDeriveTuple]], Callable[[Unpack[TDeriveTuple]], TIField]]
        | tuple[TDeriveSingle, Callable[[TDeriveSingle], TIField]]
        | None = None,
        direction: Direction,
        env: str | EllipsisType = ...,
        env_policy: EnvPolicy = EnvPolicy.CONFLICT,
    ):
        self.init = init
        self.default = default
        self.default_factory = default_factory
        self.derive = derive
        if sum((self.default is ..., self.default_factory is None, self.derive is None)) < 2:
            raise ValueError("Only one of default, default_factory, and derive may be set!")
        self.direction = direction
        self.env = env
        self.env_policy = env_policy
        self.value: Any = None

    def resolve(
        self, target: "Transform | IFace", api: ConfigApi, field: Field[TIField]
    ) -> SerialInterface:
        "Resolve missing field values and returns a serialisable interface"
        field_value = getattr(target, field.name)

        if field_value is self:
            # Value not specified in constructor
            if self.default is not ...:
                # Try static default
                field_value = cast(TIField, self.default)
            elif self.default_factory is not None:
                # Try factoried default
                field_value = self.default_factory()
            elif self.derive is not None:
                # Derive if specified
                deps, callback = self.derive
                deps = cast(tuple[IField], deps if isinstance(deps, tuple) else (deps,))
                field_value = callback(*(dep.value for dep in deps))  # type: ignore
            else:
                # Try default for type
                field_value = InterfaceSerializer.default_factory(field.type, field.name, api, self)
            # Set the resolved value on the transform
            object.__setattr__(target, field.name, field_value)

        if self.env is not ...:
            # Note env val is type checked
            interface_value = IEnv(
                key=self.env,
                val=cast(Any, field_value),
                policy=self.env_policy,
                _wrap=False,
            )
        else:
            interface_value = field_value

        # Update the value on the field itself
        self.value = field_value

        return SerialInterface.from_interface(interface_value, self.direction)

    def bind(
        self,
        ctx: Context,
        container: Foundation,
        field: Field[TIField],
        token: "TISerialAny",
        direction: Direction,
    ):
        "Bind a field value to the container and return the resolved value"
        return InterfaceSerializer.resolve(token, ctx, container, direction)


class ITool(FieldProtocol[Tool]):
    "The dataclass-like field type for tools"

    def __init__(
        self,
        *,
        init: bool = False,
        version: str | None = None,
    ):
        self.init = init
        self.version = version
        self.direction = Direction.INPUT

    def resolve(
        self, target: "Transform | IFace", api: ConfigApi, field: Field[Tool]
    ) -> SerialInterface:
        "Resolve missing field values and returns a serialisable interface"
        field_value = getattr(target, field.name)
        if field_value is self:
            # Value not specified in constructor
            # Create from version
            field_value = field.type(self.version)
            # Set the resolved value on the transform
            object.__setattr__(target, field.name, field_value)
        # Serialise the tool version
        return SerialInterface.from_interface(field_value.vernum, self.direction)

    def bind(
        self,
        ctx: Context,
        container: Foundation,
        field: Field[Tool],
        token: "TISerialAny",
        direction: Direction,
    ) -> Tool:
        "Bind a field value to the container and return the resolved value"
        tool = field.type(InterfaceSerializer.resolve(token, ctx, container, direction))
        container.add_tool(tool)
        return tool


def IN(  # noqa: N802
    *,
    default: "TIField | EllipsisType" = ...,
    default_factory: Callable[[], "TIField"] | None = None,
    derive: tuple[tuple[Unpack[TDeriveTuple]], Callable[[Unpack[TDeriveTuple]], "TIField"]]
    | tuple[TDeriveSingle, Callable[[TDeriveSingle], "TIField"]]
    | None = None,
    init: bool = True,
    env: str | EllipsisType = ...,
    env_policy: EnvPolicy = EnvPolicy.CONFLICT,
) -> "TIField":
    """
    Marks a transform field as an input interface.

    :param init: Whether this field should be set in the constructor. \
                 If false, default or default_factory is required.
    :param default: The default value - don't use for mutable types.
    :param default_factory: A factory for default values - use for mutable types.
    :param derive: A tuple containing the derive dependencies (other fields),
                   and a factory which takes those fields as arguments.
    :param env: Additionally expose the interface in the specified environment variable
    :param env_policy: The replacement policy for env if the variable is already defined

    """
    return cast(
        TIField,
        IField(
            init=init,
            default=default,
            default_factory=default_factory,
            derive=derive,
            direction=Direction.INPUT,
            env=env,
            env_policy=env_policy,
        ),
    )


def OUT(  # noqa: N802
    *,
    init=False,
    default: "TIField | EllipsisType" = ...,
    default_factory: Callable[[], "TIField"] | None = None,
    derive: tuple[tuple[Unpack[TDeriveTuple]], Callable[[Unpack[TDeriveTuple]], "TIField"]]
    | tuple[TDeriveSingle, Callable[[TDeriveSingle], "TIField"]]
    | None = None,
    env: str | EllipsisType = ...,
    env_policy: EnvPolicy = EnvPolicy.CONFLICT,
) -> "TIField":
    """
    Marks a transform field as an output interface.

    :param init: Whether this field should be set in the constructor.
    :param default: The default value - don't use for mutable types. \
                    The value '...' has special meaning when used \
                    with init=True, allowing the interface to be set \
                    in the costructor, but with an automatic default.
    :param default_factory: A factory for default values - use for mutable types

    """
    return cast(
        TIField,
        IField(
            init=init,
            default=default,
            default_factory=default_factory,
            derive=derive,
            direction=Direction.OUTPUT,
            env=env,
            env_policy=env_policy,
        ),
    )


def TOOL(  # noqa: N802
    *,
    init=False,
    version: str | None = None,
) -> TIField:
    """
    Marks a transform field as a tool input.

    :param init: Whether this field should be set in the constructor. \
                 There is no foreseen reason to set this to True.
    :param version: The version to use, uses default if not specified.
    """
    return cast(
        TIField,
        ITool(
            init=init,
            version=version,
        ),
    )


@dataclass_transform(kw_only_default=True, frozen_default=True)
class IFace:
    FIELD = IN
    TOOL = TOOL

    _serial_interfaces: dict[str, SerialInterface]
    "The internal representation of (sub) interfaces"

    _cached_input_hash: str | None = None
    "The (cached) hash of this transforms inputs"

    api: ConfigApi

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        # Make subclasses a dataclass
        cls._direction = Direction.INPUT
        dataclass(kw_only=True, frozen=True, eq=False, repr=False)(cls)
        # Ensure not defined inline as we rely on transforms being locatable
        if "<locals>" in cls.__qualname__:
            raise RuntimeError(f"IFaces must not be defined inline, got: {cls.__qualname__}")

    def __post_init__(self):
        if getattr(self, "_iface_resolve_proxy", False):
            return
        object.__setattr__(self, "api", ConfigApi.current)
        object.__setattr__(self, "_serial_interfaces", {})
        with self.api as api:
            for iface_field in fields(cast(Any, self)):
                if not isinstance(iface_field.default, IField | ITool):
                    raise ValueError(
                        "All transform interfaces must be specified with a direction"
                        ", e.g. `myinput: Path = Transform.IN()`"
                    )
                ifield = iface_field.default
                ifield.direction = self._direction
                self._serial_interfaces[iface_field.name] = ifield.resolve(self, api, iface_field)

    def __init__(self):
        raise RuntimeError("Cannot instantiate IFace directly, subclass it!")


class TIFaceSerial(TypedDict):
    typ: Literal["IFace"]
    mod: str
    name: str
    ifields: dict[str, "TISerialAny"]


@InterfaceSerializer.register("IFace", (IFace,))
class IFaceSerializer(PrimitiveSerializer["TIFaceSerial", "IFace"]):
    @classmethod
    def serialize(cls, token: IFace) -> "TIFaceSerial":
        return {
            "typ": "IFace",
            "mod": type(token).__module__,
            "name": type(token).__qualname__,
            "ifields": {k: v.value for k, v in token._serial_interfaces.items()},
        }

    @classmethod
    def resolve(
        cls,
        token: "TIFaceSerial",
        ctx: Context,
        container: Foundation,
        direction: Direction,
    ) -> "IFace":
        # Get IFace module
        mod = importlib.import_module(token["mod"])
        # Get class from module (using reduce to navigate module namespacing)
        iface_cls: type[IFace] = reduce(getattr, token["name"].split("."), mod)

        # Bind interfaces to container
        ifield_values: dict[str, Any] = {}
        for iface_field in fields(cast(Any, iface_cls)):
            if not isinstance(iface_field.default, IField | ITool):
                raise ValueError(
                    "All IFace interfaces must be specified with a direction"
                    ", e.g. `myinput: Path = IFace.FIELD()`"
                )
            value = token["ifields"][iface_field.name]
            ifield = iface_field.default
            ifield_values[iface_field.name] = ifield.bind(
                ctx, container, iface_field, value, direction
            )

        # Construct iface instance
        iface = iface_cls.__new__(iface_cls)
        object.__setattr__(iface, "_iface_resolve_proxy", True)
        iface.__init__(**ifield_values)

        return iface

    @classmethod
    def default_factory(
        cls, token: type["IFace"] | str, name: str, api: ConfigApi, field: "IField"
    ) -> "IFace":
        if isinstance(token, str):
            cls.default_error(token, name, api, field)
        # TODO DEAL WITH THIS
        token._direction = field.direction
        result = token()
        token._direction = Direction.INPUT
        return result

    @classmethod
    def walk(cls, token: "TIFaceSerial", meta: "SerialInterface"):
        for value in token["ifields"].values():
            InterfaceSerializer.walk(value, meta)
        meta.update_hash({**token, "ifields": sorted(token["ifields"].keys())})


class SerialTransform(TypedDict):
    typ: Literal["Transform"]
    mod: str
    name: str
    ifaces: dict[str, "TISerialAny"]


TISerialAny = (
    TIConstSerial
    | TIPathSerial
    | TIListSerial
    | TIDictSerial
    | TIEnvListSerial
    | TIEnvSerial
    | TIFaceSerial
)
"The JSON-serializable interface specification format"

TIAny = TIConstLeaf | TIPrimitives | IFace | Sequence["TIAny"] | dict[str, "TIAny"]
"The valid types for an interface"


@dataclass(frozen=True, kw_only=True)
class Result:
    exit_code: int | None
    run_time: float
    ident: str
    _accepted: bool = field(init=False, default=False, compare=False, repr=False, hash=False)

    def resolve(self):
        "Resolve this result, raising an error if it has not been accepted"
        if self._accepted or self.exit_code == 0:
            return
        self.reject(f"exit_code was `{self.exit_code}`")

    def reject(self, details: str = "result was rejected"):
        "Reject this result, raising an error"
        raise RuntimeError(f"{self.ident} failed: {details}")

    def accept(self):
        "Mark this result as accepted"
        object.__setattr__(self, "_accepted", True)
        return True


@dataclass_transform(kw_only_default=True, frozen_default=True, field_specifiers=(IN, OUT, TOOL))
class Transform:
    """
    Base class for Transforms. Transforms are specified using dataclass
    syntax as follows::

        class Copy(Transform):
            bash: Bash = Transform.TOOL()
            frm: Path = Transform.IN()
            to: Path = Transform.OUT()

            def execute(self, ctx):
                yield self.bash.cp(ctx, frm=self.frm, to=self.to)

    """

    # Shortcuts to the field direction specifiers
    IN = IN
    OUT = OUT
    TOOL = TOOL

    _serial_interfaces: dict[str, SerialInterface]
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
        with self.api as api:
            for tf_field in fields(cast(Any, self)):
                if not isinstance(tf_field.default, IField | ITool):
                    raise ValueError(
                        "All transform interfaces must be specified with a direction"
                        ", e.g. `myinput: Path = Transform.IN()`"
                    )
                ifield = tf_field.default
                self._serial_interfaces[tf_field.name] = ifield.resolve(self, api, tf_field)

    @cached_property
    def _mod_name(self) -> str:
        return type(self).__module__

    @cached_property
    def _cls_name(self) -> str:
        return type(self).__qualname__

    def serialize(self) -> SerialTransform:
        return {
            "typ": "Transform",
            "mod": self._mod_name,
            "name": self._cls_name,
            "ifaces": {k: v.value for k, v in self._serial_interfaces.items()},
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
        for name, serial in self._serial_interfaces.items():
            if serial.direction.is_output:
                continue
            # Interface name
            md5.update(name.encode("utf8"))
            # Interface value
            md5.update(serial._input_hash().encode("utf8"))
        digest = md5.hexdigest()
        object.__setattr__(self, "_cached_input_hash", digest)
        return digest

    @staticmethod
    def deserialize(spec: SerialTransform) -> "Transform":
        # Get transform module
        mod = importlib.import_module(spec["mod"])
        # Get class from module (using reduce to navigate module namespacing)
        cls: Transform = reduce(getattr, spec["name"].split("."), mod)
        tf = cls.__new__(cls)

        object.__setattr__(tf, "_serial_interfaces", {})
        for tf_field in fields(cast(Any, tf)):
            if not isinstance(tf_field.default, IField | ITool):
                raise ValueError(
                    "All transform interfaces must be specified with a direction"
                    ", e.g. `myinput: Path = Transform.IN()`"
                )
            ifield = tf_field.default
            tf._serial_interfaces[tf_field.name] = SerialInterface(
                spec["ifaces"][tf_field.name], direction=ifield.direction
            )

        return tf

    def run(self, ctx: "Context") -> Result:
        """Run the transform in a container."""
        tf_start = time.time()

        # Create  a container
        # Note need to do this import here to avoid circular import
        from ..foundation import Foundation

        container = Foundation(ctx)

        # Bind interfaces to container
        interface_values: dict[str, Any] = {}

        # Cast to Any to satisfy type checkers as the base Transform class will
        # not be a dataclass, but subclasses will.
        for tf_field in fields(cast(Any, self)):
            if not isinstance(tf_field.default, IField | ITool):
                raise ValueError(
                    "All transform interfaces must be specified with a direction"
                    ", e.g. `myinput: Path = Transform.IN()`"
                )
            ifield = tf_field.default
            serial = self._serial_interfaces[tf_field.name]
            interface_values[tf_field.name] = ifield.bind(
                ctx, container, tf_field, serial.value, ifield.direction
            )

        # Construct transform instance
        cls = type(self)
        tf = cls.__new__(cls)
        object.__setattr__(tf, "_tf_execute_proxy", True)
        tf.__init__(**interface_values)

        invocation_iter = tf.execute(ctx)
        exit_code = None
        result = None
        try:
            # Get the first
            invocation = next(invocation_iter)
            while True:
                # Invoke and create result object
                ivk_start = time.time()
                exit_code = container.invoke(ctx, invocation)
                ivk_stop = time.time()
                result = Result(
                    exit_code=exit_code, run_time=(ivk_stop - ivk_start), ident=str(invocation)
                )
                # Pass the result object back
                invocation = invocation_iter.send(result)
                # Resolve the result before handling next invocation
                result.resolve()
        except StopIteration:
            # Resolve last iteration if it stopped on send
            if result:
                result.resolve()
        tf_stop = time.time()
        # Return a result object with the final exit_code and total run_time
        return Result(exit_code=exit_code, run_time=(tf_stop - tf_start), ident=str(tf))

    def execute(self, ctx: "Context", /) -> Generator["Invocation", Result, None]:
        """
        Execute method to be implemented in subclasses.
        """
        raise NotImplementedError

    def tf_report(self, ctx: "Context", /) -> None:
        """
        Host hook to report on this transform after all transforms have run.
        """

    @classmethod
    def tf_cls_report(cls, ctx: "Context", transforms: list[Self], /) -> None:
        """
        Host hook to report on all instances of this transform after all transforms have run.
        """

    def __repr__(self) -> str:
        return f"<{type(self).__name__} hash='{self._cached_input_hash}'>"
