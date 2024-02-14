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

from ..context import Context

@click.group(name='wf')
def wf() -> None:
    """
    Workflow argument group.

    In the future we may want to add common options such as --dryrun here
    """
    pass

@click.command(hidden=True)
@click.argument("step", type=click.Path(exists=True, dir_okay=False))
@click.pass_obj
def wf_step(ctx : Context, step : str) -> None:
    """ Run a step dispatched from a wider workflow """
    logging.info(f"Reading workflow step specification: {step}")
    with Path(step).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    logging.info(f"Specification: {data}")
