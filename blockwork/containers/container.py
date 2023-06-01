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

import atexit
import dataclasses
import itertools
import os
from pathlib import Path
from threading import Event
from typing import Dict, List, Optional, Tuple, Union

import docker

from .client import Podman
from .common import read_stream, write_stream


class ContainerError(Exception):
    pass


@dataclasses.dataclass
class ContainerBind:
    """ Describes a bind to apply to the container """
    host_path      : Path
    container_path : Path
    readonly       : bool

    def as_configuration(self) -> Dict[str, Union[str, bool]]:
        return {
            "type"    : "bind",
            "source"  : self.host_path.as_posix(),
            "target"  : self.container_path.as_posix(),
            "readonly": self.readonly
        }


class Container:
    """
    Wrapper around Podman container launch and management that can be extended
    to support specific tools and workflows.

    :param image:       Container image to launch with
    :param workdir:     Default working directory (default: /)
    :param environment: Environment defaults to expose (empty by default)
    """

    LAUNCH_ID = itertools.count()

    def __init__(self,
                 image       : str,
                 workdir     : Path = Path("/"),
                 environment : Optional[Dict[str, str]] = None) -> None:
        # Store initialisation parameters
        self.image = image
        self.workdir = workdir
        # Configuration
        type_name = type(self).__name__.lower()
        issued_id = next(Container.LAUNCH_ID)
        self.__id : str = f"bw_{os.getpid()}_{type_name}_{issued_id}"
        self.__binds : List[ContainerBind] = []
        self.__environment : Dict[str, str] = {}
        if isinstance(environment, dict):
            self.__environment.update(environment)
        # State
        self.__container : Union[docker.Container, None] = None

    @property
    def id(self):
        """ Return the ID of the container """
        return self.__id

    def bind(self,
             host      : Path,
             container : Optional[Path] = None,
             readonly  : bool           = False) -> Path:
        """
        Bind a folder with read-write access from the host into the container at
        a given path, if the container path is not given then it uses the final
        path component and places it under the '/bw' directory.

        :param host:        Path on the host
        :param container:   Optional path within the container
        :param readonly:    Whether to bind as readonly (default: False)
        :returns:           Mapped path within the container
        """
        if self.__container:
            raise ContainerError("Binds must be applied before launch")
        if not container:
            container = Path("/bw") / host.name
        self.__binds.append(ContainerBind(host, container, readonly))
        return container

    def bind_readonly(self, host : Path, container : Optional[Path] = None) -> Path:
        """
        Bind a folder with read-only access from the host into the container at
        a given path, if the container path is not given then it uses the final
        path component and places it under the '/bw' directory.

        :param host:        Path on the host
        :param container:   Optional path within the container
        :returns:           Mapped path within the container
        """
        return self.bind(host, container, readonly=True)

    def set_env(self, key : str, value : str) -> None:
        """
        Set an environment variable within the container.

        :param key:     Environment variable name
        :param value:   Value of the environment variable
        """
        if self.__container:
            raise ContainerError("Environment must be set before launch")
        self.__environment[str(key)] = str(value)

    def append_env_path(self, key : str, value : str) -> None:
        """
        Append to a path variable within the environment

        :param key:     Environment variable name
        :param value:   Section to append
        """
        if key in self.__environment:
            self.__environment[key] += f":{value.strip()}"
        else:
            self.__environment[key] = str(value).strip()

    def prepend_env_path(self, key : str, value : str) -> None:
        """
        Prepend to a path variable within the environment

        :param key:     Environment variable name
        :param value:   Section to prepend
        """
        if key in self.__environment:
            self.__environment[key] = f"{value.strip()}:{self.__environment[key]}"
        else:
            self.__environment[key] = str(value).strip()

    def has_env(self, key : str) -> bool:
        """
        Check if an environment variable has been set for the container.

        :param key: Environment variable name
        :returns:   True if set, False otherwise
        """
        return key in self.__environment

    def get_env(self, key : str) -> Union[str, None]:
        """
        Get the value of an environment variable within the container.

        :param key: Environment variable name
        :returns:   Value of the environment variable or None if not found
        """
        return self.__environment.get(key, None)

    def overlay_env(self, env : Dict[str, str], strict : bool = False) -> None:
        """
        Overlay a set of environment variables onto the current set, if strict
        is set then any collision with an existing key will be flagged.

        :param env:     Environment variables to overlay
        :param strict:  Whether to raise an error if key already exists
        """
        for key, value in env.items():
            if strict and key in self.__environment and self.__environment[key] != value:
                raise ContainerError(
                    f"Clash for key '{key}' between existing environment value "
                    f"'{self.__environment[key]}' and new value '{value}'"
                )
            self.__environment[key] = value

    def launch(self,
               *command    : List[str],
               workdir     : Optional[Path] = None,
               interactive : bool           = False,
               display     : bool           = False) -> None:
        """
        Launch a task within the container either interactively (STDIN and STDOUT
        streamed from/to the console) or non-interactively (STDOUT is captured).
        Blocks until command execution completes.

        :param *command:    The command to execute
        :param workdir:     Working directory (defaults to /)
        :param interactive: Whether to interactively forward STDIN and STDOUT
        :param display:     Expose the host's DISPLAY variable to the container
        """
        # Check if a container is already running
        if self.__container:
            raise ContainerError("Container has already been launched")
        # Check for a command
        if not command:
            raise ContainerError("No command provided to execute")
        # Pickup default working directory if not set
        workdir = workdir or self.workdir
        # Make sure the local bind paths exist
        mounts = []
        for bind in self.__binds:
            if not bind.host_path.exists():
                bind.host_path.mkdir(parents=True)
            mounts.append(bind.as_configuration())
        # Environment
        env = {**self.__environment}
        if display:
            bind_xauth = ContainerBind(
                Path(os.environ.get("XAUTHORITY", "~/.Xauthority")).expanduser(),
                Path("/root/.Xauthority"),
                False
            )
            mounts.append(bind_xauth.as_configuration())
            if (x11_path := Path("/tmp/.X11-unix")).exists():
                env["DISPLAY"] = ":0"
                bind_x11_unix = ContainerBind(x11_path, x11_path, False)
                mounts.append(bind_x11_unix.as_configuration())
            else:
                env["DISPLAY"] = "host.containers.internal:0"
        # Get access to Podman within a context manager
        with Podman.get_client() as client:
            # Create the container
            self.__container = client.containers.run(
                # Give the container an identifiable name
                name       =self.__id,
                # Set the image the container should launch
                image      =self.image,
                # Set the initial command
                command    =command,
                # Set the initial working directory
                working_dir=workdir.as_posix(),
                # Launch as detached so that a container handle is returned
                detach     =True,
                # Attach a TTY to the process running in the container
                tty        =True,
                # Hold STDIN open even when nothing is attached
                stdin_open =True,
                # Mark the root filesystem as readonly
                read_only  =True,
                # Setup environment variables
                environment=env,
                # Setup folders to bind in
                mounts     =mounts,
                # Shared network with host
                network    ="host",
                # Set the UID to 0
                user       =0,
            )
            # Register tidy-up mechanism in case of unexpected exit
            def _make_tidy_up(container):
                def _tidy_up():
                    container.remove(force=True)
                return _tidy_up
            tidy_up = _make_tidy_up(self.__container)
            atexit.register(tidy_up)
            # Open a socket onto the container
            socket = self.__container.attach_socket(params={ "stdin"     : True,
                                                             "stdout"    : True,
                                                             "stderr"    : True,
                                                             "logs"      : True,
                                                             "detachKeys": "ctrl-p",
                                                             "stream"    : True })
            # If interactive, open a shell
            if interactive:
                # Log the keys to detach
                print(">>> Use CTRL+P to detach from container <<<")
                # Start monitoring for STDIN and STDOUT
                e_done = Event()
                t_write = write_stream(socket, e_done)
                t_read  = read_stream(socket, e_done)
                e_done.wait()
                t_read.join()
                t_write.join()
            # Otherwise, track the task
            else:
                while True:
                    line = socket.readline()
                    if not line:
                        break
                    print(line.decode("utf-8"), end="")
            # Tidy up
            atexit.unregister(tidy_up)
            self.__container.remove(force=True)
            self.__container = None

    def shell(self,
              command : Tuple[str]     = ("/bin/bash", ),
              workdir : Optional[Path] = None) -> None:
        self.launch(*command, workdir=workdir, interactive=True, display=True)
