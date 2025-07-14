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
from collections.abc import Sequence

import click
from rich.console import Console
from rich.table import Table

from ..context import Context
from ..foundation import Foundation
from ..tools import Tool
from ..tools.tool import ToolActionError
from .common import BwExecCommand


@click.command()
@click.pass_obj
def tools(ctx: Context):
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
        tool = tool_def()
        t_acts = Tool.ACTIONS.get(tool.name, {})
        actions = [(x, y) for x, y in t_acts.items() if x != "default"]
        default = t_acts.get("default", None)
        act_str = ", ".join(f"{x}{'*' if y is default else ''}" for x, y in actions)
        for idx, version in enumerate(tool):
            table.add_row(
                tool.vendor if idx == 0 else "",
                tool.name if idx == 0 else "",
                version.version,
                ["", ":heavy_check_mark:"][version.default],
                act_str if idx == 0 else "",
            )
    Console().print(table)


@click.group()
@click.option("--version", "-v", type=str, default=None, help="Set the tool version to use.")
@click.argument("tool", type=str)
@click.pass_obj
def tool(ctx: Context, version: str | None, tool: str) -> None:
    """
    Run an action defined by a specific tool. The tool and action is selected by
    the first argument either using the form <TOOL>.<ACTION> or just <TOOL>
    where the default action is acceptable.
    """
    # Find the tool
    tool = f"{tool}={version}" if version else tool
    vendor, name, version = BwExecCommand.decode_tool(tool)
    if (tool_ver := Tool.get(vendor, name, version)) is None:
        raise Exception(f"Cannot locate tool for {tool}")
    ctx.tool_ver = tool_ver


@tool.command()
@click.pass_obj
def install(ctx: Context):
    ctx.tool_ver._run_install(ctx)


@tool.command()
@click.argument("action", type=str)
@click.argument("runargs", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def run(ctx: Context, action: str, runargs: Sequence[str]):
    # See if there is an action registered
    try:
        act_def = ctx.tool_ver.get_action(action)
    except ToolActionError:
        raise Exception(f"No action known for '{action}' on tool {tool}") from None
    # Run the action and forward the exit code
    container = Foundation(ctx, hostname=f"{ctx.config.project}_{tool}_{action}")
    invocation = act_def(ctx, *runargs)
    # Actions may sometimes return null invocations if they have no work to do
    if invocation is None:
        return
    # Launch the invocation
    sys.exit(container.invoke(ctx, invocation).exit_code)
