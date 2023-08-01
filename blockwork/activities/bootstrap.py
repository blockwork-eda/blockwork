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
from click.core import Command, Option

from ..bootstrap import Bootstrap, BwBootstrapMode
from ..context import Context

class BwBootstrapCommand(Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params.insert(0,
                            Option(("--mode", ),
                            type=click.Choice(BwBootstrapMode._member_names_, case_sensitive=False),
                            default="default",
                            help=f"""Set the bootstrap mode. 
                                     default: Rebuild out of date steps
                                     force: Rebuild all steps
                                  """))


@click.command(cls=BwBootstrapCommand)
@click.pass_obj
def bootstrap(ctx : Context, mode: str) -> None:
    """ Run all bootstrapping actions """
    mode: BwBootstrapMode = getattr(BwBootstrapMode, mode)
    logging.info(f"Importing {len(ctx.config.bootstrap)} bootstrapping paths")
    Bootstrap.setup(ctx.host_root, ctx.config.bootstrap)
    logging.info(f"Invoking {len(Bootstrap.REGISTERED)} bootstrap methods")
    Bootstrap.invoke(ctx, mode=mode)
    logging.info("Bootstrap complete")
