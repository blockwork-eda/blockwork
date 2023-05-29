from pathlib import Path

from blockwork.foundation import Foundation
from blockwork.tools import Tool

tool_root = Path(__file__).absolute().parent / "tools"

class GTKWave(Tool):
    location = tool_root / "gtkwave" / "v3.3.113"
    version  = "3.3.113"
    paths    = { "PATH": [Tool.TOOL_ROOT / "src"] }

class IVerilog(Tool):
    location = tool_root / "iverilog" / "v11.0"
    version  = "11.0"
    paths    = { "PATH": [Tool.TOOL_ROOT / "build" / "bin"] }

class Verilator(Tool):
    location = tool_root / "verilator" / "v4.106"
    version  = "4.106"
    env      = { "VERILATOR_ROOT": Tool.TOOL_ROOT }
    paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] }

class Python(Tool):
    location = tool_root / "python" / "v3.11.0"
    version  = "3.11.0"
    paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] }

container = Foundation()
container.set_env("TEST", "VALUE_123")
container.add_tool(GTKWave)
container.add_tool(IVerilog)
container.add_tool(Verilator)
container.add_tool(Python)

# Launch an interactive shell
container.shell()
