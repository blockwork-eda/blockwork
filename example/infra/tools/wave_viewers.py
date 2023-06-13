from pathlib import Path
from typing import List

from blockwork.tools import Invocation, Tool, Version

tool_root = Path(__file__).absolute().parent.parent.parent.parent / "tools"

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
        h_path = Path(wavefile).absolute()
        c_path = Path("/bw/project") / h_path.name
        return Invocation(
            version = version,
            workdir = c_path.parent,
            execute = Tool.TOOL_ROOT / "src" / "gtkwave",
            args    = [c_path.name, *args],
            display = True,
            binds   = [(h_path.parent, c_path.parent)]
        )
