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

import importlib
import json
import logging
from pathlib import Path

import click

from ..context import Context
from ..transforms.transform import Transform


@click.group(name="wf")
def wf() -> None:
    """
    Workflow argument group.

    In the future we may want to add common options such as --dryrun here
    """
    pass


@click.command(name="_wf_step", hidden=True)
@click.argument("spec_path", type=click.Path(dir_okay=False, exists=True, path_type=Path))
@click.pass_obj
def wf_step(ctx: Context, spec_path: Path):
    """
    Loads a serialised transform specification from a provided file path, then
    resolves the transform class and executes it. This should NOT be called
    directly but instead as part of a wider workflow.
    """
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    # Import the relevant transform
    mod_spec = importlib.import_module(spec["mod"])
    transform_cls: type[Transform] = getattr(mod_spec, spec["name"])
    logging.info(f"Running serialised {transform_cls.__name__}")
    transform_cls._run_serialized(ctx, spec)
