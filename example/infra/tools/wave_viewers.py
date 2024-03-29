from pathlib import Path
from typing import ClassVar

from blockwork.context import Context
from blockwork.tools import Invocation, Require, Tool, Version

from .compilers import GCC, Automake, GPerf


@Tool.register()
class GTKWave(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "gtkwave" / "3.3.116",
            version="3.3.116",
            requires=[
                Require(Automake, "1.16.5"),
                Require(GCC, "13.1.0"),
                Require(GPerf, "3.1"),
            ],
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.action("GTKWave", default=True)
    def view(self, ctx: Context, version: Version, wavefile: str, *args: list[str]) -> Invocation:
        path = Path(wavefile).absolute()
        return Invocation(
            version=version,
            execute="gtkwave",
            args=[path, *args],
            display=True,
            binds=[path.parent],
        )

    @Tool.action("GTKWave")
    def version(self, ctx: Context, version: Version, *args: list[str]) -> Invocation:
        return Invocation(
            version=version,
            execute="gtkwave",
            args=["--version", *args],
            display=True,
        )

    @Tool.installer("GTKWave")
    def install(self, ctx: Context, version: Version, *args: list[str]) -> Invocation:
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/gtkwave/gtkwave/archive/refs/tags/v{vernum}.tar.gz",
            f"tar -xf v{vernum}.tar.gz",
            f"cd gtkwave-{vernum}/gtkwave3-gtk3",
            f"./configure --prefix={tool_dir.as_posix()} --enable-gtk3",
            "make -j4",
            "make install",
            "cd ../..",
            f"rm -rf gtkwave-{vernum} ./*.tar.*",
        ]
        return Invocation(
            version=version,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
            interactive=True,
        )
