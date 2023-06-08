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

from ..foundation import Foundation
from ..tools import Tool

@click.command()
@click.option("--tool", "-t", type=str, multiple=True, default=[], 
              help="Bind specific tools into the shell, if omitted then all known "
                   "tools will be bound. Either use the form '--tool <NAME>' or "
                   "'--tool <NAME>=<VERSION>' where a specific version other than "
                   "the default is desired. To specify a vendor use the form "
                   "'--tool <VENDOR>:<NAME>(=<VERSION>)'.")
@click.option("--no-tools", is_flag=True, default=False, 
              help="Do not bind any tools by default into the container")
@click.pass_context
def shell(ctx, tool, no_tools):
    container = Foundation()
    container.bind(ctx.obj.root, Path("/bw/project"), False)
    # If no tools specified and auto-binding is not disabled, bind all default 
    # tool versions
    if not tool and not no_tools:
        logging.info("Binding all tools into shell")
        for tool in ctx.obj.registry:
            container.add_tool(tool)
    # Bind selected tools
    elif tool:
        for selection in tool:
            fullname, version, *_ = (selection + "=").split("=")
            vendor, name = (Tool.NO_VENDOR + ":" + fullname).split(":")[-2:]
            matched = ctx.obj.registry.get(vendor, name, version or None)
            if not matched:
                raise Exception(f"Failed to identify tool '{selection}'")
            logging.info(f"Binding tool {name} from {vendor} version {version} into shell")
            container.add_tool(matched)
    container.shell(workdir=Path("/bw/project"), show_detach=False)