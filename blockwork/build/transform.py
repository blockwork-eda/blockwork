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

import functools
from typing import TYPE_CHECKING, Any, Iterable

from ..common.inithooks import InitHooks
from ..build.interface import Interface, Direction, Pipe
if TYPE_CHECKING:
    from ..tools.tool import Version, Tool, Invocation
    from ..context import Context
from ..common.complexnamespaces import ReadonlyNamespace

@InitHooks()
class Transform:
    """
    Base class for transforms.
    """
    tools: list[type["Tool"]] = []
    # Interfaces represents the "pretty" view of interfaces
    # with meta-interfaces visible for hierarchical access
    _interfaces: dict[str, tuple[Direction, Pipe, Interface]]
    # Flat interfaces represent the raw interfaces with those
    # nested in meta-interfaces unrolled.
    _flat_input_interfaces: list[Interface]
    _flat_output_interfaces: list[Interface]

    @InitHooks.pre
    def init_interfaces(self):
        self._interfaces = {}
        self._flat_input_interfaces = []
        self._flat_output_interfaces = []

    @property
    @functools.lru_cache()
    def output_interfaces(self):
        interfaces: dict[str, Any] = {}
        for name, (direction, _pipe, interface) in self._interfaces.items():
            if direction.is_output:
                interfaces[name] = interface
        return ReadonlyNamespace(**interfaces)

    @property
    @functools.lru_cache()
    def input_interfaces(self):
        interfaces: dict[str, Any] = {}
        for name, (direction, _pipe, interface) in self._interfaces.items():
            if direction.is_input:
                interfaces[name] = interface
        return ReadonlyNamespace(**interfaces)

    @property
    @functools.lru_cache()
    def interfaces(self):
        interfaces: dict[str, Any] = {}
        for name, (direction, _pipe, interface) in self._interfaces.items():
            interfaces[name] = interface
        return ReadonlyNamespace(**interfaces)
    
    @property
    @functools.lru_cache()
    def real_input_interfaces(self):
        return self._flat_input_interfaces
    
    @property
    @functools.lru_cache()
    def real_output_interfaces(self):
        return self._flat_output_interfaces

    def id(self):
        """
        Unique ID for the transform. This is currently just used for uniquifying
        transform output paths.

        @ed.kotarski: Ideally this should be some hash of the values so we get the
                      same value each time.
        """
        return f"{self.__class__.__name__}_{id(self)}"

    def _bind_interfaces(self, _direction: Direction, _pipe: Pipe, **kwargs: Interface):
        for name, interface in kwargs.items():
            # Don't allow the same name to be bound twice
            # Though a single call may bind that name to an array of interfaces.
            if name in self._interfaces:
                raise RuntimeError(f"Interface already bound with name `{name}`.")

            self._interfaces[name] = (_direction, _pipe, interface)
            interface._bind_transform(self, _direction)

    def bind_outputs(self, **interface: Interface):
        """
        Attach interfaces to this transform by name as outputs. The 
        supplied names can be used to refer the interfaces in `execute`.

        For each name, either a single interfaces or an array of interfaces
        may be supplied. Resolved values will be passed through to the execute
        method accordingly as a single value or array of values.
        """
        return self._bind_interfaces(Direction.OUTPUT, Pipe.FLOW, **interface)
    
    def bind_host_outputs(self, **interface: Interface):
        """
        Attach interfaces to this transform by name as outputs. The 
        supplied names can be used to refer the interfaces in `execute`.

        Host outputs are special in that they resolve as paths on 
        the host within the execute method. This is sometimes useful if
        an output file needs to be created from the execute method itself 
        rather than from within a container.
        """
        return self._bind_interfaces(Direction.OUTPUT, Pipe.HOST, **interface)

    def bind_inputs(self, **interface: Interface):
        """
        Attach interfaces to this transform by name as inputs. The 
        supplied names can be used to refer the interfaces in `execute`.

        For each name, either a single interfaces or an array of interfaces
        may be supplied. Resolved values will be passed through to the execute
        method accordingly as a single value or array of values.
        """
        return self._bind_interfaces(Direction.INPUT, Pipe.FLOW, **interface)

    def bind_host_inputs(self, **interface: Interface):
        """
        Attach interfaces to this transform by name as inputs. The 
        supplied names can be used to refer the interfaces in `execute`.

        Host inputs are special in that they resolve as paths on 
        the host within the execute method. This is sometimes useful for
        transforms which execute on the host itself - or need to log host
        paths.
        """
        return self._bind_interfaces(Direction.INPUT, Pipe.HOST, **interface)

    def run(self, ctx: "Context"):
        """Run the transform in a container."""
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
        for name, (direction, pipe, interface) in self._interfaces.items():
            if pipe is Pipe.HOST:
                interface_values[name] = interface.resolve(ctx)
            else:
                interface_values[name] = interface.resolve_container(ctx, container, direction)

        tools = ReadonlyNamespace(**tool_instances)
        iface = ReadonlyNamespace(**interface_values)

        for invocation in self.execute(ctx, tools, iface):
            if exit_code:=container.invoke(ctx, invocation) != 0:
                raise RuntimeError(f"Invocation `{invocation}` failed with exit code `{exit_code}`.")

    def execute(self,
             ctx  : "Context",
             tools: ReadonlyNamespace["Version"],
             iface: ReadonlyNamespace[Any]) -> Iterable["Invocation"]:
        """
        Execute method to be implemented in subclasses.
        """
        raise NotImplementedError
