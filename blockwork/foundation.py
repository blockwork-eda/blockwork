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

from pathlib import Path
from typing import Optional, Type, Union

from .containers import Container
from .context import Context
from .tools import Invocation, Tool, Version

class FoundationError(Exception):
    pass

class Foundation(Container):
    """ Standard baseline container for Blockwork """

    def __init__(self, **kwargs) -> None:
        super().__init__(image="foundation", workdir=Path("/bw/scratch"), **kwargs)
        cwd = Path.cwd()
        # self.bind_readonly(cwd / "bw" / "input")
        self.bind(cwd / "bw" / "output")
        self.bind(cwd / "bw" / "scratch")
        self.set_env("PATH", "usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        self.__tools     = {}
        self.__tool_root = Path("/") / "bw" / "tools"

    def add_input(self, path : Path, name : Optional[str] = None) -> None:
        self.bind_readonly(path, Path("/bw/input") / (name or path.name))

    def get_tool_path(self, version : Version, path : Path) -> Path:
        """
        Map a path relative to a tool root to the absolute path within the container.
        :param version: Tool version
        :param path:    Path relative to TOOL_ROOT
        :returns:       Absolute path
        """
        if Tool.TOOL_ROOT is path or Tool.TOOL_ROOT in path.parents:
            full_loc = self.__tool_root / version.path_chunk
            return full_loc / path.relative_to(Tool.TOOL_ROOT)
        else:
            return path

    def add_tool(self, tool : Union[Type[Tool], Tool, Version]) -> None:
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
            req_ver = req.tool().get(req.version)
            if req_ver is None:
                raise FoundationError(f"Could not resolve version {req.version} for {req.tool.base_id}")
            elif req.tool.base_id in self.__tools:
                if (rv := req_ver.version) != (xv := self.__tools[req.base_id].version):
                    raise FoundationError(f"Version clash for tool '{req.tool.base_id}': {rv} != {xv}")
            else:
                self.add_tool(req_ver)
        # Register tool and bind in the base folder
        self.__tools[tool.base_id] = tool_ver
        full_location = self.__tool_root / tool_ver.path_chunk
        self.bind_readonly(tool_ver.location, full_location)
        # Overlay the environment, expanding any paths
        if isinstance(tool_ver.env, dict):
            env = {}
            for key, value in tool_ver.env.items():
                if isinstance(value, Path):
                    env[key] = self.get_tool_path(tool_ver, value).as_posix()
                else:
                    env[key] = value
            self.overlay_env(env, strict=True)
        # Append to $PATH
        for key, paths in tool_ver.paths.items():
            for path in paths:
                self.prepend_env_path(key, self.get_tool_path(tool_ver, path).as_posix())

    def invoke(self, context : Context, invocation : Invocation) -> None:
        """
        Evaluate a tool invocation by binding the required tools and setting up
        the environment as per the request.

        :param context:     Context in which invocation is launched
        :param invocation:  An Invocation object
        """
        # Add the tool into the container (also adds dependencies)
        self.add_tool(invocation.version)
        # Bind requested files/folders to relative paths
        bound = []
        for h_path in invocation.binds:
            h_path : Path = h_path.absolute()
            if not h_path.is_relative_to(context.host_root):
                raise FoundationError(f"Path {h_path} is not within the project "
                                      f"working directory {context.host_root}")
            c_path = context.container_root / h_path.relative_to(context.host_root)
            self.bind(h_path, c_path, False)
            bound.append(h_path)
        # Process path arguments to make them relative
        args = []
        for arg in invocation.args:
            # If this is a string, but appears to be a relative path, convert it
            if isinstance(arg, str) and (as_path := (Path.cwd() / arg)).exists():
                arg = as_path
            # For path arguments, check they will be accessible in the container
            if isinstance(arg, Path):
                arg = arg.absolute()
                if not arg.is_relative_to(context.host_root):
                    raise FoundationError(f"Path {arg} is not within the project "
                                          f"working directory {context.host_root}")
                # Convert to an absolute path within the container
                c_path = context.container_root / arg.relative_to(context.host_root)
                args.append(c_path.as_posix())
                # If the path is not bound, bind it in
                if not any(arg.is_relative_to(x) for x in bound):
                    self.bind(arg, c_path, False)
                    bound.append(arg)
            # Otherwise, just pass through the argument
            else:
                args.append(arg)
        # Resolve the binary
        command = self.get_tool_path(invocation.version, invocation.execute).as_posix()
        # Launch
        self.launch(command,
                    *args,
                    workdir=invocation.workdir or context.container_root,
                    interactive=invocation.interactive,
                    display=invocation.display,
                    show_detach=False)
