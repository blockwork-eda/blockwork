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

from .common import BwExecCommand
from ..context import Context
from ..foundation import Foundation

@click.command(cls=BwExecCommand)
@click.pass_obj
def shell(ctx : Context, tool, no_tools):
    """ Launch a shell within the container environment """
    container = Foundation(ctx, hostname=f"{ctx.config.project}_shell")
    container.bind(ctx.host_root, ctx.container_root, False)
    BwExecCommand.bind_tools(ctx.registry, container, no_tools, tool)
    # Launch the shell and forward the exit code
    sys.exit(container.shell(workdir=ctx.container_root, show_detach=False))
