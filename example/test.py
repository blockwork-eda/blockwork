from pathlib import Path

from blockwork.foundation import Foundation
from blockwork.tools import Tool

tool_root = Path(__file__).absolute().parent.parent / "tools"

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
    location = tool_root / "python" / "3.11.3"
    version  = "3.11.3"
    paths    = { "PATH"           : [Tool.TOOL_ROOT / "bin"],
                 "LD_LIBRARY_PATH": [Tool.TOOL_ROOT / "lib"] }

class PythonSite(Tool):
    location = tool_root / "python-site" / "3.11.3"
    version  = "3.11.3"
    env      = { "PYTHONUSERBASE": Tool.TOOL_ROOT }
    paths    = { "PATH"      : [Tool.TOOL_ROOT / "bin"],
                 "PYTHONPATH": [Tool.TOOL_ROOT / "lib" / "python3.11" / "site-packages"] }

class GCC(Tool):
    location = tool_root / "gcc" / "13.1.0"
    version  = "13.1.0"
    paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] }

class Make(Tool):
    location = tool_root / "make" / "4.4"
    version  = "4.4"
    paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] }

container = Foundation()

container.set_env("TEST", "VALUE_123")

container.add_tool(GTKWave)
container.add_tool(IVerilog)
container.add_tool(Verilator)
container.add_tool(Python)
container.add_tool(PythonSite)
container.add_tool(GCC)
container.add_tool(Make)

ex_root = Path(__file__).absolute().parent

container.add_input(ex_root / "design")
container.add_input(ex_root / "bench")


# Launch an interactive shell
# container.shell()
container.launch("make", "-f", "/bw/input/bench/Makefile", "run_cocotb")
container.launch("gtkwave", "/bw/scratch/waves.vcd", display=True)

# Launch GTKWave and forward the display back to the host
# container.launch("gtkwave", display=True)
