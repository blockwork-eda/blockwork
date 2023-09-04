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

from ..config import Config, parsers
from ..workflows.workflow import Workflow

from ..context import Context

@click.command(name='wf')
@click.option('--project', '-p', type=str, required=True)
@click.option('--target', '-t', type=str, required=True)
@click.argument("workflow_name", type=str)
@click.pass_obj
def workflow(ctx : Context, project: str, target: str, workflow_name: str) -> None:
    """ Run a workflow """
    wf = cast(type[Workflow], Workflow.get_by_name(workflow_name))

    site_parser = parsers.Site(ctx)
    site_path = ctx.site
    site_config = site_parser(wf.SITE_TYPE).parse(site_path)

    project_parser = parsers.Project(ctx, site_config)
    project_path = Path(site_config.projects[project])
    project_config = project_parser(wf.PROJECT_TYPE).parse(project_path)

    target_parser = parsers.Element(ctx, site_config, project_config)
    target_config = target_parser.parse_target(target, wf.TARGET_TYPE)

    config = Config(ctx=ctx, site=site_config, project=project_config, target=target_config)

    wf(config).run()
