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
import functools
import itertools
import logging
import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import TextIO

import docker.utils.socket as socket_utils
import pytz
import requests
from docker.errors import ImageNotFound
from filelock import FileLock

from ..context import Context, ContextHostPathError
from .common import decode_partial_utf8, forwarding_host, read_stream, write_stream
from .runtime import Runtime


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


class Container:
    """
    Wrapper around container launch and management that can be extended to support
    specific tools and workflows.

    :param context:     Execution context
    :param image:       Container image to launch with
    :param definition:  Container file definition
    :param workdir:     Default working directory (default: /)
    :param environment: Environment defaults to expose (empty by default)
    :param hostname:    Set a custom hostname (defaults to None)
    """

    LAUNCH_ID = itertools.count()

    def __init__(
        self,
        context: Context,
        image: str,
        definition: Path,
        workdir: Path = Path("/"),
        environment: dict[str, str] | None = None,
        hostname: str | None = None,
    ) -> None:
        # Store initialisation parameters
        self.context = context
        self.image = image
        self.definition = definition
        self.workdir = workdir
        self.hostname = hostname
        # Configuration
        type_name = type(self).__name__.lower()
        issued_id = next(Container.LAUNCH_ID)
        now = datetime.now(UTC).timestamp()
        self.__id: str = f"bw_{os.getpid()}_{now}_{type_name}_{issued_id}"
        self.__binds: list[ContainerBind] = []
        self.__environment: dict[str, str] = {}
        if isinstance(environment, dict):
            self.__environment.update(environment)

    @property
    def id(self):
        """Return the ID of the container"""
        return self.__id

    @property
    @functools.cache  # noqa: B019
    def exists(self) -> bool:
        """Determine whether the container image is already built"""
        with Runtime.get_client() as client:
            try:
                client.images.get(self.image)
            except ImageNotFound:
                return False
        return True

    def build(self):
        """Build the container image"""
        # Grab a lock to avoid races with other build actions in this same workspace
        # NOTE: Deliberately made local to the machine
        with Runtime.get_client() as client, FileLock(f"/tmp/{self.image}.lock"):
            # Check if the image exists (in case it was removed manually)
            try:
                data = client.images.get(self.image)
                last_run = datetime.fromisoformat(data.attrs["Created"])
            except ImageNotFound:
                last_run = datetime.fromtimestamp(0, tz=pytz.UTC)
            # Check that the container file can be found
            if not self.definition.exists():
                raise FileExistsError(f"Failed to open definition {self.definition}")
            # Check if the container file is newer than the last run
            file_time = datetime.fromtimestamp(self.definition.stat().st_mtime, tz=pytz.UTC)
            if file_time <= last_run:
                return
            # Build the container
            logging.info(
                f"Building container image from {self.definition} for "
                f"{self.context.host_architecture} architecture - this may take "
                f"a while..."
            )
            client.images.build(
                path=self.definition.parent.as_posix(),
                dockerfile=self.definition.name,
                tag=self.image,
                rm=True,
            )
            logging.info("Container built")

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
        for bind in self.__binds:
            # If new bind exact match to existing bind, allow and skip
            if bind.container_path == container:
                if bind.host_path.samefile(host) and (bind.readonly == readonly):
                    return container
                else:
                    raise ContainerBindError(host, container, readonly, bind)

            # If new bind is subpath of existing bind, allow if we can match
            # them up.
            if bind.container_path.is_relative_to(container):
                cont_relative = bind.container_path.relative_to(container)

                # If host path exact match for container subpath, allow
                if bind.host_path.samefile(host / cont_relative):
                    if bind.readonly != readonly:
                        raise ContainerBindError(host, container, readonly, bind)

                # If host path also a subpath and the subpaths are the same
                # we've already bound in a directory and are now trying to
                # bind in a subpath, which is safe.
                elif bind.host_path.is_relative_to(host):
                    host_relative = bind.host_path.relative_to(host)
                    # And the subpaths are the same, we've already bound in a
                    # directory and are now trying to bind in a subpath, which
                    # can be ignored
                    if cont_relative != host_relative or bind.readonly != readonly:
                        raise ContainerBindError(host, container, readonly, bind)

        if mkdir and not host.exists():
            host.mkdir(parents=True, exist_ok=True)
        self.__binds.append(ContainerBind(host, container, readonly))
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

    def set_env(self, key: str, value: str) -> None:
        """
        Set an environment variable within the container.

        :param key:     Environment variable name
        :param value:   Value of the environment variable
        """
        self.__environment[str(key)] = str(value)

    def append_env_path(self, key: str, value: str) -> None:
        """
        Append to a path variable within the environment

        :param key:     Environment variable name
        :param value:   Section to append
        """
        if key in self.__environment:
            self.__environment[key] += f":{value.strip()}"
        else:
            self.__environment[key] = str(value).strip()

    def prepend_env_path(self, key: str, value: str) -> None:
        """
        Prepend to a path variable within the environment

        :param key:     Environment variable name
        :param value:   Section to prepend
        """
        if key in self.__environment:
            self.__environment[key] = f"{value.strip()}:{self.__environment[key]}"
        else:
            self.__environment[key] = str(value).strip()

    def has_env(self, key: str) -> bool:
        """
        Check if an environment variable has been set for the container.

        :param key: Environment variable name
        :returns:   True if set, False otherwise
        """
        return key in self.__environment

    def get_env(self, key: str) -> str | None:
        """
        Get the value of an environment variable within the container.

        :param key: Environment variable name
        :returns:   Value of the environment variable or None if not found
        """
        return self.__environment.get(key, None)

    def overlay_env(self, env: dict[str, str], strict: bool = False) -> None:
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
        # Check for a command
        if not command:
            raise ContainerError("No command provided to execute")
        stdout = stdout or sys.stdout
        stderr = stderr or sys.stderr
        # Disable interactive if not a terminal
        # Note we check stdout rather than stdin because when piping out to
        # a file, stdin still reports as tty, but stdout does not.
        interactive &= stdout and stdout.isatty()
        # Pickup default working directory if not set
        workdir = workdir or self.workdir
        # Make sure the local bind paths exist
        mounts = []
        for bind in self.__binds:
            if not bind.host_path.exists():
                bind.host_path.mkdir(parents=True, exist_ok=True)
            mounts.append(bind.as_configuration())
        # Merge baseline environment with provided environment
        env = {**self.__environment, **(env or {})}
        # Merge path variables into the environment
        for key, extension in (path or {}).items():
            existing = env.get(key, "")
            if len(existing) > 0:
                existing += ":"
            env[key] = existing + ":".join(map(str, extension))
        # Collect files to 'push' into the container's temporary directory
        tmpfiles = []
        # Setup $DISPLAY
        if display:
            # If we're on macOS, use the Docker Desktop forwarding
            if Runtime.is_macos():
                # Locate the user's Xauthority on the host
                xauth_h_path = Path(os.environ.get("XAUTHORITY", "~/.Xauthority")).expanduser()
                # If Xauthority exists, copy it into the container
                if xauth_h_path.exists():
                    logging.debug(f"XAuthority located at {xauth_h_path}")
                    tmpfiles.append(xauth_h_path)
                # Set the Xauthority file location within the container
                env["XAUTHORITY"] = "/tmp/.Xauthority"
                env["DISPLAY"] = f"{Runtime.get_host_address()}:0"
                logging.debug(f"Setting DISPLAY to {env['DISPLAY']}")
            # Otherwise, look for xauth
            elif (xauth := shutil.which("xauth")) is not None:
                rsp = subprocess.run((xauth, "list"), capture_output=True)
                if rsp.returncode == 0:
                    lines = rsp.stdout.decode("utf-8").splitlines()
                    hostname = socket.gethostname()
                    hostmatch = [x for x in lines if hostname in x]
                    if hostmatch:
                        env["BLOCKWORK_XTOKEN"] = hostmatch[-1].split(" ")[-1].strip()
                        env["DISPLAY"] = os.environ.get("DISPLAY", ":0")
                        logging.debug(
                            f"Setting DISPLAY to {env['DISPLAY']} and passing "
                            f"through the xauth magic cookie"
                        )
        # Expose terminal dimensions
        tsize = shutil.get_terminal_size()
        logging.debug(f"Setting terminal to {tsize.columns}x{tsize.lines}")
        env["LINES"] = str(tsize.lines)
        env["COLUMNS"] = str(tsize.columns)
        env["TERM"] = "xterm-256color"
        # Set TMP and TMPDIR environment variables
        env["TMP"] = "/tmp"
        env["TMPDIR"] = "/tmp"
        # Get access to container within a context manager
        with Runtime.get_client() as client, tempfile.TemporaryDirectory(prefix=self.id) as tmpdir:
            tmpdir = Path(tmpdir)
            # Copy requested files into the temporary directory
            (tmpdir / "tmp").mkdir(exist_ok=True, parents=True)
            for file in tmpfiles:
                target = tmpdir / "tmp" / file.name
                logging.debug(f"Copying {file} to {target}")
                shutil.copy(file, target)
            # Create a temporary script to execute
            # NOTE: Arguments containing spaces will be wrapped by double quotes
            run_script = tmpdir / "tmp" / "run.sh"
            run_script.write_text("#!/bin/bash\n" + shlex.join(command))
            env["BLOCKWORK_CMD"] = "/tmp/run.sh"
            # Provide mounts for '/tmp' and other paths (using a tmpfs mount
            # implicitly adds 'noexec' preventing binaries executing)
            for implicit_path in ["/tmp", "/root", "/var/log", "/var/cache"]:
                bind = ContainerBind(
                    host_path=tmpdir / Path(implicit_path).relative_to("/"),
                    container_path=Path(implicit_path),
                    readonly=False,
                )
                bind.host_path.mkdir(parents=True, exist_ok=True)
                mounts.append(bind.as_configuration())
            # Create a thread-safe event to mark when container finishes
            e_done = Event()
            # Create a thread-safe event to mark when keys are sent to the container
            e_sent = Event()
            # Start a forwarding host
            t_host, host_port = forwarding_host(e_done)
            env["BLOCKWORK_FWD"] = f"{Runtime.get_host_address()}:{host_port}"
            # Create the container
            logging.debug(f"Creating container '{self.__id}' with image '{self.image}'")
            container = client.containers.create(
                # Give the container an identifiable name
                name=self.__id,
                # Set the image the container should launch
                image=self.image,
                # Set the initial command
                command="/usr/bin/launch.sh",
                # Set the initial working directory
                working_dir=workdir.as_posix(),
                # Launch as detached so that a container handle is returned
                detach=True,
                # Attach a TTY to the process running in the container
                tty=interactive,
                # Hold STDIN open even when nothing is attached
                stdin_open=interactive,
                # Mark the root filesystem as readonly
                read_only=True,
                # Setup environment variables
                environment=env,
                # Setup folders to bind in
                mounts=mounts,
                # Shared network with host
                network="host",
                # Set the UID based on the platform's behaviour
                user=Runtime.get_uid(),
                # Customise the hostname
                hostname=self.hostname,
            )

            # Register tidy-up mechanism in case of unexpected exit
            def _make_tidy_up(container):
                def _tidy_up():
                    container.remove(force=True)

                return _tidy_up

            tidy_up = _make_tidy_up(container)
            atexit.register(tidy_up)
            # Open a socket onto the container
            cntr_sock = container.attach_socket(
                params={
                    "stdin": True,
                    "stdout": True,
                    "stderr": True,
                    "logs": True,
                    "detachKeys": "ctrl-p",
                    "stream": True,
                }
            )
            # Start the job
            container.start()
            # If interactive, open a shell
            if interactive:
                # Log the keys to detach
                if show_detach:
                    print(">>> Use CTRL+P to detach from container <<<")
                # Start monitoring for STDIN and STDOUT
                t_write = write_stream(cntr_sock, e_done, e_sent)
                t_read = read_stream(cntr_sock, stdout, e_done)
                e_done.wait()
                t_read.join()
                t_write.join()
                # Clear the screen
                if clear:
                    os.system("cls || clear")
            # Otherwise, track the task
            else:
                partial_bytes = b""
                for stream, b_line in socket_utils.frames_iter(cntr_sock, tty=False):
                    line, partial_bytes = decode_partial_utf8(partial_bytes + b_line)
                    if stream == socket_utils.STDOUT:
                        stdout.write(line)
                    elif stream == socket_utils.STDERR:
                        stderr.write(line)
                    else:
                        raise RuntimeError(f"Unexpected stream `{stream}` for line `{line}`")
                # If there are remaining partial bytes, this will except
                partial_bytes.decode("utf-8", errors="strict")
                stdout.flush()
                stderr.flush()
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
        return ContainerResult(exit_code=result.get("StatusCode", 1), interacted=e_sent.is_set())

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
        return self.launch(
            *command,
            workdir=workdir,
            interactive=True,
            display=True,
            show_detach=show_detach,
        ).exit_code
