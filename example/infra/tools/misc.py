from pathlib import Path
from typing import ClassVar

from blockwork.context import Context
from blockwork.tools import Invocation, Require, Tool, Version

from .compilers import GCC


@Tool.register()
class Python(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "python" / "3.11.4",
            version="3.11.4",
            requires=[Require(GCC, "13.1.0")],
            paths={
                "PATH": [Tool.CNTR_ROOT / "bin"],
                "LD_LIBRARY_PATH": [Tool.CNTR_ROOT / "lib"],
            },
            default=True,
        ),
    ]

    @Tool.installer("Python")
    def install(self, ctx: Context, version: Version, *args: list[str]) -> Invocation:
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://www.python.org/ftp/python/{vernum}/Python-{vernum}.tgz",
            f"tar -xf Python-{vernum}.tgz",
            f"cd Python-{vernum}",
            f"./configure --enable-optimizations --with-ensurepip=install "
            f"--enable-shared --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf Python-{vernum} ./*.tgz*",
        ]
        return Invocation(
            version=version,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class PythonSite(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "python-site" / "3.11.4",
            version="3.11.4",
            env={"PYTHONUSERBASE": Tool.CNTR_ROOT},
            paths={
                "PATH": [Tool.CNTR_ROOT / "bin"],
                "PYTHONPATH": [Tool.CNTR_ROOT / "lib" / "python3.11" / "site-packages"],
            },
            requires=[Require(Python, "3.11.4")],
            default=True,
        ),
    ]

    @Tool.action("PythonSite")
    def run(self, ctx: Context, *args: list[str]) -> Invocation:
        return Invocation(version=self.version, execute="python3", args=args)

    @Tool.installer("PythonSite")
    def install(self, ctx: Context, version: Version, *args: list[str]) -> Invocation:
        return Invocation(
            version=version,
            execute="python3",
            args=[
                "-m",
                "pip",
                "--no-cache-dir",
                "install",
                "-r",
                ctx.host_root / "infra" / "tools" / "pythonsite.txt",
            ],
            interactive=True,
            host=True,
        )


@Tool.register()
class Make(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "make" / "4.4.1",
            version="4.4.1",
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.action("Make", default=True)
    def run(self, ctx: Context, version: Version, *args: list[str]) -> Invocation:
        return Invocation(version=version, execute="make", args=args)

    @Tool.installer("Make")
    def install(self, ctx: Context, version: Version, *args: list[str]) -> Invocation:
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://ftp.gnu.org/gnu/make/make-{vernum}.tar.gz",
            f"tar -xf make-{vernum}.tar.gz",
            f"cd make-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf make-{vernum} ./*.tar.*",
        ]
        return Invocation(
            version=version,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )
