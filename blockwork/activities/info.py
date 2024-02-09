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

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

import blockwork

from ..context import Context


@click.command()
@click.argument("query", nargs=-1, type=str)
@click.pass_obj
def info(ctx: Context, query: list[str]):
    """
    List information about the project, an optional list of keys may be provided
    to only print select information - for example 'bw info host_tools' will just
    show the host tools' root directory path and nothing else.
    """
    info = {
        "Project": ctx.config.project,
        "Configuration File": ctx.config_path.as_posix(),
        "Blockwork Install": Path(blockwork.__file__).parent.as_posix(),
        "Site": ctx.site.as_posix(),
        "Host Root": ctx.host_root.as_posix(),
        "Host Tools": ctx.host_tools.as_posix(),
        "Host Scratch": ctx.host_scratch.as_posix(),
        "Host State": ctx.host_state.as_posix(),
        "Container Root": ctx.container_root.as_posix(),
        "Container Tools": ctx.container_tools.as_posix(),
        "Container Scratch": ctx.container_scratch.as_posix(),
    }
    if query:
        for partial in query:
            for name, value in info.items():
                if name.lower().replace(" ", "_").startswith(partial):
                    print(value)
    else:
        table = Table(show_header=False)
        for name, value in info.items():
            table.add_row(name, value)
        Console().print(table)
