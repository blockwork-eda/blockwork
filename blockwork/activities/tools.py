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

import click
from rich.console import Console
from rich.table import Table

@click.command()
@click.pass_context
def tools(ctx):
    """ Tabulate all of the available tools """
    table = Table()
    table.add_column("Vendor")
    table.add_column("Tool")
    table.add_column("Version")
    table.add_column("Default")
    for tool in ctx.obj.registry:
        for idx, version in enumerate(tool):
            table.add_row(
                tool.vendor if idx == 0 else "",
                tool.name   if idx == 0 else "",
                version.version,
                ["", ":heavy_check_mark:"][version.default]
            )
    Console().print(table)
