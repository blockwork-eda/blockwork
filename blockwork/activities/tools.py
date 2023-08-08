# Copyright 2023, Blockwork, github.com/intuity/blockwork
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table

from .common import BwExecCommand, ToolMode
from ..context import Context
from ..foundation import Foundation
from ..tools import Tool

@click.command()
@click.pass_obj
def tools(ctx : Context):
    """
    Tabulate all of the available tools including vendor name, tool name, version,
    which version is default, and a list of supported actions. The default action
    will be marked with an asterisk ('*').
    """
    table = Table()
    table.add_column("Vendor")
    table.add_column("Tool")
    table.add_column("Version")
    table.add_column("Default", justify="center")
    table.add_column("Actions")
    for tool_def in Tool.get_all().values():
        tool   = tool_def()
        t_acts = Tool.ACTIONS.get(tool.name, {})
        actions = [(x, y) for x, y in t_acts.items() if x != "default"]
        default = t_acts.get("default", None)
        act_str = ", ".join(f"{x}{'*' if y is default else ''}" for x, y in actions)
        for idx, version in enumerate(tool):
            table.add_row(
                tool.vendor if idx == 0 else "",
                tool.name   if idx == 0 else "",
                version.version,
                ["", ":heavy_check_mark:"][version.default],
                act_str     if idx == 0 else "",
            )
    Console().print(table)

@click.command()
@click.option("--version", "-v",
              type=str,
              default=None,
              help="Set the tool version to use.")
@click.option("--tool-mode",
              type=click.Choice(ToolMode, case_sensitive=False),
              default="readonly",
              help="Set the file mode used when binding tools "
                   "to enable write access. Legal values are "
                   "either 'readonly' or 'readwrite', defaults "
                   "to 'readonly'.")
@click.argument("tool_action", type=str)
@click.argument("runargs", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def tool(ctx         : Context,
         version     : Optional[str],
         tool_action : str,
         tool_mode   : str,
         runargs     : List[str]) -> None:
    """
    Run an action defined by a specific tool. The tool and action is selected by
    the first argument either using the form <TOOL>.<ACTION> or just <TOOL>
    where the default action is acceptable.
    """
    # Split <TOOL>.<ACTION> or <TOOL> into parts
    base_tool, action, *_ = (tool_action + ".default").split(".")
    # Find the tool
    tool = f"{base_tool}={version}" if version else base_tool 
    vendor, name, version = BwExecCommand.decode_tool(tool)
    if (tool_ver := Tool.get(vendor, name, version)) is None:
        raise Exception(f"Cannot locate tool for {tool}")
    # See if there is an action registered
    if (act_def := tool_ver.get_action(action)) is None:
        raise Exception(f"No action known for '{action}' on tool {tool}")
    # Run the action and forward the exit code
    container = Foundation(ctx, hostname=f"{ctx.config.project}_{tool}_{action}")
    sys.exit(container.invoke(ctx,
                              act_def(*runargs),
                              readonly=(ToolMode(tool_mode) == ToolMode.READONLY)))
