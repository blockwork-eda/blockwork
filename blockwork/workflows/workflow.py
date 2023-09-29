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

from ..common.inithooks import InitHooks
import click
import logging
from pathlib import Path
from typing import Iterable, cast

from ..config.scheduler import Scheduler
from ..config import parsers

from ..context import Context

from ..build.interface import Interface

from ..build.transform import Transform
from ..config import base
from ..activities.workflow import wf


@InitHooks()
class Workflow:
    """Base class for workflows"""

    # Tool root locator
    ROOT : Path = Path("/__tool_root__")

    # Config types this workflow uses
    SITE_TYPE = base.Site
    PROJECT_TYPE = base.Project
    TARGET_TYPE = base.Element

    def __init__(self, ctx: Context, project: str, target: str, **options) -> None:
        self.ctx = ctx

        site_parser = parsers.Site(ctx)
        site_path = ctx.site
        self.site = site_parser(self.SITE_TYPE).parse(site_path)

        project_parser = parsers.Project(ctx, self.site)
        project_path = Path(self.site.projects[project])
        self.project = project_parser(self.PROJECT_TYPE).parse(project_path)

        target_parser = parsers.Element(ctx, self.site, self.project)
        self.target = target_parser.parse_target(target, self.TARGET_TYPE)

        self.workflow_options = options

    @staticmethod
    def register():
        def inner(workflow: "Workflow") -> "Workflow":
            # This registers the workflow as a subcommand with default options
            workflow = click.pass_obj(workflow)
            wf_command = click.command(workflow)
            wf_command = click.option('--project', '-p', type=str, required=True)(wf_command)
            wf_command = click.option('--target', '-t', type=str, required=True)(wf_command)
            wf.add_command(wf_command, name=workflow.__name__.lower())
            return wf_command
        return inner

    def depth_first_elements(self, element: base.Element) -> Iterable[base.Element]:
        'Recures elements and yields depths first'
        for sub_element in element.iter_elements():
            yield from self.depth_first_elements(sub_element)
        yield element

    # Note this is run as a post-init hook so subclasses can add attributes
    # after the init by overriding the method but before the run.
    @InitHooks.post
    def run(self):
        """
        Run every transform from the configuration.

        @ed.kotarski: This is a temporary implementation that I
                      intend to change soon
        """
        # Join interfaces together and get transform dependencies
        output_interfaces: list[Interface] = []
        element_transforms: list[tuple[base.Element, Transform]] = []
        dependency_map: dict[Transform, set[Transform]] = {}
        for element in self.depth_first_elements(self.target):
            for transform in element.iter_transforms():
                element_transforms.append((element, transform))
                dependency_map[transform] = set()
                for interface in transform.output_interfaces.values():
                    output_interfaces.append(interface)

        # We only need to look at output interfaces since an output must
        # exist in order for a dependency to exist
        for interface in output_interfaces:
            input_transform = cast(Transform, interface.input_transform)
            for output_transform in interface.output_transforms:
                dependency_map[output_transform].add(input_transform)

        # Use the filters to pick out targets
        targets = (t for e,t in element_transforms if self.transform_filter(t, e, **self.workflow_options))

        # Run everything in order serially
        scheduler = Scheduler(dependency_map, targets=targets)
        while scheduler.incomplete:
            for element in scheduler.schedulable:
                scheduler.schedule(element)
                # Note this message is info for now for demonstrative purposes only
                logging.info("Running transform: %s", element)
                element.run(self.ctx)
                scheduler.finish(element)

    def transform_filter(self, transform: Transform, element: base.Element) -> bool:
        'Return true for transforms that this workflow is interested in'
        raise NotImplementedError
