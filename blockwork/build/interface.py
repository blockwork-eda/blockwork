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

from enum import Enum, auto
from functools import cache
import hashlib
from pathlib import Path
import shlex
import types
from typing import Any, Callable, Generic, Hashable, Iterable, Optional, Sequence, TypeVar, TYPE_CHECKING
from .caching import Cache

from blockwork.context import Context

from ..common.complexnamespaces import ReadonlyNamespace

from ..common.inithooks import InitHooks

from ..common.singleton import keyed_singleton

from ..containers.container import Container

if TYPE_CHECKING:
    from ..context import Context
    from .transform import Transform


class InterfaceError(Exception): ...

# The resolved value type
_RVALUE = TypeVar("_RVALUE")

class Direction(Enum):
    '''
    Used to identify if an interface is acting as an input-to or output-from
    a container
    '''
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


class Pipe(Enum):
    '''
    Used to control whether an interface is resolved on the host or on the
    container when passed through to a transform.
    '''
    HOST = auto()
    FLOW = auto()


@InitHooks()
class Interface(Generic[_RVALUE], metaclass=keyed_singleton(inst_key=lambda i: (i.__class__, i.key()))):
    '''
    Base class for interfaces that link transforms together.

    Interfaces are automatically linked based on the the output of the key
    method which should be overriden in subclasses.

    The resolve_* methods can be overriden to control the interface value
    that transforms see. 

    The base Interface takes a single value that resolves as itself, with
    a unique key so it'll never link transforms together. This can be used
    to pass values directly into transforms.
    '''
    input_transform: Optional["Transform"]
    output_transforms: list["Transform"]

    def __init__(self, value) -> None:
        self.value = value

    @InitHooks.pre
    def init_transforms(self):
        self.input_transform = None
        self.output_transforms = []
        # Wrapped here since if they are overriden they still
        # must be cached.
        self.resolve = cache(self.resolve)
        self._hash = cache(self._hash)
        self.get_hashsource = cache(self.get_hashsource)

    def get_hashsource(self, ctx):
        '''
        Get a computed hash for this interface based on the hash of its input
        or the hash of its own value if it is a static input.

        Note: Although not decorated, this method is always cached via 
        '''
        if self.input_transform:
            return self.input_transform.get_hashsource(ctx)
        else:
            return self._hash(ctx)
        
    def serialize(self, ctx: "Context") -> Iterable[str]:
        if type(self) is Interface:
            # For some types we can just go ahead and serialize
            if isinstance(self.value, (str, int, float, types.NoneType)):
                yield type(self.value).__name__
                yield str(self.value)
                return
        raise NotImplementedError

    def _hash(self, ctx: "Context"):
        md5 = hashlib.md5(type(self).__name__.encode('utf8'))
        for part in self.serialize(ctx):
            md5.update(part.encode('utf8'))
        return md5.hexdigest()

    def key(self) -> Hashable:
        """
        Returns a key which is used for matching up interfaces.

        @ed.kotarski: Note this is a temporary mechansim that will be replaced later on.
        """
        return id(self)

    def __deepcopy__(self, _memo):
        """
        Interfaces are singletons based on the key that absolutely must not be
        copied.
        """
        return self

    def _bind_transform(self, transform: "Transform", direction: Direction):
        """
        Binds this interface to a transform with direction and name.

        This should not be called by user code. Instead call `bind_inputs` or `bind_outputs` on
        the transform object (which will call this internally).
        """
        if direction.is_input:
            self.output_transforms.append(transform)
            # Add to the transforms flat interfaces
            transform._flat_input_interfaces.append(self)
        else:
            if self.input_transform:
                raise RuntimeError(f"Tried to output interface `{self}` from multiple transforms `{self.input_transform}` and `{transform}`")
            self.input_transform = transform
            # Add to the transforms flat interfaces
            transform._flat_output_interfaces.append(self)

    def resolve_output(self, ctx: "Context") -> _RVALUE:
        """
        Resolve this interface as an output value to pass through to the transform.
        See `resolve` for further details.
        """
        return self.value
    
    def resolve_input(self, ctx: "Context") -> _RVALUE:
        """
        Resolve this interface as an input value to pass through to the transform. 
        See `resolve` for further details.
        """
        return self.value

    def resolve(self, ctx: "Context") -> _RVALUE:
        """
        Resolve this interface to the value that will be passed through to the transform.
        This will internally call:
            - this interfaces `resolve_output` method if this interface is an output
            - this interfaces `resolve_input` method if this interface is an 
              unconnected input.

        Note: If the associated transform uses containers, then the `resolve_container`
              method will be called instead. See `resolve_container` for details.
        """
        if self.input_transform:
            return self.resolve_output(ctx)
        else:
            return self.resolve_input(ctx)

    def resolve_container(self, ctx: "Context", container: Container, direction: Direction) -> _RVALUE:
        """
        Resolve the value for a container, and return the value that should
        appear in the transforms execute method.

        This gives an an opportunity to bind required container paths etc. 
        Usually this is expected to internally call the standard `resolve` 
        method (the default implementation simply returns the value from resolve).
        """
        return self.resolve(ctx)

class MetaInterface(Interface[_RVALUE]):
    '''
    An interface base class that can be used to encapsulate other interfaces
    into this one. For example::

        class DesignInterface(MetaInterface):
        
            def __init__(self, sources: list[FileInterface], 
                               headers: list[FileInterface]) -> None:
                self.sources = sources
                self.headers = headers

            def abstract_resolve(self, fn):
                return ReadonlyNamespace(sources=map(fn, self.sources),
                                         headers=map(fn, self.headers))

    '''
    def __init__(self) -> None:
        raise NotImplementedError

    def _bind_transform(self, *args, **kwargs):
        self.resolve_meta(lambda v: v._bind_transform(*args, **kwargs))

    def resolve(self, ctx) -> _RVALUE:
        return self.resolve_meta(lambda v: v.resolve(ctx))
    
    def resolve_container(self, ctx, container, direction: Direction) -> _RVALUE:
        return self.resolve_meta(lambda v: v.resolve_container(ctx, container, direction))
    
    def serialize(self, ctx) -> Iterable[str]:
        raise RuntimeError('Metainterfaces should not be being serialized (should be transparent)')
    
    @staticmethod
    def map(fn, iterable):
        return list(map(fn, iterable))

    def resolve_meta(self, fn: Callable[[Interface], Any]) -> Any:
        '''
        This is expected to return the resolved structure where the resolver `fn`
        argument will take an interface and return the correct resolved value
        based on context. 

        Note: Lazy iteration using map (or similar) will not work since we rely
              on all interfaces being processed in stages. For convenience a
              `map` method which isn't lazy is provided on this class. 
        '''
        raise NotImplementedError

class ArgsInterface(Interface[str]):
    'Takes a list of arguments and maps them into the container'
    def resolve_container(self, ctx: Context, container: Container, direction: Direction) -> Sequence[str]:
        return shlex.join(container.bind_and_map_args(ctx, args=self.resolve(ctx)))

class ListInterface(MetaInterface):
    'List of other interfaces'
    def __init__(self, items: Iterable[Interface]) -> None:
        self.items = list(items)

    def resolve_meta(self, fn):
        return self.map(fn, self.items)
    
class DictInterface(MetaInterface):
    'Dict of other interfaces'
    def __init__(self, mapping: dict[str, Interface] | None = None, **interfaces: Interface):
        self.interfaces = {**(mapping or {}), **interfaces}

    def resolve_meta(self, fn):
        return ReadonlyNamespace(**{k: fn(v) for k, v in self.interfaces.items()})

class FileInterface(Interface[Path]):
    def __init__(self, value: str | Path) -> None:
        self.value = Path(value)

    def resolve_container(self, ctx: "Context", container: Container, direction: Direction):
        value = self.resolve(ctx)
        container_path = ctx.map_to_container(value)
        readonly = direction.is_input
        container.bind(value.parent, container_path.parent, readonly=readonly)
        return container_path
    
    def serialize(self, ctx: "Context") -> Iterable[str]:
        yield Cache.hash_content(self.resolve(ctx))

    def to_content_interface(self):
        return FileContentInterface(self)

class SplitFileInterface(FileInterface):
    """
    File interface where input and output path resolve differently, but with a common key
    """
    def __init__(self, input_path: str | Path, output_path: str | Path, key: Hashable) -> None:
        self._input_path = Path(input_path)
        self._output_path = Path(output_path)
        self._key = key

    def key(self):
        return self._key
    
    def resolve_output(self, ctx: "Context"):
        return self._output_path
    
    def resolve_input(self, ctx: "Context"):
        return self._input_path
    
class FileContentInterface(MetaInterface):
    def __init__(self, path: FileInterface | str | Path):
        self._file = path if isinstance(path, FileInterface) else FileInterface(path)

    def resolve_meta(self, fn):
        return fn(self._file)

    def resolve(self, ctx) -> Any:
        path = super().resolve(ctx)
        with path.open(encoding='utf8') as f:
            return f.read()
    
    def resolve_container(self, ctx, container, direction: Direction) -> Any:
        return self.resolve(ctx)

class TemplateInterface(MetaInterface):
    def __init__(self, text: Interface[str], fields: DictInterface):
        self._text = text
        self._fields = fields
    
    def resolve_meta(self, fn):
        return fn(self._text), fn(self._fields)
    
    def resolve(self, ctx) -> Any:
        text, fields = super().resolve(ctx)
        breakpoint()
        return text.format(**fields.ns)
    
    def resolve_container(self, ctx, container, direction: Direction) -> Any:
        text, fields = super().resolve_container(ctx, container, direction)
        return text.format(**fields.ns)
