from pathlib import Path
from typing import List

from blockwork.tools import Invocation, Require, Tool, Version

from .common import TOOL_ROOT
from .compilers import Help2Man, Autoconf, Flex, Bison, CCache

@Tool.register()
class IVerilog(Tool):
    versions = [
        Version(location = TOOL_ROOT / "iverilog" / "v11.0",
                version  = "11.0",
                paths    = { "PATH": [Tool.ROOT / "build" / "bin"] },
                default  = True),
    ]

@Tool.register()
class Verilator(Tool):
    versions = [
        Version(location = TOOL_ROOT / "verilator" / "5.014",
                version  = "5.014",
                env      = { "VERILATOR_ROOT": Tool.ROOT },
                paths    = { "PATH": [Tool.ROOT / "bin"] },
                requires = [Require(Help2Man, "1.49.3"),
                            Require(Autoconf, "2.71"),
                            Require(Flex,     "2.6.4"),
                            Require(Bison,    "3.8"),
                            Require(CCache,   "4.8.2")],
                default  = True),
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
            f"rm -rf verilator-{vernum} ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir,
        )
