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

import logging
from pathlib import Path

import click
from rich.logging import RichHandler

from .activities import info, shell, tools
from .context import Context

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, tracebacks_show_locals=True)]
)

@click.group()
@click.pass_context
@click.option("--cwd", "-C", 
              type=click.Path(exists=True, file_okay=False), 
              default=None,
              help="Override the working directory")
def blockwork(ctx, cwd):
    # Create the context object and attach to click
    ctx.obj = Context(root=Path(cwd).absolute() if cwd else None)

blockwork.add_command(info)
blockwork.add_command(shell)
blockwork.add_command(tools)

if __name__ == "__main__":
    blockwork()
