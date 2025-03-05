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

import contextlib
import dataclasses
import fcntl
import itertools
import json
import logging
import os
import select
import shlex
import socket
import sys
import termios
import tty
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from socket import SocketIO
from threading import Event, Thread
from typing import TextIO, cast

from ..context import Context, ContextContainerPathError, ContextHostPathError
from ..tools import Tool
from ..tools.tool import Invocation


@contextlib.contextmanager
def get_raw_input():
    """
    Context manager to capture raw STDIN - this uses a raw I/O stream set to be
    non-blocking in order to forward every character. Control sequences such as
    arrow keys (up/down/left/right) are multiple character sequences which means
    that reading a single character at a time is not correct. Instead, a large
    read is executed in non-blocking mode which allows these multiple character
    sequences to be captured without deadlocking.
    """
    # Capture the base configuration of termios and fcntl
    stdin = sys.stdin.fileno()
    orig_termios = termios.tcgetattr(stdin)
    orig_fcntl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    # If any exception occurs, always capture it to avoid exception escaping
    try:
        # Set TTY into raw mode
        tty.setraw(stdin)

        # Yield a function to get a input
        def _get_char():
            # Wait up to one second for data
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            # If data available
            if sys.stdin in rlist:
                # Peek at the next (up to) 4096 bytes of data
                # NOTE: This is done to reliably capture multi-character control
                #       sequences while still maintaining updates on every single
                #       key press
                data = sys.stdin.buffer.peek(4096)
                # Read as much data as was 'peeked' to move the cursor forwards
                sys.stdin.buffer.read(len(data))
                return data

        yield _get_char
    finally:
        # Reset termios and fcntl back to base values
        termios.tcsetattr(stdin, termios.TCSADRAIN, orig_termios)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fcntl)


def decode_partial_utf8(buffer: bytes, errors: str = "strict") -> tuple[str, bytes]:
    """
    Detect if the bytes sequence ends mid-way through a multi-byte unicode
    character, and if so decode up to that point, returning the decoded
    unicode string and the remaining undecoded bytes.

    See:
    https://www.ibm.com/docs/en/db2/11.5?topic=support-unicode-character-encoding#c0004816__utf8utf16
    """
    if len(buffer) > 0 and (buffer[-1] & 0b1100_0000) == 0b1100_0000:
        # Last byte is start of a multi-byte sequence
        complete, partial = buffer[:-1], buffer[-1:]
    elif len(buffer) > 1 and ((buffer[-2] & 0b1110_0000) == 0b1110_0000):
        # Second to last byte is start of a three or four byte sequence
        complete, partial = buffer[:-2], buffer[-2:]
    elif len(buffer) > 2 and ((buffer[-3] & 0b1111_0000) == 0b1111_0000):
        # Third to last byte is start of a four byte sequence
        complete, partial = buffer[:-3], buffer[-3:]
    else:
        complete, partial = buffer, b""
    return complete.decode("utf-8", errors), partial


def read_stream(socket: SocketIO, stdout: TextIO, e_done: Event) -> Thread:
    """Wrapped thread method to capture from the container STDOUT"""

    def _inner(socket, e_done):
        try:
            # Move socket into non-blocking mode
            base = fcntl.fcntl(socket, fcntl.F_GETFL)
            fcntl.fcntl(socket, fcntl.F_SETFL, base | os.O_NONBLOCK)
            # Keep track of partial unicode characters
            partial_bytes = b""
            # Keep reading until done event set (or we break out)
            while not e_done.is_set():
                rlist, _, _ = select.select([socket], [], [], 0.1)
                if rlist:
                    buff = socket.read(1024)
                    string, partial_bytes = decode_partial_utf8(partial_bytes + buff)

                    if len(buff):
                        stdout.write(string)
                        stdout.flush()
                    else:
                        # If there are remaining partial bytes, this will except
                        partial_bytes.decode("utf-8", errors="strict")
                        break
        except BrokenPipeError:
            pass
        # Set event to signal completion of stream
        e_done.set()

    thread = Thread(target=_inner, args=(socket, e_done), daemon=True)
    thread.start()
    return thread


def write_stream(socket: SocketIO, e_done: Event, command: list[str] | None = None) -> Thread:
    """Wrapped thread method to capture STDIN and write into container"""

    def _inner(socket, e_done, command):
        with get_raw_input() as get_char:
            try:
                # Send the initial command sequence
                if command:
                    socket._sock.send((" ".join(command) + "\n").encode("utf-8"))
                # Monitor for further STDIO
                while not e_done.is_set():
                    if (char := get_char()) is not None:
                        socket._sock.send(char)
            except BrokenPipeError:
                pass
        # Set event to signal completion of stream
        e_done.set()

    thread = Thread(target=_inner, args=(socket, e_done, command), daemon=True)
    thread.start()
    return thread


def forwarding_host(e_done: Event) -> tuple[Thread, int]:
    """
    Wrapped thread method to handle forwarded commands from the container. Within
    the container, a relatively simple Python script encapsulates calls to the
    'blockwork' command in a JSON dictionary and forwards them to the socket
    exposed by this thread. This thread is then responsible for enacting the
    request and sending the response back to the socket. The sockets are
    implemented in a simple fashion so as to add few requirements to the Python
    installation within the container. All argument handling is performed by the
    host process.

    :param e_done:  Event that signals when container has finished
    :returns:       Tuple of the launched thread and the port number
    """
    # Choose a port number
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = s.getsockname()[1]

    # Declare the thread process
    def _inner(e_done, port):
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("", port))
            s.settimeout(0.2)
            s.listen()
            # Keep looping until container stops
            while not e_done.is_set():
                try:
                    conn, _addr = s.accept()
                except TimeoutError:
                    continue
                # Once a client connects, start receiving data
                with conn:
                    conn.setblocking(0)
                    conn.settimeout(0.2)
                    buffer = bytearray()
                    # The first 4 bytes carry the data size
                    while not e_done.is_set() and len(buffer) < 4:
                        buffer += conn.recv(4 - len(buffer))
                    # If done event set, break out
                    if e_done.is_set():
                        break
                    size = sum([(int(x) << (i * 8)) for i, x in enumerate(buffer)])
                    # The remaining data is encoded JSON
                    raw_data = conn.recv(size)
                    # Decode JSON
                    try:
                        data = json.loads(raw_data)
                    except json.JSONDecodeError:
                        print("Decoding error in forwarded command")
                        break
                    # TODO: DO SOMETHING WITH DATA!
                    # Encode response
                    raw_resp = json.dumps(
                        {
                            "stdout": f"STDOUT for {data}",
                            "stderr": f"STDERR for {data}",
                            "exitcode": 1,
                        }
                    ).encode("utf-8")
                    # Send the data size as the first 4 bytes
                    conn.sendall(bytearray(((len(raw_resp) >> (x * 8)) & 0xFF) for x in range(4)))
                    # Send the encoded data
                    conn.sendall(raw_resp)

    # Start the thread
    thread = Thread(target=_inner, args=(e_done, port), daemon=True)
    thread.start()
    # Return thread and port number
    return thread, port


class ExecutorError(Exception):
    pass


class ExecutorBindError(ExecutorError):
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
class ExecutorBind:
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


class Executor:
    """
    Base class for execution contexts which Transforms can run in.

    Can be subclasses to modify path bindings, but cannot run invocations.
    """

    LAUNCH_ID = itertools.count()

    def __init__(
        self,
        context: Context,
        environment: dict[str, str] | None = None,
    ) -> None:
        # Store initialisation parameters
        self.context = context
        # Configuration
        type_name = type(self).__name__.lower()
        issued_id = next(Executor.LAUNCH_ID)
        now = datetime.now(UTC).timestamp()
        self._id: str = f"bw_{os.getpid()}_{now}_{type_name}_{issued_id}"
        self._binds: list[ExecutorBind] = []
        self._environment: dict[str, str] = {}
        self._tools: dict[str, Tool] = {}

        if isinstance(environment, dict):
            self._environment.update(environment)

    @property
    def id(self):
        """Return the ID of the container"""
        return self._id

    def map_to_host(self, c_path: Path) -> Path:
        return self.context.map_to_host(c_path)

    def map_to_container(self, h_path: Path) -> Path:
        return self.context.map_to_container(h_path)

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
        if not container:
            container = Path("/") / host.name
        # Ensure paths are fully resolved
        host = host.resolve()
        container = container.resolve()
        # Check for duplicate bind inside the container
        for bind in self._binds:
            # If new bind exact match to existing bind, allow and skip
            if bind.container_path == container:
                if bind.host_path.samefile(host) and (bind.readonly == readonly):
                    return container
                else:
                    raise ExecutorBindError(host, container, readonly, bind)

            # If new bind is subpath of existing bind, allow if we can match
            # them up.
            if bind.container_path.is_relative_to(container):
                cont_relative = bind.container_path.relative_to(container)

                # If host path exact match for container subpath, allow
                if bind.host_path.samefile(host / cont_relative):
                    if bind.readonly != readonly:
                        raise ExecutorBindError(host, container, readonly, bind)

                # If host path also a subpath and the subpaths are the same
                # we've already bound in a directory and are now trying to
                # bind in a subpath, which is safe.
                elif bind.host_path.is_relative_to(host):
                    host_relative = bind.host_path.relative_to(host)
                    # And the subpaths are the same, we've already bound in a
                    # directory and are now trying to bind in a subpath, which
                    # can be ignored
                    if cont_relative != host_relative or bind.readonly != readonly:
                        raise ExecutorBindError(host, container, readonly, bind)

        if mkdir and not host.exists():
            host.mkdir(parents=True, exist_ok=True)
        self._binds.append(ExecutorBind(host, container, readonly))
        return container

    def bind_readonly(self, host: Path, container: Path | None = None) -> Path:
        """
        Bind a folder with read-only access from the host into the container at
        a given path, if the container path is not given then it uses the final
        path component and places it under the root directory.

        :param host:        Path on the host
        :param container:   Optional path within the container
        :returns:           Mapped path within the container
        """
        return self.bind(host, container, readonly=True)

    def bind_many(
        self,
        context: Context,
        binds: Sequence[Path | tuple[Path, Path]],
        readonly: bool = False,
    ):
        """
        Bind a list bind mappings or single paths (which will be mapped
        automatically). See `bind`.

        :param context:    Context object
        :param binds:      Path on the host
        :param readonly:   Whether to bind as readonly (default: False)
        """
        for entry in binds:
            if isinstance(entry, Path):
                h_path = entry
                h_path = h_path.absolute()
                c_path = context.map_to_container(h_path)
            else:
                h_path, c_path = entry
                h_path = h_path.absolute()
            self.bind(h_path, c_path, readonly=readonly)

    def bind_and_map_args(
        self, context: Context, args: Sequence[str | Path], host_okay: bool = True
    ) -> Sequence[str]:
        """
        Map host paths to container paths (if applicable) and bind paths to
        the container.

        :param context:     Context object
        :param args:        Arguments to map
        :param host_okay:   Whether to map arguments from host paths
        :returns:           List of mapped arguments
        """
        mapped_args = []
        binds = []

        # Identify all host paths that need to be bound in
        for arg in args:
            mapped_parts = []

            # Split strings as they might be passed in as e.g. `command '--path <mypath>'`
            if isinstance(arg, str):
                parts = shlex.split(arg)
            else:
                parts = [arg]

            for part in parts:
                # If this is a string, but appears to be a path, convert it
                if isinstance(part, str) and (
                    part.startswith("/") or part.startswith("./") or part.startswith("../")
                ):
                    part = Path.cwd() / part
                # For path arguments convert to str...
                if isinstance(part, Path):
                    if host_okay:
                        # ...and conditionally try binding host paths to container
                        # try our best with paths that look like directories or files
                        part = part.absolute().resolve()
                        h_path, h_name = part, ""
                        try:
                            c_path = context.map_to_container(h_path)
                            binds.append((h_path, c_path))
                            part = c_path / h_name
                        except ContextHostPathError:
                            logging.debug(f"Assuming '{part}' is a container-relative path")
                    mapped_parts.append(part.as_posix())
                # Otherwise, just pass through the argument
                else:
                    mapped_parts.append(part)
            mapped_args.append(shlex.join(mapped_parts))

        for h_path, c_path in binds:
            self.bind(h_path, c_path, False)

        return mapped_args

    def add_tool(self, tool: type[Tool] | Tool, readonly: bool = True) -> None:
        # If class has been provided, create an instance
        if not isinstance(tool, Tool):
            if not issubclass(tool, Tool):
                raise ExecutorError("Tool definitions must inherit from the Tool class")
            tool = tool()
        tool_ver = tool.version
        # Check tool is not already registered
        if tool.base_id in self._tools:
            if self._tools[tool.base_id].version is tool_ver:
                return
            raise ExecutorError(f"Tool already registered for ID '{tool.base_id}'")
        # Load any requirements
        for req in tool_ver.requires:
            if req.tool.base_id in self._tools:
                if (rv := req.tool.version) != (xv := self._tools[req.tool.base_id].version):
                    raise ExecutorError(
                        f"Version clash for tool '{req.tool.base_id}': {rv} != {xv}"
                    )
            else:
                self.add_tool(req.tool, readonly=readonly)
        # Register tool and bind in the base folder
        self._tools[tool.base_id] = tool
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

    def set_env(self, key: str, value: str) -> None:
        """
        Set an environment variable within the container.

        :param key:     Environment variable name
        :param value:   Value of the environment variable
        """
        self._environment[str(key)] = str(value)

    def append_env_path(self, key: str, value: str) -> None:
        """
        Append to a path variable within the environment

        :param key:     Environment variable name
        :param value:   Section to append
        """
        if key in self._environment:
            self._environment[key] += f":{value.strip()}"
        else:
            self._environment[key] = str(value).strip()

    def prepend_env_path(self, key: str, value: str) -> None:
        """
        Prepend to a path variable within the environment

        :param key:     Environment variable name
        :param value:   Section to prepend
        """
        if key in self._environment:
            self._environment[key] = f"{value.strip()}:{self._environment[key]}"
        else:
            self._environment[key] = str(value).strip()

    def has_env(self, key: str) -> bool:
        """
        Check if an environment variable has been set for the container.

        :param key: Environment variable name
        :returns:   True if set, False otherwise
        """
        return key in self._environment

    def get_env(self, key: str) -> str | None:
        """
        Get the value of an environment variable within the container.

        :param key: Environment variable name
        :returns:   Value of the environment variable or None if not found
        """
        return self._environment.get(key, None)

    def overlay_env(self, env: dict[str, str], strict: bool = False) -> None:
        """
        Overlay a set of environment variables onto the current set, if strict
        is set then any collision with an existing key will be flagged.

        :param env:     Environment variables to overlay
        :param strict:  Whether to raise an error if key already exists
        """
        for key, value in env.items():
            if strict and key in self._environment and self._environment[key] != value:
                raise ExecutorError(
                    f"Clash for key '{key}' between existing environment value "
                    f"'{self._environment[key]}' and new value '{value}'"
                )
            self._environment[key] = value


class Invoker(Executor):
    """
    Base class for execution contexts which can launch tool invocations.
    """

    def __init__(
        self,
        context: Context,
        environment: dict[str, str] | None = None,
        workdir: Path | None = None,
    ) -> None:
        super().__init__(context=context, environment=environment)
        self.workdir = workdir

    def launch(
        self,
        *command: str,
        workdir: Path | None = None,
        interactive: bool = False,
        display: bool = False,
        show_detach: bool = True,
        clear: bool = False,
        env: dict[str, str] | None = None,
        path: Mapping[str, list[Path]] | None = None,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
    ) -> int:
        stdout = stdout or cast(TextIO, sys.stdout)
        stderr = stderr or cast(TextIO, sys.stderr)
        # Pickup default working directory if not set
        workdir = workdir or self.workdir or Path("/")
        # Disable interactive if not a terminal
        # Note we check stdout rather than stdin because when piping out to
        # a file, stdin still reports as tty, but stdout does not.
        interactive &= stdout and stdout.isatty()
        # Merge baseline environment with provided environment
        env = {**self._environment, **(env or {})}
        # Merge path variables into the environment
        for key, extension in (path or {}).items():
            existing = env.get(key, "")
            if len(existing) > 0:
                existing += ":"
            env[key] = existing + ":".join(map(str, extension))

        return self._launch(
            *command,
            workdir=workdir,
            interactive=interactive,
            display=display,
            show_detach=show_detach,
            clear=clear,
            env=env,
            stdout=stdout,
            stderr=stderr,
        )

    def _launch(
        self,
        *command: str,
        workdir: Path,
        interactive: bool,
        display: bool,
        show_detach: bool,
        clear: bool,
        env: dict[str, str],
        stdout: TextIO,
        stderr: TextIO,
    ):
        """
        Implement to define how this executor runs commands.
        """
        raise NotImplementedError

    def shell(
        self,
        command: tuple[str, ...] = ("/bin/bash",),
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
        return self.launch(
            *command,
            workdir=workdir,
            interactive=True,
            display=True,
            show_detach=show_detach,
        )

    def invoke(self, context: Context, invocation: Invocation, readonly: bool = True) -> int:
        """
        Evaluate a tool invocation by binding the required tools and setting up
        the environment as per the request.

        :param context:     Context in which invocation is launched
        :param invocation:  An Invocation object
        :param readonly:    Whether to bind tools read only (defaults to True)
        :returns:           Exit code from the executed process
        """
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
