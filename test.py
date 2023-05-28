from pathlib import Path

from blockwork.podman.container import Container

container = Container("docker.io/library/rockylinux:9.1",
                      workdir=Path("/bw/scratch"))
container.bind_readonly(Path.cwd() / "bw" / "input")
container.bind_readonly(Path.cwd() / "bw" / "tools")
container.bind(Path.cwd() / "bw" / "output")
container.bind(Path.cwd() / "bw" / "scratch")
container.set("TEST", "VALUE_123")

with container.launch() as access:
    access.shell("echo", "hi")
    access.execute("echo", "hi")
    # breakpoint()
