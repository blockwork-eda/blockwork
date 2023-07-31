from blockwork.tools import Require, Tool, Version

from .common import TOOL_ROOT

class Python(Tool):
    versions = [
        Version(location = TOOL_ROOT / "python" / "3.11.3",
                version  = "3.11.3",
                paths    = { "PATH"           : [Tool.TOOL_ROOT / "bin"],
                             "LD_LIBRARY_PATH": [Tool.TOOL_ROOT / "lib"] },
                default  = True),
    ]

class PythonSite(Tool):
    versions = [
        Version(location = TOOL_ROOT / "python-site" / "3.11.3",
                version  = "3.11.3",
                env      = { "PYTHONUSERBASE": Tool.TOOL_ROOT },
                paths    = { "PATH"      : [Tool.TOOL_ROOT / "bin"],
                             "PYTHONPATH": [Tool.TOOL_ROOT / "lib" / "python3.11" / "site-packages"] },
                requires = [Require(Python, "3.11.3")],
                default  = True),
    ]

class Make(Tool):
    versions = [
        Version(location = TOOL_ROOT / "make" / "4.4",
                version  = "4.4",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = True),
        Version(location = TOOL_ROOT / "make" / "4.4",
                version  = "4.3",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = False),
    ]
