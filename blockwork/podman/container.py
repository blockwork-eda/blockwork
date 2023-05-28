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
import contextlib
import dataclasses
import itertools
import os
import select
import sys
import termios
import time
import tty
from pathlib import Path
from threading import Event, Thread
from typing import Dict, List, Optional, Tuple, Union

import docker

from .client import Podman


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

    :param image:   Container image to launch with
    :param workdir: Working directory (default: /)
    :param command: Command to launch inside the container (default: /bin/bash)
    """

    LAUNCH_ID = itertools.count()

    def __init__(self,
                 image       : str,
                 workdir     : Path                     = Path("/"),
                 command     : Tuple[str]               = ("/bin/bash", ),
                 environment : Optional[Dict[str, str]] = None) -> None:
        # Store initialisation parameters
        self.image = image
        self.workdir = workdir
        self.command = command
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

    def set(self, key : str, value : str) -> None:
        """
        Set an environment variable within the container.

        :param key:     Environment variable name
        :param value:   Value of the environment variable
        """
        if self.__container:
            raise ContainerError("Environment must be set before launch")
        self.__environment[str(key)] = str(value)

    def get(self, key : str) -> Union[str, None]:
        """
        Get the value of an environment variable within the container.

        :param key: Environment variable name
        :returns:   Value of the environment variable or None if not found
        """
        return self.__environment.get(key, None)

    @contextlib.contextmanager
    def launch(self) -> None:
        """
        Launch the container with the stored configuration wrapped as a context.
        Calls should use the 'with' keyword to properly use the context, so that
        the cleanup phases run once the container completes.

        :yields:    This instance of Container, for easy operation chaining
        """
        # Check if a container is already running
        if self.__container:
            raise ContainerError("Container has already been launched")
        # Make sure the local bind paths exist
        mounts = []
        for bind in self.__binds:
            bind.host_path.mkdir(parents=True, exist_ok=True)
            mounts.append(bind.as_configuration())
        # Get access to Podman within a context manager
        with Podman.get_client() as client:
            # Create the container
            self.__container = client.containers.run(
                # Give the container an identifiable name
                name       =self.__id,
                # Set the image the container should launch
                image      =self.image,
                # Set the initial command
                command    =self.command,
                # Set the initial working directory
                working_dir=self.workdir.as_posix(),
                # Launch as detached so that a container handle is returned
                detach     =True,
                # Attach a TTY to the process running in the container
                tty        =True,
                # Hold STDIN open even when nothing is attached
                stdin_open =True,
                # Mark the root filesystem as readonly
                read_only  =True,
                # Setup environment variables
                environment=self.__environment,
                # Setup folders to bind in
                mounts     =mounts,
            )
            # Register tidy-up mechanism in case of unexpected exit
            def _make_tidy_up(container):
                def _tidy_up():
                    container.remove(force=True)
                return _tidy_up
            tidy_up = _make_tidy_up(self.__container)
            atexit.register(tidy_up)
            # Return this instance for easy chaining
            yield self
            # Tidy up
            atexit.unregister(tidy_up)
            self.__container.remove(force=True)
            self.__container = None

    @contextlib.contextmanager
    def __get_raw_input(self):
        """ Context manager to capture raw STDIN """
        stdin  = sys.stdin.fileno()
        before = termios.tcgetattr(stdin)
        try:
            tty.setraw(stdin)
            # TODO: There is an issue here with arrow key sequences lagging by
            #       one keypress
            def _get_char():
                rlist, _, _ = select.select([sys.stdin], [], [], 1.0)
                if rlist:
                    return sys.stdin.read(1)
                else:
                    return None
            yield _get_char
        finally:
            termios.tcsetattr(stdin, termios.TCSADRAIN, before)

    def __read_stream(self, socket, e_done) -> Thread:
        """ Wrapped thread method to capture from the container STDOUT """
        def _inner(socket, e_done):
            try:
                while not e_done.is_set():
                    buff = socket.read(1)
                    if len(buff) > 0:
                        sys.stdout.write(buff.decode("utf-8"))
                        sys.stdout.flush()
                    else:
                        break
                e_done.set()
            except BrokenPipeError:
                pass
        thread = Thread(target=_inner, args=(socket, e_done), daemon=True)
        thread.start()
        return thread

    def __write_stream(self, socket, e_done, command) -> Thread:
        """ Wrapped thread method to capture STDIN and write into container """
        def _inner(socket, e_done, command):
            with self.__get_raw_input() as get_char:
                try:
                    if command:
                        socket._sock.send((" ".join(command) + "\n").encode("utf-8"))
                    while not e_done.is_set():
                        if (char := get_char()) is not None:
                            socket._sock.send(char.encode("utf-8"))
                except BrokenPipeError:
                    pass
        thread = Thread(target=_inner, args=(socket, e_done, command), daemon=True)
        thread.start()
        return thread

    def shell(self, *command : Tuple[str]) -> None:
        """
        Open an interactive shell within a running container, optionally calling
        a command as the container opens.

        :param *command:    Positional arguments are taken as a command string
        """
        # Check container is launched
        if not self.__container:
            raise ContainerError("Container has not been launched")
        # Open a socket onto the container
        socket = self.__container.attach_socket(params={ "stdin"     : True,
                                                         "stdout"    : True,
                                                         "stderr"    : True,
                                                         "logs"      : True,
                                                         "detachKeys": "ctrl-p",
                                                         "stream"    : True })

        # Log the keys to detach
        print(">>> Use CTRL+P to detach from container <<<")
        # Start monitoring for STDIN and STDOUT
        e_done = Event()
        t_write = self.__write_stream(socket, e_done, command)
        t_read  = self.__read_stream(socket, e_done)
        e_done.wait()
        t_read.join()
        t_write.join()

    def execute(self, *command : Tuple[str]) -> None:
        """
        Execute a command within a running container, blocks until the command
        is complete.

        :param *command:    Positional arguments are taken as a command string
        """
        # Check container is launched
        if not self.__container:
            raise ContainerError("Container has not been launched")
        # Check for a command
        if len(command) == 0:
            raise ContainerError("No command provided")
        # Open a socket onto the container
        socket = self.__container.attach_socket(params={ "stdin" : True,
                                                         "stdout": True,
                                                         "stderr": True,
                                                         "logs"  : True,
                                                         "stream": True })
        # Write the command
        socket._sock.send("\n".encode("utf-8"))
        socket._sock.send((" ".join(command) + "\n").encode("utf-8"))
        socket._sock.send("exit\n".encode("utf-8"))
        while True:
            line = socket.readline()
            if not line:
                break
            print(line.decode("utf-8"), end="")
