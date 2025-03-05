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
import functools
import logging
import os
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import TextIO

import docker.utils.socket as socket_utils
import pytz
import requests
from docker.errors import ImageNotFound
from filelock import FileLock

from ..context import Context
from . import ExecutorError
from .common import (
    ExecutorBind,
    Invoker,
    decode_partial_utf8,
    forwarding_host,
    read_stream,
    write_stream,
)
from .runtime import Runtime


class Container(Invoker):
    """
    Transform execution context which launches invocations in a container.
    Container launch and management can be extended to support specific tools
    and workflows.

    :param context:     Execution context
    :param image:       Container image to launch with
    :param definition:  Container file definition
    :param workdir:     Default working directory (default: /)
    :param environment: Environment defaults to expose (empty by default)
    :param hostname:    Set a custom hostname (defaults to None)
    """

    def __init__(
        self,
        context: Context,
        image: str,
        definition: Path,
        environment: dict[str, str] | None = None,
        workdir: Path | None = None,
        hostname: str | None = None,
    ) -> None:
        super().__init__(context=context, environment=environment, workdir=workdir)
        # Store initialisation parameters
        self.image = image
        self.definition = definition
        self.hostname = hostname

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
    ) -> int:
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
        if not command:
            raise ExecutorError("No command provided to execute")

        # Build container if it doesn't already exist
        if not self.exists:
            self.build()

        # Make sure the local bind paths exist
        mounts = []
        for bind in self._binds:
            if not bind.host_path.exists():
                bind.host_path.mkdir(parents=True, exist_ok=True)
            mounts.append(bind.as_configuration())
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
                bind = ExecutorBind(
                    host_path=tmpdir / Path(implicit_path).relative_to("/"),
                    container_path=Path(implicit_path),
                    readonly=False,
                )
                bind.host_path.mkdir(parents=True, exist_ok=True)
                mounts.append(bind.as_configuration())
            # Create a thread-safe event to mark when container finishes
            e_done = Event()
            # Start a forwarding host
            t_host, host_port = forwarding_host(e_done)
            env["BLOCKWORK_FWD"] = f"{Runtime.get_host_address()}:{host_port}"
            # Create the container
            logging.debug(f"Creating container '{self._id}' with image '{self.image}'")
            container = client.containers.create(
                # Give the container an identifiable name
                name=self._id,
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
                t_write = write_stream(cntr_sock, e_done)
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
        return result.get("StatusCode", 1)
