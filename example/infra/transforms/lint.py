from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, List, Union

from blockwork.build import Transform
from blockwork.tools import Invocation, Version

from infra.tools.simulators import Verilator

@Transform.register()
@Transform.tool(Verilator)
@Transform.input(".sv")
def verilator_lint(tools    : SimpleNamespace,
                   inputs   : SimpleNamespace,
                   out_dirx : Path) -> Iterable[Union[Invocation, Path]]:
    yield tools.verilator.get_action("run")(
        "--lint-only",
        "-Wall",
        *inputs.sv
    )
