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

import json
import logging
from pathlib import Path

import click

from ..build.caching import BWFrozenHash, Cache
from ..context import Context
from ..transforms.transform import SerialTransform, Transform


@click.group(name="wf")
def wf() -> None:
    """
    Workflow argument group.

    In the future we may want to add common options such as --dryrun here
    """
    pass


@click.command(name="_wf_step", hidden=True)
@click.argument("spec_path", type=click.Path(dir_okay=False, exists=True, path_type=Path))
@click.argument("input_hash", type=click.STRING)
@click.option("--target", is_flag=True, default=False)
@click.pass_obj
def wf_step(ctx: Context, spec_path: Path, input_hash: str, target: bool):
    """
    Loads a serialised transform specification from a provided file path, then
    resolves the transform class and executes it. This should NOT be called
    directly but instead as part of a wider workflow.
    """
    # TODO @intuity: We should consider making wf_step part of non-parallel
    #                executions so that there is a single execution path
    # Reload the serialised workflow step specification
    spec: SerialTransform = json.loads(spec_path.read_text(encoding="utf-8"))
    # Load the relevant transform
    transform = Transform.deserialize(spec, BWFrozenHash(spec["name"], bytes.fromhex(input_hash)))

    is_caching = Cache.enabled(ctx)

    if (
        is_caching
        and (ctx.cache_targets or not target)
        and Cache.fetch_transform_from_any(ctx, transform)
    ):
        logging.info("Fetched transform from cache: %s (late)", transform)
    else:
        logging.info("Running transform: %s", transform)
        result = transform.run(ctx)

        # Whether a cache is in place
        if is_caching and Cache.store_transform_to_any(ctx, transform, result.run_time):
            logging.info("Stored transform to cache: %s", transform)
