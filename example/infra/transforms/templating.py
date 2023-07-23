from pathlib import Path
from typing import Callable, List

from blockwork.build import input, output, transform, tool
from blockwork.tools import Version

from infra.tools.misc import PythonSite

@transform()
@tool(PythonSite)
@input("sv_mako")
@output("sv")
def mako(tool : Version, inputs : List[Path], output : Callable):
    pass
