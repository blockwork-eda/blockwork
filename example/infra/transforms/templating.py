from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Union
from blockwork.config import registry
from blockwork.config.parser import ElementConverter
from blockwork.common.checkeddataclasses import dataclass
from blockwork.config import base
from blockwork.build import Transform
from blockwork.context import Context
from blockwork.tools.tool import Invocation
from infra.tools.misc import PythonSite


@registry.element.register(ElementConverter)
@dataclass(kw_only=True)
class Mako(base.Transform):
    template: str
    output: str

    def resolve_input_paths(self, resolve):
        self.template = resolve(self.template)

    def resolve_output_paths(self, resolved):
        self.output = resolved(self.output)


    @Transform.register("mako")
    @Transform.tool(PythonSite)
    @Transform.input(".sv.mako")
    @Transform.output(".sv")
    @staticmethod
    def exec(ctx      : Context,
             tools    : SimpleNamespace,
             inputs   : SimpleNamespace,
             out_dirx : Path) -> Iterable[Union[Invocation, Path]]:
        assert len(inputs.sv_mako) == 1
        tmpl  = inputs.sv_mako[0]
        fname = tmpl.name.rstrip(".mako")
        cmd  = "from mako.template import Template;"
        cmd += f"fh = open('{out_dirx / fname}', 'w');"
        cmd += f"fh.write(Template(filename='{tmpl}').render());"
        cmd += "fh.flush();"
        cmd += "fh.close()"
        yield tools.pythonsite.get_action("run")(ctx, "-c", cmd)
        yield out_dirx / fname
