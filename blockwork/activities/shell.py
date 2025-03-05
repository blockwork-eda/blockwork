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

import click

from ..context import Context
from ..executors import Invoker
from ..tools import ToolMode
from .common import BwExecCommand


@click.command(cls=BwExecCommand)
@click.pass_obj
def shell(
    ctx: Context,
    tool: list[str],
    no_tools: bool,
    tool_mode: str,
    invoker: type[Invoker],
):
    """Launch a shell within the container environment"""
    container = invoker(ctx)
    container.bind(ctx.host_root, ctx.container_root, False)
    BwExecCommand.bind_tools(container, no_tools, tool, ToolMode(tool_mode))
    # Launch the shell and forward the exit code
    sys.exit(container.shell(workdir=ctx.container_root, show_detach=False))
