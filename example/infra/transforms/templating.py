from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Union

from blockwork.build import Transform
from blockwork.tools import Tool, Invocation

from infra.tools.misc import PythonSite

@Transform.register()
@Transform.tool(PythonSite)
@Transform.input(".sv.mako")
@Transform.output(".sv")
def mako(tools    : SimpleNamespace,
         inputs   : SimpleNamespace,
         out_dirx : Path) -> Iterable[Union[Invocation, Path]]:
    assert len(inputs.sv_mako) == 1
    tmpl  = inputs.sv_mako[0]
    fname = tmpl.name.rstrip(".mako")
    cmd  = "from mako.template import Template;"
    cmd += f"fh = open('{out_dirx / fname}', 'w');"
    cmd += f"fh.write(Template(filename='{tmpl}').render());"
    cmd += f"fh.flush();"
    cmd += f"fh.close()"
    yield tools.pythonsite.get_action("run")("-c", cmd)
    yield out_dirx / fname
