from datetime import datetime
from pathlib import Path

from blockwork.bootstrap import Bootstrap
from blockwork.context import Context
from blockwork.foundation import Foundation

from ..tools.common import TOOL_ROOT
from ..tools.misc import Python, PythonSite


@Bootstrap.register(check_point=Path("infra/tools/pythonsite.txt"))
def setup_pythonsite(context : Context, last_run : datetime) -> bool:
    # Get default versions of tools
    python = Python().default
    python_site = PythonSite().default
    # Create the directories for the Python site installation
    site_root = python_site.location
    site_root.mkdir(parents=True, exist_ok=True)
    # Create a container instance and install all requirements
    container = Foundation(context, hostname=f"{context.config.project}_pythonsite")
    container.add_tool(python, readonly=True)
    container.add_tool(python_site, readonly=False)
    container.bind(context.host_root / "infra" / "tools" / "pythonsite.txt",
                   Path("/") / "project" / "pythonsite.txt")
    container.launch(
        "python3",
        "-m",
        "pip",
        "--no-cache-dir",
        "install",
        "-r",
        "/project/pythonsite.txt",
        interactive=True,
        show_detach=False
    )
