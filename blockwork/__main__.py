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

import dataclasses
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from .common.registry import Registry

from .bootstrap import Bootstrap
from .activities import activities
from .activities.workflow import Workflow
from .context import Context, HostArchitecture
from .containers.runtime import Runtime
from .tools import Tool
from .common import scopes


@scopes.scope
@dataclasses.dataclass
class Verbosity:
    VERBOSE: bool = False
    VERBOSE_LOCALS: bool = False

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
@click.option("--verbose-locals",
              is_flag=True,
              default=False,
              help="Print local variables in an exception traceback")
@click.option("--quiet", "-q",
              is_flag=True,
              default=False,
              help="Lower the verbosity of messages to warning")
@click.option("--runtime", "-r",
              type=str,
              default=None,
              help="Set a specific container runtime to use")
@click.option("--arch",
              type=str,
              default=None,
              help="Override the host architecture")
def blockwork(ctx,
              cwd : str,
              verbose : bool,
              verbose_locals : bool,
              quiet : bool,
              runtime : Optional[str] = None,
              arch : Optional[str] = None) -> None:
    # Setup the verbosity
    Verbosity.current.VERBOSE = verbose
    Verbosity.current.VERBOSE_LOCALS = verbose and verbose_locals
    if verbose:
        logging.info("Setting logging verbosity to DEBUG")
        logging.getLogger().setLevel(logging.DEBUG)
    elif quiet:
        logging.getLogger().setLevel(logging.WARNING)
    # Set a preferred runtime, if provided
    if runtime:
        Runtime.set_preferred_runtime(runtime)
    # Create the context object and attach to click
    ctx.obj = Context(root=Path(cwd).absolute() if cwd else None)
    # Set the host architecture
    if arch:
        ctx.obj.host_architecture = HostArchitecture(arch)
    # Trigger registration procedures
    Tool.setup(ctx.obj.host_root, ctx.obj.config.tooldefs)
    Bootstrap.setup(ctx.obj.host_root, ctx.obj.config.bootstrap)
    Workflow.setup(ctx.obj.host_root, ctx.obj.config.workflows)
    Registry.setup(ctx.obj.host_root, ctx.obj.config.config)


for activity in activities:
    blockwork.add_command(activity)

def main():
    with Verbosity(VERBOSE=True, VERBOSE_LOCALS=True) as v:
        try:
            blockwork(auto_envvar_prefix="BW")
            sys.exit(0)
        except Exception as e:
            if type(e) is not Exception:
                logging.error(f"{type(e).__name__}: {e}")
            else:
                logging.error(str(e))
            if v.VERBOSE:
                Console().print_exception(show_locals=v.VERBOSE_LOCALS)
            sys.exit(1)

if __name__ == "__main__":
    main()
