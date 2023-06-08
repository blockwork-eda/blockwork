from pathlib import Path

from blockwork.tools import Tool, Version

tool_root = Path(__file__).absolute().parent.parent / "tools"

class GTKWave(Tool):
    versions = [
        Version(location = tool_root / "gtkwave" / "v3.3.113",
                version  = "3.3.113",
                paths    = { "PATH": [Tool.TOOL_ROOT / "src"] },
                default  = True),
    ]

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

class Python(Tool):
    versions = [
        Version(location = tool_root / "python" / "3.11.3",
                version  = "3.11.3",
                paths    = { "PATH"           : [Tool.TOOL_ROOT / "bin"],
                             "LD_LIBRARY_PATH": [Tool.TOOL_ROOT / "lib"] },
                default  = True),
    ]

class PythonSite(Tool):
    versions = [
        Version(location = tool_root / "python-site" / "3.11.3",
                version  = "3.11.3",
                env      = { "PYTHONUSERBASE": Tool.TOOL_ROOT },
                paths    = { "PATH"      : [Tool.TOOL_ROOT / "bin"],
                             "PYTHONPATH": [Tool.TOOL_ROOT / "lib" / "python3.11" / "site-packages"] },
                default  = True),
    ]

class GCC(Tool):
    versions = [
        Version(location = tool_root / "gcc" / "13.1.0",
                version  = "13.1.0",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = True),
    ]

class Make(Tool):
    versions = [
        Version(location = tool_root / "make" / "4.4",
                version  = "4.4",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = True),
        Version(location = tool_root / "make" / "4.4",
                version  = "4.3",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = False),
    ]
