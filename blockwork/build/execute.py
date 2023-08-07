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
from collections import defaultdict
from pathlib import Path

from ..context import Context
from .entity import Entity
from .file import FileType
from ..foundation import Foundation
from .orchestrate import Graph
from ..tools import Invocation


class ExecutionError(Exception):
    pass


def execute(ctx : Context, entity : Entity, graph : Graph) -> None:
    """
    Execute a pre-computed build graph using transforms to produce either final
    or intermediary files.

    :param ctx:     Workspace context
    :param graph:   The build graph to execute
    """
    # Keep track of available files
    # NOTE: Index is tracked to maintain order even when files are transformed
    files = defaultdict(list)
    for idx, edge in enumerate(graph.origin.outputs):
        files[edge.filetype].append((idx, edge.file))
    # Pipeline nodes
    logging.info(f"Pipelining {len(graph.nodes)} nodes:")
    for idx, nodes in enumerate(graph.pipeline()):
        logging.info(f"|-> Step {idx}: {', '.join(x.fullname for x in nodes)}")
        for node in nodes:
            # Create a container instance
            container = Foundation(
                ctx,
                hostname=f"{ctx.config.project}_{entity.name}_{node.transform.name}"
            )
            # Bind all requested tools
            for tool in node.transform.tools:
                container.add_tool(tool().default)
            # Iterate through request extensions
            inputs = defaultdict(list)
            for in_type in node.transform.inputs:
                # Map to container and create binds
                for _, h_path in files[in_type]:
                    c_path = ctx.map_to_container(h_path)
                    inputs[in_type.extension].append(c_path)
                    container.bind_readonly(h_path, c_path)
            # Evaluate the transform and collect invocations and outputs
            invocations = []
            for obj in node.transform(ctx, entity, inputs):
                if isinstance(obj, Invocation):
                    invocations.append(obj)
                elif isinstance(obj, Path):
                    # Map container path back to the host
                    c_path = obj
                    h_path = ctx.map_to_host(c_path)
                    # Bind this path so the container may write it
                    container.bind(h_path.parent, c_path.parent, readonly=False, mkdir=True)
                    # Figure out the file type
                    f_type = FileType.from_path(c_path)
                    # Add this output to the right file category
                    # TODO: This should be re-using the index from the input but
                    #       that means finding a way to link the two together
                    files[f_type].append((len(files[f_type]), h_path))
                else:
                    raise ExecutionError(
                        f"Unexpected yield from '{node.tranform.name}': {obj}"
                    )
            # Execute each invocation within the container
            for invocation in invocations:
                exit_code = container.invoke(ctx, invocation)
                if exit_code != 0:
                    args = invocation.map_args_to_container(ctx)
                    raise ExecutionError(
                        f"Transformation '{node.transform.name}' failed with "
                        f"exit code {exit_code} following invocation: "
                        f"{invocation.execute} {' '.join(map(str, args))}"
                    )
