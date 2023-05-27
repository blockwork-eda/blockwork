import json
import os
import pwd
import subprocess
import sys
import tty
import termios
import tempfile
import time
from contextlib import contextmanager
from urllib.parse import urlparse
from pathlib import Path
from threading import Thread
from typing import Tuple

from docker import DockerClient

root = Path(__file__).absolute().parent

def get_podman_access() -> Tuple[str, str, int, str, str]:
    p = subprocess.Popen(["podman", "system", "connection", "ls", "--format=json"],
                     stdout=subprocess.PIPE)
    out, _ = p.communicate()
    data = json.loads(out)
    default = [x for x in data if x["Name"] == "podman-machine-default"][0]
    parsed = urlparse(default["URI"])
    assert parsed.scheme == "ssh", f"Unsupported scheme {parsed.scheme}"
    return parsed.username, parsed.hostname, parsed.port, parsed.path, default["Identity"]

@contextmanager
def forward_port():
    user, host, port, path, identity = get_podman_access()
    tmpdir   = Path(tempfile.mkdtemp())
    sockfile = tmpdir / "podman.sock"
    command  = ["ssh",
                "-L",
                f"{sockfile.as_posix()}:{path}",
                "-i",
                identity,
                "-p",
                str(port),
                f"{user}@{host}"]
    print(" ".join(command))
    ssh_fwd  = subprocess.Popen(command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin =subprocess.PIPE)
    while not sockfile.exists():
        time.sleep(0.01)
    yield sockfile
    ssh_fwd.kill()
    sockfile.unlink()
    tmpdir.rmdir()

@contextmanager
def get_raw_input():
    stdin  = sys.stdin.fileno()
    before = termios.tcgetattr(stdin)
    try:
        tty.setraw(stdin)
        def _get_char():
            return sys.stdin.read(1)
        yield _get_char
    finally:
        termios.tcsetattr(stdin, termios.TCSADRAIN, before)


with forward_port() as portloc:
    assert portloc.exists()
    client = DockerClient(f"unix://{portloc.as_posix()}")
    # Check on the version
    version = client.version()
    print("Release: ", version["Version"])
    print("Compatible API: ", version["ApiVersion"])
    print("Podman API: ", version["Components"][0]["Details"]["APIVersion"], "\n")
    # Create a container
    user      = pwd.getpwuid(os.getuid()).pw_name
    v_input   = root / "test" / "input"
    v_output  = root / "test" / "output"
    v_tools   = root / "test" / "tools"
    v_scratch = root / "test" / "scratch"
    for dirx in (v_input, v_output, v_tools, v_scratch):
        dirx.mkdir(exist_ok=True, parents=True)
    response = client.containers.run(
        image      ="docker.io/library/rockylinux:9.1",
        detach     =True,
        tty        =True,
        stdin_open =True,
        command    =["/bin/bash"],
        name       =f"eda_dev_{user}",
        remove     =True,
        working_dir="/bw/scratch",
        mounts     = [{ "type"     : "bind",
                        "source"   : v_input.as_posix(),
                        "target"   : "/bw/input",
                        "read_only": True },
                      { "type"     : "bind",
                        "source"   : v_output.as_posix(),
                        "target"   : "/bw/output",
                        "read_only": False },
                      { "type"     : "bind",
                        "source"   : v_tools.as_posix(),
                        "target"   : "/bw/tools",
                        "read_only": True },
                      { "type"     : "bind",
                        "source"   : v_scratch.as_posix(),
                        "target"   : "/bw/scratch",
                        "read_only": False }]
    )
    socket = response.attach_socket(params={ "stdin": True, "stdout": True, "stream": True })

    def _read(socket):
        while True:
            sys.stdout.write(socket.read(1).decode("utf-8"))
            sys.stdout.flush()

    def _write(socket, get_char):
        while True:
            socket._sock.send(get_char().encode("utf-8"))

    with get_raw_input() as get_char:
        t_read  = Thread(target=_read,  args=(socket, ), daemon=True)
        t_write = Thread(target=_write, args=(socket, get_char), daemon=True)
        t_read.start()
        t_write.start()
        response.wait()

    # Start the container
    client.close()
