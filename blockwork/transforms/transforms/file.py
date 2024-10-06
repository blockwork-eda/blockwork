from pathlib import Path

from ...tools import tools
from ..transform import Transform


class Copy(Transform):
    frm: Path = Transform.IN()
    to: Path = Transform.OUT(init=True, default=...)
    bash: tools.Bash = Transform.TOOL()

    def execute(self, ctx):
        yield self.bash.cp(ctx, frm=self.frm, to=self.to)
