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
from pathlib import Path
import sys
from typing import Generic, Hashable, Iterable, Self, TypeVar, TYPE_CHECKING

from ..containers.container import Container

if TYPE_CHECKING:
    from ..context import Context
    from .transform import Transform


class InterfaceError(Exception): ...

class InterfaceDirection(Enum):
    Input = auto()
    Output = auto()

# The resolved value type
_RVALUE = TypeVar("_RVALUE")
# The container value type (passed into execute)
if sys.version_info >= (3, 12): # (PEP 696)
    # Most of the time the type won't change when binding to container
    _CVALUE = TypeVar("_CVALUE", default=_RVALUE)
else:
    _CVALUE = TypeVar("_CVALUE")

class Interface(Generic[_RVALUE, _CVALUE]):
    transform: "Transform"
    name: str
    direction: InterfaceDirection
    connections: list[Self]

    def __init__(self):
        raise NotImplementedError
    
    def keys(self) -> Iterable[Hashable]:
        """
        Yields keys which are used for matching up interfaces.

        @ed.kotarski: Note this is a temporary mechansim that will be replaced later on.
        """
        raise NotImplementedError

    def _bind_transform(self, transform: "Transform", direction: InterfaceDirection, name: str):
        """
        Binds this interface to a transform with direction and name.

        This should not be called by user code. Instead call `bind_inputs` or `bind_outputs` on
        the transform object (which will call this internally).
        """
        self.transform = transform
        self.direction = direction
        self.name = name
        self.connections = []

    def connect(self, other: Self):
        """
        Connect this interface to another.
        """
        if other.direction == self.direction:
            raise RuntimeError(f"Tried to connect two interfaces with same direction `{self}` and `{other}`")
        i, o = (self, other) if self.direction is InterfaceDirection.Input else (other, self)
        if len(i.connections) != 0:
            raise RuntimeError(f"Tried to connect input interface `{i}` to multiple outputs `{i.connections[0]}` and `{o}`")
        i.connections.append(o)
        o.connections.append(i)

    def resolve_output(self, ctx: "Context") -> _RVALUE:
        """
        Resolve this interface as an output value to pass through to the transform.
        See `resolve` for further details.
        """
        raise NotImplementedError
    
    def resolve_input(self, ctx: "Context") -> _RVALUE:
        """
        Resolve this interface as an input value to pass through to the transform. 
        See `resolve` for further details.
        """
        raise InterfaceError(f"Interface {self} has no connections and has no way to resolve itself as an input!")
    
    def resolve(self, ctx: "Context") -> _RVALUE:
        """
        Resolve this interface to the value that will be passed through to the transform.
        This will internally call:
            - this interfaces `resolve_output` method if this interface is an output
            - the connected interfaces `resolve_output` method if this interface is
              a connected input.
            - this interfaces `resolve_input` method if this interface is an 
              unconnected input.

        Note: If the associated transform uses containers, then the `bind_container`
              method has another chance to "resolve" the output of this method to the
              value that will be seen in the `transform.execute` method.
        """
        if self.direction is InterfaceDirection.Output:
            return self.resolve_output(ctx)
        if self.connections:
            return self.connections[0].resolve_output(ctx)
        else:
            return self.resolve_input(ctx)

    @classmethod
    def bind_container(cls, ctx: "Context",  container: Container, value: _RVALUE) -> _CVALUE:
        """
        Bind this interface into a transform container, and return the value
        that should appear in the transforms execute method.
        """
        raise NotImplementedError

    def __repr__(self):
        if not hasattr(self, 'transform'):
            return super().__repr__()
        return f"<{self.direction.name}:{self.__class__.__name__}:`{self.name}`>"


class FileInterface(Interface[Path, Path]):
    def bind_container(self, ctx: "Context", container: Container, value: Path):
        container_path = ctx.map_to_container(value)
        readonly = self.direction is InterfaceDirection.Input
        container.bind(value.parent, container_path.parent, readonly=readonly)
        return container_path
