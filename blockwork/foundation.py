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

from .containers import Container
from .tools import Tool

class FoundationError(Exception):
    pass

class Foundation(Container):
    """ Standard baseline container for Blockwork """

    def __init__(self, **kwargs) -> None:
        super().__init__(image="docker.io/library/rockylinux:9.1",
                         workdir=Path("/bw/scratch"),
                         **kwargs)
        cwd = Path.cwd()
        self.bind_readonly(cwd / "bw" / "input")
        self.bind(cwd / "bw" / "output")
        self.bind(cwd / "bw" / "scratch")
        self.set_env("PATH", "usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
        self.__tools     = {}
        self.__tool_root = Path("/") / "bw" / "tools"

    def add_tool(self, tool : Tool) -> None:
        if tool.id in self.__tools:
            raise FoundationError(f"Tool already registered for ID '{tool.id}'")
        self.__tools[tool.id] = tool
        full_location = self.__tool_root / tool.path_chunk
        self.bind_readonly(tool.location, full_location)
        if isinstance(tool.env, dict):
            self.overlay_env(tool.env, strict=True)
        for path in tool.paths:
            c_path = path
            # If a subpath of 'TOOL_ROOT', then make it relative to the tool's
            # base directory
            if Tool.TOOL_ROOT in path.parents:
                c_path = full_location / path.relative_to(Tool.TOOL_ROOT)
            self.append_env_path("PATH", c_path.as_posix())
