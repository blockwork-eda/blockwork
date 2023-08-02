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
from typing import List, Optional

import click

from ..build import Entity, Transform, execute, orchestrate
from .common import BwExecCommand
from ..context import Context

@click.command(cls=BwExecCommand)
@click.option("--top", "-t", type=str, help="Top-level entity", required=True)
@click.option("--graph", "-g", "graph_path",
              type=click.Path(dir_okay=False),
              help="Path to write Graphviz DOT file")
@click.argument("transform", type=str)
@click.pass_obj
def build(ctx : Context,
          tool : List[str],
          no_tools : bool,
          tool_mode : str,
          top : str,
          graph_path : Optional[str],
          transform : str) -> None:
    """ Run a build step """
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
        with open(graph_path, "w") as fh:
            fh.write(graph.to_dot())
    # Execute the graph
    logging.debug(f"Executing the build graph of {len(graph.nodes)} nodes")
    execute(ctx, entity, graph)
