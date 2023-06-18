from pathlib import Path

from blockwork.tools import Tool, Version

tool_root = Path(__file__).absolute().parent.parent.parent.parent / "example.tools"

class GCC(Tool):
    versions = [
        Version(location = tool_root / "gcc" / "13.1.0",
                version  = "13.1.0",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = True),
    ]
