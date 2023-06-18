from pathlib import Path

from blockwork.tools import Tool, Version

tool_root = Path(__file__).absolute().parent.parent.parent.parent / "example.tools"

class IVerilog(Tool):
    versions = [
        Version(location = tool_root / "iverilog" / "v11.0",
                version  = "11.0",
                paths    = { "PATH": [Tool.TOOL_ROOT / "build" / "bin"] },
                default  = True),
    ]

class Verilator(Tool):
    versions = [
        Version(location = tool_root / "verilator" / "v4.106",
                version  = "4.106",
                env      = { "VERILATOR_ROOT": Tool.TOOL_ROOT },
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = True),
    ]
