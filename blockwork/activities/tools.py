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

from typing import List

import click
from rich.console import Console
from rich.table import Table

from .common import BwExecCommand
from ..context import Context
from ..foundation import Foundation

@click.command()
@click.pass_obj
def tools(ctx : Context):
    """ Tabulate all of the available tools """
    table = Table()
    table.add_column("Vendor")
    table.add_column("Tool")
    table.add_column("Version")
    table.add_column("Default")
    for tool in ctx.registry:
        for idx, version in enumerate(tool):
            table.add_row(
                tool.vendor if idx == 0 else "",
                tool.name   if idx == 0 else "",
                version.version,
                ["", ":heavy_check_mark:"][version.default]
            )
    Console().print(table)

@click.command()
@click.argument("tool", type=str)
@click.argument("action", type=str, default="default")
@click.argument("runargs", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def tool(ctx : Context,
         tool : str,
         action : str,
         runargs : List[str]) -> None:
    """ Run an action defined by a specific tool """
    # Find the tool
    vendor, name, version = BwExecCommand.decode_tool(tool)
    if (tool_ver := ctx.registry.get(vendor, name, version)) is None:
        raise Exception(f"Cannot locate tool for {tool}")
    # See if there is an action registered
    if (act_def := tool_ver.get_action(action)) is None:
        raise Exception(f"No action known for '{action}' on tool {tool}")
    # Run the action
    container = Foundation(hostname=f"{ctx.config.project}_{tool}_{action}")
    container.invoke(act_def(*runargs))
