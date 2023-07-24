from typing import List

from blockwork.tools import Invocation, Require, Tool, Version

from .common import TOOL_ROOT

@Tool.register()
class Python(Tool):
    versions = [
        Version(location = TOOL_ROOT / "python" / "3.11.3",
                version  = "3.11.3",
                paths    = { "PATH"           : [Tool.ROOT / "bin"],
                             "LD_LIBRARY_PATH": [Tool.ROOT / "lib"] },
                default  = True),
    ]

@Tool.register()
class PythonSite(Tool):
    versions = [
        Version(location = TOOL_ROOT / "python-site" / "3.11.3",
                version  = "3.11.3",
                env      = { "PYTHONUSERBASE": Tool.ROOT },
                paths    = { "PATH"      : [Tool.ROOT / "bin"],
                             "PYTHONPATH": [Tool.ROOT / "lib" / "python3.11" / "site-packages"] },
                requires = [Require(Python, "3.11.3")],
                default  = True),
    ]

    @Tool.action("PythonSite")
    def run(self,
            version : Version,
            *args   : List[str]) -> Invocation:
        return Invocation(
            version = version,
            execute = "python3",
            args    = args
        )


@Tool.register()
class Make(Tool):
    versions = [
        Version(location = TOOL_ROOT / "make" / "4.4",
                version  = "4.4",
                paths    = { "PATH": [Tool.ROOT / "bin"] },
                default  = True),
        Version(location = TOOL_ROOT / "make" / "4.4",
                version  = "4.3",
                paths    = { "PATH": [Tool.ROOT / "bin"] },
                default  = False),
    ]
