from pathlib import Path
from typing import List

from blockwork.tools import Invocation, Require, Tool, Version

from .common import TOOL_ROOT
from .compilers import Autoconf, Bison, CCache, GCC, GPerf, Help2Man, Flex

@Tool.register()
class IVerilog(Tool):
    versions = [
        Version(location = TOOL_ROOT / "iverilog" / "12.0",
                version  = "12.0",
                requires = [Require(Autoconf, "2.71"),
                            Require(Bison,    "3.8"),
                            Require(GCC,      "13.1.0"),
                            Require(Flex,     "2.6.4"),
                            Require(GPerf,    "3.1")],
                paths    = { "PATH": [Tool.ROOT / "bin"] },
                default  = True),
    ]

    @Tool.action("IVerilog")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        vernum = version.version.replace(".", "_")
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://github.com/steveicarus/iverilog/archive/refs/tags/v{vernum}.tar.gz",
            f"tar -xf v{vernum}.tar.gz",
            f"cd iverilog-{vernum}",
            "autoconf",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf iverilog-{vernum} ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )


@Tool.register()
class Verilator(Tool):
    versions = [
        Version(location = TOOL_ROOT / "verilator" / "5.014",
                version  = "5.014",
                env      = { "VERILATOR_ROOT": Tool.ROOT },
                paths    = { "PATH": [Tool.ROOT / "bin"] },
                requires = [Require(Autoconf, "2.71"),
                            Require(Bison,    "3.8"),
                            Require(CCache,   "4.8.2"),
                            Require(GCC,      "13.1.0"),
                            Require(Flex,     "2.6.4"),
                            Require(Help2Man, "1.49.3")],
                default  = True),
        Version(location = TOOL_ROOT / "verilator" / "v4.106",
                version  = "4.106",
                env      = { "VERILATOR_ROOT": Tool.ROOT },
                paths    = { "PATH": [Tool.ROOT / "bin"] },
                default  = False),
    ]

    @Tool.action("Verilator")
    def run(self,
            version : Version,
            *args   : List[str]) -> Invocation:
        return Invocation(
            version = version,
            execute = "verilator",
            args    = args
        )

    @Tool.action("Verilator")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://github.com/verilator/verilator/archive/refs/tags/v{vernum}.tar.gz",
            f"tar -xf v{vernum}.tar.gz",
            f"cd verilator-{vernum}",
            "autoconf",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            f"rm -rf verilator-{vernum} ./*.tar.*",
            "cp -r share/verilator/include include"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir,
        )
