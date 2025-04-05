from pathlib import Path

from blockwork.context import Context
from blockwork.tools import Invocation
from blockwork.tools.tools import Bash
from blockwork.transforms import Transform


class BashTF(Transform):
    bash: Bash = Transform.TOOL()
    binary: Path = Transform.IN()
    workdir: Path = Transform.OUT(init=True, default=...)

    def execute(self, ctx: Context):
        yield Invocation(
            tool=self.bash,
            execute=self.binary,
            workdir=self.workdir,
            interactive=True,
        )
