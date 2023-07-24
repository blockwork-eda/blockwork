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
        files[edge.filetype].append((idx, edge))
    # Pipeline nodes
    logging.debug(f"Pipelining {len(graph.nodes)} nodes:")
    for idx, nodes in enumerate(graph.pipeline()):
        logging.debug(f"|-> Step {idx}: {', '.join(x.fullname for x in nodes)}")
        for node in nodes:
            inputs      = { x.extension: [x[1].file for x in files[x]] for x in node.transform.inputs }
            invocations = []
            outputs     = []
            for obj in node.transform(ctx, entity, inputs):
                if isinstance(obj, Invocation):
                    invocations.append(obj)
                elif isinstance(obj, Path):
                    # TODO: This should be re-using the index from the input but
                    #       that means finding a way to link the two together
                    cat = files[FileType.from_path(obj)]
                    cat.append((len(cat), obj))
                    outputs.append(obj)
                else:
                    raise ExecutionError(f"Unexpected yield from '{node.tranform.name}': {obj}")
            container = Foundation(
                ctx,
                hostname=f"{ctx.config.project}_{entity.name}_{node.transform.name}"
            )
            for invocation in invocations:
                container.invoke(ctx, invocation)
            breakpoint()
