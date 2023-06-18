from pathlib import Path
from typing import List

from blockwork.tools import Invocation, Tool, Version

tool_root = Path(__file__).absolute().parent.parent.parent.parent / "example.tools"

class GTKWave(Tool):
    versions = [
        Version(location = tool_root / "gtkwave" / "v3.3.113",
                version  = "3.3.113",
                paths    = { "PATH": [Tool.TOOL_ROOT / "src"] },
                default  = True),
    ]

    @Tool.action("GTKWave", default=True)
    def view(self,
             version  : Version,
             wavefile : str,
             *args    : List[str]) -> Invocation:
        path = Path(wavefile).absolute()
        return Invocation(
            version = version,
            execute = Tool.TOOL_ROOT / "src" / "gtkwave",
            args    = [path, *args],
            display = True,
            binds   = [path.parent]
        )

    @Tool.action("GTKWave")
    def version(self,
                version : Version,
                *args   : List[str]) -> Invocation:
        return Invocation(
            version = version,
            execute = Tool.TOOL_ROOT / "src" / "gtkwave",
            args    = ["--version", *args],
            display = True,
        )
