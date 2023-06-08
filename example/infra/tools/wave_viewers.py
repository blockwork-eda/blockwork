from pathlib import Path

from blockwork.tools import Tool, Version

tool_root = Path(__file__).absolute().parent.parent.parent.parent / "tools"

class GTKWave(Tool):
    versions = [
        Version(location = tool_root / "gtkwave" / "v3.3.113",
                version  = "3.3.113",
                paths    = { "PATH": [Tool.TOOL_ROOT / "src"] },
                default  = True),
    ]
