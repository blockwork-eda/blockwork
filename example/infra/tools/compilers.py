from pathlib import Path

from blockwork.tools import Tool, Version

from .common import TOOL_ROOT

class GCC(Tool):
    versions = [
        Version(location = TOOL_ROOT / "gcc" / "13.1.0",
                version  = "13.1.0",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = True),
    ]
