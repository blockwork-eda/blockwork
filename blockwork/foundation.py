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

import logging
from pathlib import Path
from typing import Optional, Type, Union

from .containers import Container
from .context import Context, ContextContainerPathError
from .tools import Invocation, Tool, Version

class FoundationError(Exception):
    pass

class Foundation(Container):
    """ Standard baseline container for Blockwork """

    def __init__(self, context : Context, **kwargs) -> None:
        super().__init__(image=f"foundation_{context.host_architecture}",
                         workdir=context.container_root,
                         **kwargs)
        self.__context = context
        self.__tools = {}
        self.bind(self.__context.host_scratch, self.__context.container_scratch)
        # Ensure various standard $PATHs are present
        self.append_env_path("PATH", "/usr/local/sbin")
        self.append_env_path("PATH", "/usr/local/bin")
        self.append_env_path("PATH", "/usr/sbin")
        self.append_env_path("PATH", "/usr/bin")
        self.append_env_path("PATH", "/sbin")
        self.append_env_path("PATH", "/bin")
        # Provide standard paths as environment variables
        self.set_env("BW_ROOT", context.container_root.as_posix())
        self.set_env("BW_SCRATCH", context.container_scratch.as_posix())
        self.set_env("BW_TOOLS", context.container_tools.as_posix())
        self.set_env("BW_PROJECT", context.config.project)

    def add_input(self, path : Path, name : Optional[str] = None) -> None:
        self.bind_readonly(path, Path("/input") / (name or path.name))

    def add_tool(self, tool : Union[Type[Tool], Tool, Version], readonly : bool = True) -> None:
        # If class has been provided, create an instance
        if not isinstance(tool, (Tool, Version)):
            if not issubclass(tool, Tool):
                raise Foundation("Tool definitions must inherit from the Tool class")
            tool = tool()
        # Grab the default
        tool_ver = tool if isinstance(tool, Version) else tool.default
        tool     = tool_ver.tool
        # Check tool is not already registered
        if tool.base_id in self.__tools:
            if self.__tools[tool.base_id] is tool_ver:
                return
            raise FoundationError(f"Tool already registered for ID '{tool.base_id}'")
        # Load any requirements
        for req in tool_ver.requires:
            req_ver = req.tool().get_version(req.version)
            if req_ver is None:
                raise FoundationError(f"Could not resolve version {req.version} for {req.tool.base_id}")
            elif req.tool.base_id in self.__tools:
                if (rv := req_ver.version) != (xv := self.__tools[req.base_id].version):
                    raise FoundationError(f"Version clash for tool '{req.tool.base_id}': {rv} != {xv}")
            else:
                self.add_tool(req_ver, readonly=readonly)
        # Register tool and bind in the base folder
        self.__tools[tool.base_id] = tool_ver
        host_loc = tool_ver.get_host_path(self.__context)
        cntr_loc = tool_ver.get_container_path(self.__context)
        logging.debug(f"Binding '{host_loc}' to '{cntr_loc}' {readonly=}")
        self.bind(host_loc, cntr_loc, readonly=readonly)
        # Overlay the environment, expanding any paths
        if isinstance(tool_ver.env, dict):
            env = {}
            for key, value in tool_ver.env.items():
                if isinstance(value, Path):
                    env[key] = tool_ver.get_container_path(self.__context, value).as_posix()
                else:
                    env[key] = value
            self.overlay_env(env, strict=True)
        # Append to $PATH
        for key, paths in tool_ver.paths.items():
            for path in paths:
                self.prepend_env_path(key, tool_ver.get_container_path(self.__context, path).as_posix())

    def invoke(self,
               context : Context,
               invocation : Invocation,
               readonly : bool = True) -> int:
        """
        Evaluate a tool invocation by binding the required tools and setting up
        the environment as per the request.

        :param context:     Context in which invocation is launched
        :param invocation:  An Invocation object
        :param readonly:    Whether to bind tools read only (defaults to True)
        :returns:           Exit code from the executed process
        """
        # Add the tool into the container (also adds dependencies)
        self.add_tool(invocation.version, readonly=readonly)

        # Bind files and folders to host and remap path args
        args = invocation.bind_and_map(context=context, container=self)
        # Resolve the binary
        command = invocation.execute
        if isinstance(command, Path):
            command = invocation.version.get_container_path(self.__context, command).as_posix()
        # Determine and create (if required) the working directory
        c_workdir = invocation.workdir or context.container_root
        try:
            h_workdir = context.map_to_host(c_workdir)
            if not h_workdir.exists():
                h_workdir.mkdir(parents=True, exist_ok=True)
        except ContextContainerPathError:
            pass
        # Launch
        logging.debug(f"Launching in container: {command} {' '.join(args)}")
        return self.launch(command,
                           *args,
                           workdir=invocation.workdir or context.container_root,
                           interactive=invocation.interactive,
                           display=invocation.display,
                           show_detach=False,
                           env=invocation.env,
                           path=invocation.path)
