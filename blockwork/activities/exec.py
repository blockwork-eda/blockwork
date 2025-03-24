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
from pathlib import Path

import click

from ..context import Context
from ..foundation import Foundation
from ..tools import ToolMode
from .common import BwExecCommand


@click.command(cls=BwExecCommand)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    default=False,
    help="Make the shell interactive (attaches a TTY)",
)
@click.option(
    "--cwd",
    type=str,
    default=None,
    help="Set the working directory within the container",
)
@click.argument("runargs", nargs=-1, type=click.UNPROCESSED)
@click.pass_obj
def exec(  # noqa: A001
    ctx: Context,
    tool: list[str],
    no_tools: bool,
    tool_mode: str,
    interactive: bool,
    cwd: str,
    runargs: list[str],
) -> None:
    """Run a command within the container environment"""
    container = Foundation(ctx, hostname=f"{ctx.config.project}_run")
    container.bind(ctx.host_root, ctx.container_root, False)
    BwExecCommand.bind_tools(container, no_tools, tool, ToolMode(tool_mode))
    # Execute and forward the exit code
    sys.exit(
        container.launch(
            *runargs,
            workdir=Path(cwd) if cwd else ctx.container_root,
            interactive=interactive,
            display=True,
            show_detach=False,
        ).exit_code
    )
