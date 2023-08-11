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

from pathlib import Path
from typing import cast
import click

from blockwork.config import parser, base
from blockwork.workflows.workflow import Workflow

from ..context import Context

@Workflow.register()
class ex(Workflow):
    pass

@click.command(name='wf')
@click.option('--project', '-p', type=str, required=True)
@click.option('--target', '-t', type=str, required=True)
@click.argument("workflow_name", type=str)
@click.pass_obj
def workflow(ctx : Context, project: str, target: str, workflow_name: str) -> None:
    """ Run a workflow """
    workflow = cast(Workflow, Workflow.get_by_name(workflow_name))

    site_parser = parser.Site()
    site_path = ctx.site
    Site = site_parser(base.Site).parse(site_path)

    project_parser = parser.Project(Site)
    project_path = Path(Site.projects[project])
    Project = project_parser(base.Project).parse(project_path)

    target_parser = parser.Element(Site, Project)
    target_path = Path(Project.targets[target])
    Target = target_parser(base.Element).parse(target_path)
    # Config.site
    breakpoint()
