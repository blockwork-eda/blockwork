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
from .tools import Tool, Version

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
                    if Tool.TOOL_ROOT is value or Tool.TOOL_ROOT in value.parents:
                        value = full_location / value.relative_to(Tool.TOOL_ROOT)
                    env[key] = value.as_posix()
                else:
                    env[key] = value
            self.overlay_env(env, strict=True)
        # Append to $PATH
        for key, paths in tool_ver.paths.items():
            for path in paths:
                c_path = path
                # If a subpath of 'TOOL_ROOT', then make it relative to the
                # tool's base directory
                if Tool.TOOL_ROOT is path or Tool.TOOL_ROOT in path.parents:
                    c_path = full_location / path.relative_to(Tool.TOOL_ROOT)
                self.prepend_env_path(key, c_path.as_posix())
