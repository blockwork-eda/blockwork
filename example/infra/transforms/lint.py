from pathlib import Path
from typing import Callable, List

from blockwork.build import input, output, transform, tool
from blockwork.tools import Version

from infra.tools.simulators import Verilator

@transform()
@tool(Verilator)
@input("sv")
@output("lint_report")
def mako(tool : Version, inputs : List[Path], output : Callable):
    pass
