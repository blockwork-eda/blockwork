from pathlib import Path
from typing import List

from blockwork.tools import Invocation, Tool, Version

from .common import TOOL_ROOT

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
        Version(location = TOOL_ROOT / "verilator" / "v4.106",
                version  = "4.106",
                env      = { "VERILATOR_ROOT": Tool.ROOT },
                paths    = { "PATH": [Tool.ROOT / "bin"] },
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
