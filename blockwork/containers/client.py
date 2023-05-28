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
import subprocess
import tempfile
import time
from typing import Any, Dict, Tuple
from urllib.parse import urlparse
from pathlib import Path

from docker import DockerClient

class Podman:
    """
    Wraps the Podman REST API with a Docker Python client, adjusting for whether
    Podman is running locally or remotely. The Docker Python client is more fully
    featured that the Podman Python client, and is compatible with the Podman
    REST API.
    """

    @staticmethod
    @functools.lru_cache()
    def get_info() -> Dict[str, Any]:
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

    @staticmethod
    @functools.lru_cache()
    def is_remote() -> bool:
        """
        Determine if Podman is running locally or remote

        :returns:   True if remote, or False if locally
        """
        return Podman.get_info()["host"]["serviceIsRemote"]

    @staticmethod
    @functools.lru_cache()
    def get_rootless_remote_details() -> Tuple[str, str, int, str, str]:
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

    @staticmethod
    @contextlib.contextmanager
    def get_socket() -> Path:
        """
        Get a local handle to the Podman socket. If Podamn is running locally
        this just returns the socket, otherwise it opens an SSH link and forwards
        the socket from the remote system. This should be used as a context by
        wrapping it in a `with` statement.

        :yields:    Path to the local socket
        """
        if Podman.is_remote():
            user, host, port, path, identity = Podman.get_rootless_remote_details()
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
            yield Path(Podman.get_info()["host"]["remoteSocket"]["path"])

    @staticmethod
    @contextlib.contextmanager
    def get_client() -> DockerClient:
        """
        Get a Docker API client wrapped around the Podman API endpoint, either
        using the local or remote Podman service. This should be consumed as a
        context using the `with` keyword.

        :yields:    DockerClient instance wrapped around the Podman API
        """
        with Podman.get_socket() as sockpath:
            client = DockerClient(f"unix://{sockpath.as_posix()}")
            yield client
            client.close()
