from pathlib import Path

from ...tools import tools
from ..transform import Transform


class Copy(Transform):
    frm: Path = Transform.IN()
    to: Path = Transform.OUT(init=True, default=...)
    tools = (tools.Bash,)

    def execute(self, ctx, tools, iface):
        yield tools.bash.get_action("cp")(ctx, frm=iface.frm, to=iface.to)
