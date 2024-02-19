from ...build.interface import FileInterface
from ...tools.tools import Bash
from ..transform import Transform


class Copy(Transform):
    def __init__(self, frm: FileInterface, to: FileInterface):
        self.bind_tools(Bash).bind_inputs(frm=frm).bind_outputs(to=to)

    def execute(self, ctx, tools, iface):
        yield tools.bash.get_action("cp")(ctx, frm=iface.frm, to=iface.to)
