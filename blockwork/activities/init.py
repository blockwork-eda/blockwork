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

import shutil
import subprocess
from pathlib import Path

import click

from ..config import Blockwork, BlockworkParser


@click.command()
def init() -> None:
    root: Path = click.prompt("Root directory", default=Path.cwd(), type=Path)
    site: str = click.prompt(
        "Site name (typically same as repository name)", default=root.name or "site"
    )
    host_tools: str = click.prompt("Tool install path", default="../{site}.tools")
    host_state: str = click.prompt("State tracking path", default="../{site}.state")
    host_scratch: str = click.prompt("Scratch path", default="../{site}.scratch")

    cfg = Blockwork(
        site=site,
        host_tools=host_tools,
        host_state=host_state,
        host_scratch=host_scratch,
    )

    if click.confirm("Create an example project (recommended)?", default=True):
        source_root = Path(__file__).parent.parent.parent / "examples" / "hello"
        shutil.copytree(source_root, root, dirs_exist_ok=True)

        source_cfg = BlockworkParser.parse(source_root / ".bw.yaml")
        cfg.projects = source_cfg.projects
        cfg.tooldefs = source_cfg.tooldefs
        cfg.workflows = source_cfg.workflows
        cfg.config = source_cfg.config

        if click.confirm("Install tools with '$ bw bootstrap' now?", default=True):
            subprocess.run(["bw", "bootstrap"], cwd=root)
            click.echo("Next...")
            click.echo("2) Run '$ bw wf run -t hello -p v0' to run the example")
        else:
            click.echo("Next steps...")
            click.echo("1) Run '$ bw bootstrap' to install the project tools")
            click.echo("2) Run '$ bw wf run -t hello -p v0' to run the example")

    BlockworkParser.dump(cfg, root / ".bw.yaml")
