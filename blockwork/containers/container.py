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
import logging
import os
import time
from pathlib import Path
from threading import Event
from typing import Dict, List, Optional, Tuple, Union

import requests

from .runtime import Runtime
from .common import read_stream, write_stream, forwarding_host


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
    Wrapper around container launch and management that can be extended to support
    specific tools and workflows.

    :param image:       Container image to launch with
    :param workdir:     Default working directory (default: /)
    :param environment: Environment defaults to expose (empty by default)
    :param hostname:    Set a custom hostname (defaults to None)
    """

    LAUNCH_ID = itertools.count()

    def __init__(self,
                 image       : str,
                 workdir     : Path = Path("/"),
                 environment : Optional[Dict[str, str]] = None,
                 hostname    : Optional[str] = None) -> None:
        # Store initialisation parameters
        self.image = image
        self.workdir = workdir
        self.hostname = hostname
        # Configuration
        type_name = type(self).__name__.lower()
        issued_id = next(Container.LAUNCH_ID)
        self.__id : str = f"bw_{os.getpid()}_{type_name}_{issued_id}"
        self.__binds : List[ContainerBind] = []
        self.__environment : Dict[str, str] = {}
        if isinstance(environment, dict):
            self.__environment.update(environment)

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
        path component and places it under the root directory.

        :param host:        Path on the host
        :param container:   Optional path within the container
        :param readonly:    Whether to bind as readonly (default: False)
        :returns:           Mapped path within the container
        """
        if not container:
            container = Path("/") / host.name
        # Ensure paths are fully resolved
        host      = host.resolve()
        container = container.resolve()
        # Check for duplicate bind inside the container
        for bind in self.__binds:
            c_match = bind.container_path == container
            # If exact match, silently allow
            if c_match and bind.host_path.samefile(host) and (bind.readonly == readonly):
                return
            # Otherwise if a match or a parent, fail
            elif c_match or container in bind.container_path.parents:
                raise ContainerError(f"Cannot bind {host} to {container} due to"
                                     f"collision with existing bind from {bind.host_path}")
        self.__binds.append(ContainerBind(host, container, readonly))
        return container

    def bind_readonly(self, host : Path, container : Optional[Path] = None) -> Path:
        """
        Bind a folder with read-only access from the host into the container at
        a given path, if the container path is not given then it uses the final
        path component and places it under the root directory.

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
               display     : bool           = False,
               show_detach : bool           = True,
               clear       : bool           = False) -> int:
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
        :returns:           Exit code of the executed process
        """
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
                env["DISPLAY"] = f"{Runtime.get_host_address()}:0"
        # Expose terminal dimensions
        tsize = os.get_terminal_size()
        logging.info(f"Setting terminal to {tsize.columns}x{tsize.lines}")
        env["LINES"]   = str(tsize.lines)
        env["COLUMNS"] = str(tsize.columns)
        env["TERM"]    = "xterm-256color"
        # Map /tmp to a tmpfs and set TMPDIR and TMP environment variables
        mounts.append({ "type": "tmpfs", "target": "/tmp" })
        env["TMPDIR"] = "/tmp"
        env["TMP"]    = "/tmp"
        # Get access to container within a context manager
        with Runtime.get_client() as client:
            # Create a thread-safe event to mark when container finishes
            e_done = Event()
            # Start a forwarding host
            t_host, host_port = forwarding_host(e_done)
            env["BLOCKWORK_FWD"] = f"{Runtime.get_host_address()}:{host_port}"
            # Create the container
            container = client.containers.create(
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
                tty        =interactive,
                # Hold STDIN open even when nothing is attached
                stdin_open =interactive,
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
                # Customise the hostname
                hostname   =self.hostname,
            )
            # Register tidy-up mechanism in case of unexpected exit
            def _make_tidy_up(container):
                def _tidy_up():
                    container.remove(force=True)
                return _tidy_up
            tidy_up = _make_tidy_up(container)
            atexit.register(tidy_up)
            # Open a socket onto the container
            socket = container.attach_socket(params={ "stdin"     : True,
                                                      "stdout"    : True,
                                                      "stderr"    : True,
                                                      "logs"      : True,
                                                      "detachKeys": "ctrl-p",
                                                      "stream"    : True })
            # Start the job
            container.start()
            # If interactive, open a shell
            if interactive:
                # Log the keys to detach
                if show_detach:
                    print(">>> Use CTRL+P to detach from container <<<")
                # Start monitoring for STDIN and STDOUT
                t_write = write_stream(socket, e_done)
                t_read  = read_stream(socket, e_done)
                e_done.wait()
                t_read.join()
                t_write.join()
                # Clear the screen
                if clear:
                    os.system("cls || clear")
            # Otherwise, track the task
            else:
                while True:
                    line = socket.readline()
                    if not line:
                        break
                    try:
                        print(line.decode("utf-8"), end="")
                    except UnicodeDecodeError:
                        pass
            # Get the result (carries the status code)
            # NOTE: Podman sometimes drops the connection during 'wait()' leading
            #       to a connection aborted error, so retry the operation until
            #       it succeeds or reaching 10 failed attempts
            for _ in range(10):
                try:
                    result = container.wait()
                    break
                except requests.exceptions.ConnectionError:
                    time.sleep(0.1)
                    continue
            else:
                raise Exception("Failed to retrieve container result after 10 attempts")
            # Ensure the host thread has exited
            e_done.set()
            t_host.join()
            # Tidy up
            atexit.unregister(tidy_up)
            container.remove(force=True)
            container = None
        # Extract the status code (assume error if not set)
        return result.get("StatusCode", 1)

    def shell(self,
              command     : Tuple[str]     = ("/bin/bash", ),
              workdir     : Optional[Path] = None,
              show_detach : bool           = False) -> int:
        """
        Open an interactive shell in the container. This is similar to launch,
        but always enables and interactive shell and forwards the X11 display.

        :param command:     Command to execute (defaults to /bin/bash)
        :param workdir:     Working directory (defaults to /)
        :param show_detach: Whether to show the detach key message
        :returns:           Exit code from the executed process
        """
        return self.launch(*command,
                           workdir=workdir,
                           interactive=True,
                           display=True,
                           show_detach=show_detach)
