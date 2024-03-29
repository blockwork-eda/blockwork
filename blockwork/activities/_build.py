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

import click

from ..build import Entity, Transform, _execute, orchestrate
from ..context import Context
from .common import BwExecCommand


@click.command(cls=BwExecCommand)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    default=False,
    help="Force all build steps to run interactively",
)
@click.option("--pre-shell", type=str, help="Open an interactive shell before a specific stage")
@click.option("--post-shell", type=str, help="Open an interactive shell after a specific stage")
@click.option("--top", "-t", type=str, help="Top-level entity", required=True)
@click.option(
    "--graph",
    "-g",
    "graph_path",
    type=click.Path(dir_okay=False),
    help="Path to write Graphviz DOT file",
)
@click.argument("transform", type=str)
@click.pass_obj
def build(
    ctx: Context,
    tool: list[str],
    no_tools: bool,
    tool_mode: str,
    interactive: bool,
    pre_shell: str,
    post_shell: str,
    top: str,
    graph_path: str | None,
    transform: str,
) -> None:
    """Run a build step"""
    del no_tools, tool_mode
    BwExecCommand.set_tool_versions(tool)
    # Locate the top-level
    logging.info(f"Locating top-level '{top}'")
    entity = Entity.get_by_name(top)()
    # Locate the transform
    logging.info(f"Locating transform '{transform}'")
    transform = Transform.get_by_name(transform)
    # Calculate the build graph
    graph = orchestrate(entity, transform)
    # If requested, write the graph to file
    if graph_path:
        logging.info(f"Writing build graph to '{graph_path}'")
        with graph_path.open("w", encoding="utf-8") as fh:
            fh.write(graph.to_dot())
    # Execute the graph
    logging.debug(f"Executing the build graph of {len(graph.nodes)} nodes")
    _execute(
        ctx,
        entity,
        graph,
        interactive=interactive,
        pre_shell=pre_shell,
        post_shell=post_shell,
    )
