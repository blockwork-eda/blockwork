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

from .containers import Container
from .context import Context, ContextContainerPathError
from .tools import Invocation, Tool

cntr_dir = Path(__file__).absolute().parent / "containerfiles"


class FoundationError(Exception):
    pass


class Foundation(Container):
    """Standard baseline container for Blockwork"""

    def __init__(self, context: Context, **kwargs) -> None:
        super().__init__(
            context,
            image=f"foundation_{context.host_architecture}_{context.host_root_hash}",
            definition=cntr_dir / "foundation" / f"Containerfile_{context.host_architecture}",
            workdir=context.container_root,
            **kwargs,
        )
        self.__tools: dict[str, Tool] = {}
        self.bind(self.context.host_scratch, self.context.container_scratch)
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

    def add_input(self, path: Path, name: str | None = None) -> None:
        self.bind_readonly(path, Path("/input") / (name or path.name))

    def add_tool(self, tool: type[Tool] | Tool, readonly: bool = True) -> None:
        # If class has been provided, create an instance
        if not isinstance(tool, Tool):
            if not issubclass(tool, Tool):
                raise Foundation("Tool definitions must inherit from the Tool class")
            tool = tool()
        tool_ver = tool.version
        # Check tool is not already registered
        if tool.base_id in self.__tools:
            if self.__tools[tool.base_id].version is tool_ver:
                return
            raise FoundationError(f"Tool already registered for ID '{tool.base_id}'")
        # Load any requirements
        for req in tool_ver.requires:
            if req.tool.base_id in self.__tools:
                if (rv := req.tool.version) != (xv := self.__tools[req.tool.base_id].version):
                    raise FoundationError(
                        f"Version clash for tool '{req.tool.base_id}': {rv} != {xv}"
                    )
            else:
                self.add_tool(req.tool, readonly=readonly)
        # Register tool and bind in the base folder
        self.__tools[tool.base_id] = tool
        host_loc = tool.get_host_path(self.context)
        cntr_loc = tool.get_container_path(self.context)
        logging.debug(f"Binding '{host_loc}' to '{cntr_loc}' {readonly=}")
        self.bind(host_loc, cntr_loc, readonly=readonly)
        # Overlay the environment, expanding any paths
        if isinstance(tool_ver.env, dict):
            env = {}
            for key, value in tool_ver.env.items():
                if isinstance(value, Path):
                    env[key] = tool.get_container_path(self.context, value).as_posix()
                else:
                    env[key] = value
            self.overlay_env(env, strict=True)
        # Append to $PATH
        for key, paths in tool_ver.paths.items():
            for segment in paths:
                if isinstance(segment, Path):
                    segment = tool.get_container_path(self.context, segment).as_posix()
                self.prepend_env_path(key, segment)

    def invoke(self, context: Context, invocation: Invocation, readonly: bool = True) -> int:
        """
        Evaluate a tool invocation by binding the required tools and setting up
        the environment as per the request.

        :param context:     Context in which invocation is launched
        :param invocation:  An Invocation object
        :param readonly:    Whether to bind tools read only (defaults to True)
        :returns:           Exit code from the executed process
        """
        # Build container if it doesn't already exist
        if not self.exists:
            self.build()

        # Add the tool into the container (also adds dependencies)
        self.add_tool(invocation.tool, readonly=readonly)
        # Convert remaining paths
        args = [a.as_posix() if isinstance(a, Path) else a for a in invocation.args]

        # Bind files and directories
        self.bind_many(context, binds=invocation.binds, readonly=False)
        self.bind_many(context, binds=invocation.ro_binds, readonly=True)

        # Resolve the binary
        command = invocation.execute
        if isinstance(command, Path):
            command = invocation.tool.get_container_path(self.context, command).as_posix()
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
        return self.launch(
            command,
            *args,
            workdir=invocation.workdir or context.container_root,
            interactive=invocation.interactive,
            display=invocation.display,
            show_detach=False,
            env=invocation.env,
            path=invocation.path,
            stdout=invocation.stdout,
            stderr=invocation.stderr,
        )
