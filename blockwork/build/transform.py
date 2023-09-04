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

from typing import TYPE_CHECKING, Any, Iterable
from ..build.interface import Interface, InterfaceDirection
if TYPE_CHECKING:
    from ..tools.tool import Version, Tool, Invocation
    from ..context import Context
from ..common.complexnamespaces import ReadonlyNamespace

class Transform:
    """
    Base class for transforms.
    """
    tools: list[type["Tool"]] = []

    def __init__(self):
        self.interfaces: list[Interface] = []
        self.interfaces_by_name: dict[str, Interface | list[Interface]] = {}

    def id(self):
        """
        Unique ID for the transform. This is currently just used for uniquifying
        transform output paths.

        @ed.kotarski: Ideally this should be some hash of the values so we get the
                      same value each time.
        """
        return f"{self.__class__.__name__}_{id(self)}"

    def _bind_interfaces(self, direction: InterfaceDirection, **kwargs: Interface | Iterable[Interface]):
        for name, interfaces in kwargs.items():
            # Don't allow the same name to be bound twice
            # Though a single call may bind that name to an array of interfaces.
            if name in self.interfaces_by_name:
                raise RuntimeError(f"Interface already bound with name `{name}`.")

            if isinstance(interfaces, Interface):
                self.interfaces_by_name[name] = interfaces
                interfaces = [interfaces]
            else:
                interfaces = list(interfaces)
                self.interfaces_by_name[name] = interfaces

            # Establish two-way link from transform to interface and interface to transfor,
            for interface in interfaces:
                self.interfaces.append(interface)
                interface._bind_transform(self, direction, name)

    def bind_outputs(self, **interfaces: Interface | Iterable[Interface]):
        """
        Attach interfaces to this transform by name as outputs. The 
        supplied names can be used to refer the interfaces in `execute`.

        For each name, either a single interfaces or an array of interfaces
        may be supplied. Resolved values will be passed through to the execute
        method accordingly as a single value or array of values.
        """
        return self._bind_interfaces(InterfaceDirection.Output, **interfaces)

    def bind_inputs(self, **interfaces: Interface | Iterable[Interface]):
        """
        Attach interfaces to this transform by name as inputs. The 
        supplied names can be used to refer the interfaces in `execute`.

        For each name, either a single interfaces or an array of interfaces
        may be supplied. Resolved values will be passed through to the execute
        method accordingly as a single value or array of values.
        """
        return self._bind_interfaces(InterfaceDirection.Input, **interfaces)

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
        for name, interfaces in self.interfaces_by_name.items():
            if isinstance(interfaces, Interface):
                value = interfaces.bind_container(ctx, container, interfaces.resolve(ctx))
            else:
                value = [interface.bind_container(ctx, container, interface.resolve(ctx)) for interface in interfaces]
            interface_values[name] = value

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
