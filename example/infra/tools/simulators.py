from pathlib import Path
from typing import ClassVar

from blockwork.context import Context
from blockwork.tools import Invocation, Require, Tool, Version

from .compilers import GCC, Autoconf, Bison, CCache, Flex, GPerf, Help2Man


@Tool.register()
class IVerilog(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "iverilog" / "12.0",
            version="12.0",
            requires=[
                Require(Autoconf, "2.71"),
                Require(Bison, "3.8"),
                Require(GCC, "13.1.0"),
                Require(Flex, "2.6.4"),
                Require(GPerf, "3.1"),
            ],
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.installer("IVerilog")
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum.replace(".", "_")
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/steveicarus/iverilog/archive/refs/tags/v{vernum}.tar.gz",
            f"tar -xf v{vernum}.tar.gz",
            f"cd iverilog-{vernum}",
            "autoconf",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf iverilog-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class Verilator(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "verilator" / "5.014",
            version="5.014",
            env={
                "VERILATOR_BIN": "../../bin/verilator_bin",
                "VERILATOR_ROOT": Tool.CNTR_ROOT / "share" / "verilator",
            },
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            requires=[
                Require(Autoconf, "2.71"),
                Require(Bison, "3.8"),
                Require(CCache, "4.8.2"),
                Require(GCC, "13.1.0"),
                Require(Flex, "2.6.4"),
                Require(Help2Man, "1.49.3"),
            ],
            default=True,
        ),
    ]

    @Tool.action("Verilator")
    def run(self, ctx: Context, *args: list[str]) -> Invocation:
        return Invocation(version=self, execute="verilator", args=args)

    @Tool.installer("Verilator")
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/verilator/verilator/archive/refs/tags/v{vernum}.tar.gz",
            f"tar -xf v{vernum}.tar.gz",
            f"cd verilator-{vernum}",
            "autoconf",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            f"rm -rf verilator-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )
