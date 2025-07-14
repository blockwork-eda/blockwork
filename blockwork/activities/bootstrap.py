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

from ..bootstrap import Bootstrap, BwBootstrapMode
from ..context import Context


@click.command()
@click.option("--execute", "action", flag_value="execute", default=True)
@click.option("--list-only", "action", flag_value="list")
@click.option(
    "--mode",
    type=click.Choice(BwBootstrapMode, case_sensitive=False),
    default="default",
    help="""Set the bootstrap mode.
                          default: Rebuild out of date steps
                          force: Rebuild all steps
                   """,
)
@click.argument("steps", nargs=-1, type=str, required=False, default=None)
@click.pass_obj
def bootstrap(ctx: Context, action: str, mode: str, steps: list[str] | None) -> None:
    """Run all bootstrapping actions"""
    mode: BwBootstrapMode = getattr(BwBootstrapMode, mode)
    logging.info(f"Importing {len(ctx.config.bootstrap)} bootstrapping paths")
    Bootstrap.setup(ctx.host_root, ctx.config.bootstrap)
    match action:
        case "execute":
            if steps:
                for name in filter(lambda x: x in steps, Bootstrap.get_all().keys()):
                    logging.info(f"Invoking bootstrap step: {name}")
                    Bootstrap.evaluate(name, context=ctx, mode=mode)
            else:
                logging.info(f"Invoking {len(Bootstrap.get_all())} bootstrap steps")
                Bootstrap.evaluate_all(ctx, mode=mode)
            logging.info("Bootstrap complete")
        case "list":
            logging.info(f"Listing {len(Bootstrap.get_all())} bootstrap steps")
            for name in Bootstrap.get_all().keys():
                logging.info(f" - {name}")
