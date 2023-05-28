from pathlib import Path

from blockwork.foundation import Foundation
from blockwork.tools import Tool

class Python(Tool):
    location = Path("/Users/peterbirch/Library/Caches/pypoetry/virtualenvs/blockwork-174y0VXa-py3.11")
    vendor   = "python"
    version  = "3.11"
    env      = { "PY_VER": "3.11" }
    paths    = [Tool.TOOL_ROOT / "bin"]

container = Foundation()
container.set_env("TEST", "VALUE_123")
container.add_tool(Python())

# Launch an interactive shell
container.shell()
