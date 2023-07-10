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
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from .activities import activities
from .context import Context
from .containers.runtime import Runtime

VERBOSE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True,
                          tracebacks_show_locals=True,
                          show_path=False)]
)

@click.group()
@click.pass_context
@click.option("--cwd", "-C",
              type=click.Path(exists=True, file_okay=False),
              default=None,
              help="Override the working directory")
@click.option("--verbose", "-v",
              is_flag=True,
              default=False,
              help="Raise the verbosity of messages to debug")
@click.option("--quiet", "-q",
              is_flag=True,
              default=False,
              help="Lower the verbosity of messages to warning")
@click.option("--runtime", "-r",
              type=str,
              default=None,
              help="Set a specific container runtime to use")
def blockwork(ctx, cwd : str, verbose : bool, quiet : bool, runtime : str) -> None:
    global VERBOSE
    # Setup the verbosity
    if verbose:
        logging.info("Setting logging verbosity to DEBUG")
        logging.getLogger().setLevel(logging.DEBUG)
        VERBOSE = True
    elif quiet:
        logging.getLogger().setLevel(logging.WARNING)
    # Set a preferred runtime, if provided
    if runtime:
        Runtime.set_preferred_runtime(runtime)
    # Create the context object and attach to click
    ctx.obj = Context(root=Path(cwd).absolute() if cwd else None)

for activity in activities:
    blockwork.add_command(activity)

def main():
    global VERBOSE
    try:
        blockwork()
        sys.exit(0)
    except Exception as e:
        if type(e) is not Exception:
            logging.error(f"{type(e).__name__}: {e}")
        else:
            logging.error(str(e))
        if VERBOSE:
            Console().print_exception(show_locals=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
