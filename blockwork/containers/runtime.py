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
import functools
import json
import logging
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, Generator, Tuple
from urllib.parse import urlparse
from pathlib import Path

from docker import DockerClient

class Runtime:
    """
    Wraps a Docker-compatible REST API with the Docker Python client, this is
    compatible with Docker and other container runtimes like Podman and Orbstack.
    """

    PREFERENCE = None

    @classmethod
    def set_preferred_runtime(cls, preference : str) -> None:
        cls.PREFERENCE = preference

    @classmethod
    @functools.lru_cache()
    def is_orbstack_available(cls) -> bool:
        if shutil.which("orbctl") is None:
            return False
        if subprocess.run(["orbctl", "status"], capture_output=True).returncode != 0:
            return False
        return True

    @classmethod
    @functools.lru_cache()
    def is_podman_available(cls) -> bool:
        if shutil.which("podman") is None:
            return False
        if subprocess.run(["podman", "system", "info"], capture_output=True).returncode != 0:
            return False
        return True

    @classmethod
    @functools.lru_cache()
    def is_docker_available(cls) -> bool:
        if shutil.which("docker") is None:
            return False
        if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
            return False
        return True

    @classmethod
    @functools.lru_cache()
    def identify_runtime(cls) -> str:
        """
        Attempt to identify which container runtime is being used by testing for
        different binaries. Test for 'docker' last as many other runtimes offer
        a 'dummy' docker command.

        :returns:   Name of the identified runtime
        """
        if cls.PREFERENCE is not None:
            pref = cls.PREFERENCE.lower()
            if pref not in ("orbstack", "podman", "docker"):
                raise Exception(f"Unsupported runtime: {pref}")
            logging.debug(f"Using preferred runtime: {pref}")
            return pref
        elif cls.is_orbstack_available():
            logging.debug("Using Orbstack as the container runtime")
            return "orbstack"
        elif cls.is_podman_available():
            logging.debug("Using Podman as the container runtime")
            return "podman"
        elif cls.is_docker_available():
            logging.debug("Using Docker as the container runtime")
            return "docker"
        else:
            raise Exception("Could not identify a container runtime")

    @classmethod
    @functools.lru_cache()
    def get_host_address(cls) -> str:
        """
        Determine the hostname used to access the container host from within the
        running container.

        :returns:   String of the hostname
        """
        if cls.is_podman_available():
            return "host.containers.internal"
        else:
            return "host.internal"

    @classmethod
    @functools.lru_cache()
    def get_podman_info(cls) -> Dict[str, Any]:
        """
        Read back the information dictionary from the local Podman client which
        contains details on the host.

        :returns:   Parsed dictionary from Podman's JSON output
        """
        proc = subprocess.Popen(["podman", "info", "--format=json"],
                                stdout=subprocess.PIPE)
        out, _ = proc.communicate()
        assert proc.returncode == 0, f"Bad podman exit code: {proc.returncode}"
        return json.loads(out)

    @classmethod
    @functools.lru_cache()
    def is_podman_remote(cls) -> bool:
        """
        Determine if Podman is running locally or remote

        :returns:   True if remote, or False if locally
        """
        return cls.get_podman_info()["host"]["serviceIsRemote"]

    @classmethod
    @functools.lru_cache()
    def get_rootless_remote_podman_details(cls) -> Tuple[str, str, int, str, str]:
        """
        Get the rootless remote access details.

        :returns:   Tuple of username, hostname, port, remote socket path, and
                    the local SSH identity path
        """
        p = subprocess.Popen(["podman", "system", "connection", "ls", "--format=json"],
                             stdout=subprocess.PIPE)
        out, _ = p.communicate()
        data = json.loads(out)
        default = [x for x in data if x["Name"] == "podman-machine-default"][0]
        parsed = urlparse(default["URI"])
        assert parsed.scheme == "ssh", f"Unsupported scheme {parsed.scheme}"
        return parsed.username, parsed.hostname, parsed.port, parsed.path, default["Identity"]

    @classmethod
    @contextlib.contextmanager
    def get_podman_socket(cls) -> Path:
        """
        Get a local handle to the Podman socket. If Podamn is running locally
        this just returns the socket, otherwise it opens an SSH link and forwards
        the socket from the remote system. This should be used as a context by
        wrapping it in a `with` statement.

        :yields:    Path to the local socket
        """
        if cls.is_podman_remote():
            user, host, port, path, identity = cls.get_rootless_remote_podman_details()
            tmpdir   = Path(tempfile.mkdtemp())
            sockfile = tmpdir / "podman.sock"
            command  = ["ssh", "-L", f"{sockfile.as_posix()}:{path}",
                               "-i", identity,
                               "-p", str(port),
                               f"{user}@{host}"]
            ssh_fwd  = subprocess.Popen(command,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        stdin =subprocess.PIPE)
            # Wait for the forwarded socket to appear
            while not sockfile.exists():
                time.sleep(0.01)
            # Yield to the context consumer
            yield sockfile
            # Clean up once the context closes
            ssh_fwd.kill()
            sockfile.unlink()
            tmpdir.rmdir()
        else:
            yield Path(cls.get_podman_info()["host"]["remoteSocket"]["path"])

    @classmethod
    @contextlib.contextmanager
    def get_docker_socket(cls) -> Path:
        """
        Get a local handle to the Docker REST API socket.

        :yields:    Path to the Docker socket file
        """
        yield Path("/var/run/docker.sock")

    @classmethod
    @contextlib.contextmanager
    def get_client(cls) -> Generator[DockerClient, None, None]:
        """
        Get a Docker API client wrapped around the runtime API endpoint, either
        using the local or remote runtime service. This should be consumed as a
        context using the `with` keyword.

        :yields:    DockerClient instance wrapped around the runtime's API
        """
        runtime = cls.identify_runtime()
        if runtime == "podman":
            get_sock = cls.get_podman_socket
        else:
            get_sock = cls.get_docker_socket
        with get_sock() as sockpath:
            client = DockerClient(f"unix://{sockpath.as_posix()}")
            yield client
            client.close()
