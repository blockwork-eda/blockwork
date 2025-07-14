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

import dataclasses
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TextIO


class ContainerError(Exception):
    pass


class ContainerBindError(ContainerError):
    def __init__(self, host, container, readonly, bind):
        e_str = (
            f"Cannot bind {host} to {container} "
            f"(as {'readonly' if readonly else 'writable'}) "
            "due to collision with existing "
            f"bind {bind.host_path} to {bind.container_path} "
            f"(as {'readonly' if bind.readonly else 'writable'})"
        )
        super().__init__(e_str)


@dataclasses.dataclass
class ContainerBind:
    """Describes a bind to apply to the container"""

    host_path: Path
    container_path: Path
    readonly: bool

    def as_configuration(self) -> dict[str, str | bool]:
        return {
            "type": "bind",
            "source": self.host_path.as_posix(),
            "target": self.container_path.as_posix(),
            "readonly": self.readonly,
        }


@dataclasses.dataclass(frozen=True, kw_only=True)
class ContainerResult:
    exit_code: int
    interacted: bool


class ContainerBase(ABC):
    @property
    @abstractmethod
    def id(self):
        """Return the ID of the container"""
        ...

    @property
    @abstractmethod
    def exists(self) -> bool:
        """Determine whether the container image is already built"""
        ...

    @abstractmethod
    def build(self) -> None:
        """Build the container image"""
        ...

    @abstractmethod
    def bind(
        self,
        host: Path,
        container: Path | None = None,
        readonly: bool = False,
        mkdir: bool = False,
    ) -> Path:
        """
        Bind a folder with read-write access from the host into the container at
        a given path, if the container path is not given then it uses the final
        path component and places it under the root directory.

        :param host:        Path on the host
        :param container:   Optional path within the container
        :param readonly:    Whether to bind as readonly (default: False)
        :param mkdir:       Whether to create the directory first
        :returns:           Mapped path within the container
        """
        ...

    @abstractmethod
    def set_env(self, key: str, value: str) -> None:
        """
        Set an environment variable within the container.

        :param key:     Environment variable name
        :param value:   Value of the environment variable
        """
        ...

    @abstractmethod
    def append_env_path(self, key: str, value: str) -> None:
        """
        Append to a path variable within the environment

        :param key:     Environment variable name
        :param value:   Section to append
        """
        ...

    @abstractmethod
    def prepend_env_path(self, key: str, value: str) -> None:
        """
        Prepend to a path variable within the environment

        :param key:     Environment variable name
        :param value:   Section to prepend
        """
        ...

    @abstractmethod
    def has_env(self, key: str) -> bool:
        """
        Check if an environment variable has been set for the container.

        :param key: Environment variable name
        :returns:   True if set, False otherwise
        """
        ...

    @abstractmethod
    def get_env(self, key: str) -> str | None:
        """
        Get the value of an environment variable within the container.

        :param key: Environment variable name
        :returns:   Value of the environment variable or None if not found
        """
        ...

    @abstractmethod
    def overlay_env(self, env: dict[str, str], strict: bool = False) -> None:
        """
        Overlay a set of environment variables onto the current set, if strict
        is set then any collision with an existing key will be flagged.

        :param env:     Environment variables to overlay
        :param strict:  Whether to raise an error if key already exists
        """
        ...

    @abstractmethod
    def launch(
        self,
        *command: str,
        workdir: Path | None = None,
        interactive: bool = False,
        display: bool = False,
        show_detach: bool = True,
        clear: bool = False,
        env: dict[str, str] | None = None,
        path: dict[str, list[Path]] | None = None,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> ContainerResult:
        """
        Launch a task within the container either interactively (STDIN and STDOUT
        streamed from/to the console) or non-interactively (STDOUT is captured).
        Blocks until command execution completes.

        :param *command:    The command to execute
        :param workdir:     Working directory (defaults to /)
        :param interactive: Whether to interactively forward STDIN and STDOUT
        :param display:     Expose the host's DISPLAY variable to the container
        :param show_detach: Whether to show the detach key message
        :param clear:       Whether to clear the screen after the command completes
        :param env:         Additional environment variables
        :param path:        Additional path variables to extend
        :param stdout:      Replacement file to send stdout to
        :param stderr:      Replacement file to send stderr to
        :returns:           Exit code of the executed process
        """
        ...

    @abstractmethod
    def shell(
        self,
        command: tuple[str] = ("/bin/bash",),
        workdir: Path | None = None,
        show_detach: bool = False,
    ) -> int:
        """
        Open an interactive shell in the container. This is similar to launch,
        but always enables and interactive shell and forwards the X11 display.

        :param command:     Command to execute (defaults to /bin/bash)
        :param workdir:     Working directory (defaults to /)
        :param show_detach: Whether to show the detach key message
        :returns:           Exit code from the executed process
        """
        ...
