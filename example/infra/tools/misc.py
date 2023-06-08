from pathlib import Path

from blockwork.tools import Tool, Version

tool_root = Path(__file__).absolute().parent.parent.parent.parent / "tools"

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
