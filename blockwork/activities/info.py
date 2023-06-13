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

from ..context import Context

@click.command()
@click.pass_obj
def info(ctx : Context):
    """ List information about the project """
    table = Table(show_header=False)
    table.add_row("Project", ctx.config.project)
    table.add_row("Host Root Directory", ctx.host_root.as_posix())
    table.add_row("Container Root Directory", ctx.container_root.as_posix())
    table.add_row("Configuration File", ctx.config_path.as_posix())
    Console().print(table)
