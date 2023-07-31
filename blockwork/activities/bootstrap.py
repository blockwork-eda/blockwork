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

from ..bootstrap import Bootstrap
from ..context import Context

@click.command()
@click.pass_obj
def bootstrap(ctx : Context) -> None:
    """ Run all bootstrapping actions """
    logging.info(f"Importing {len(ctx.config.bootstrap)} bootstrapping paths")
    Bootstrap.setup(ctx.host_root, ctx.config.bootstrap)
    logging.info(f"Invoking {len(Bootstrap.REGISTERED)} bootstrap methods")
    Bootstrap.invoke(ctx)
    logging.info("Bootstrap complete")