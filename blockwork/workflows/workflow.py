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

from functools import partial, reduce
from ..config.base import Config, Project, Site
import click
import logging
from pathlib import Path
from typing import Callable, Iterable, Optional, cast

from ..config.scheduler import Scheduler
from ..config import parsers

from ..build.interface import Interface

from ..build.transform import Transform
from ..config import base
from ..activities.workflow import wf


class Workflow:
    '''
    Wrapper for workflow functions.

    Workflows are implemented as functions which are run from the command
    line and that return a Config object. For example::

        @Workflow("<workflow_name>")
        @click.option('--match', type=str, required=True)
        def my_workflow(ctx, match):
            return Build(match=match)

    '''

     # Type for Site object
    SITE_TYPE = Site

    def __init__(self, name: str):
        self.name = name
        self.project_type = None
        self.target_type = None

    def with_project(self, typ: Optional[type[Project]]=None):
        'Convenience method to add a --project option'
        self.project_type = typ or Project
        return self

    def with_target(self, typ: Optional[type[Config]]=None):
        'Convenience method to add --project and --target options'
        self.project_type = self.project_type or Project
        self.target_type = typ or Config
        return self

    @classmethod
    def parse_site(cls, ctx) -> Site:
        SITE_TYPE = cls.SITE_TYPE
        site_parser = parsers.Site(ctx)
        site_path = ctx.site
        return site_parser(SITE_TYPE).parse(site_path)

    @classmethod
    def parse_project(cls, ctx, site: Site, project: str, typ: type) -> Project:
        'Parse a project option using the given site'
        project_parser = parsers.Project(ctx, site)
        project_path = Path(site.projects[project])
        return project_parser(typ).parse(project_path)

    @classmethod
    def parse_target(cls, ctx, site: Site, project: Project, target:str, typ: type) -> base.Element:
        'Parse a target option using the given site and project'
        target_parser = parsers.Element(ctx, site, project)
        # If target type not provided assume we're pointing to a workflow file itself
        return target_parser.parse_target(target, typ)

    def __call__(self, fn: Callable[..., Config]) -> Callable[..., None]:

        @click.command()
        @click.pass_obj
        def command(ctx, project=None, target=None, *args, **kwargs):
            site = self.parse_site(ctx)
            if project:
                kwargs['project'] = self.parse_project(ctx, site, project, self.project_type)
                if target:
                    kwargs['target'] = self.parse_target(ctx, site, kwargs['project'], target, self.target_type)

            inst = fn(ctx, *args, **kwargs)
            self._run(ctx, inst)

        option_fns = []
        if self.project_type:
            option_fns.append(click.option('--project', '-p', type=str, required=True))
        if self.target_type:
            option_fns.append(click.option('--target', '-t', type=str, required=True))

        # Apply the additional options
        command = reduce(lambda f, o: o(f), option_fns, command)            

        # This is a little horrible but this means click options
        # can be added before or after the workflow decorator
        command.params += getattr(fn, '__click_params__', [])

        wf.add_command(command, name=self.name)
        return command
    

    def gather(self, config: Config) -> Iterable[tuple[Config, list[Transform], list[Transform]]]:
        '''
        Iterate over the tree of configs gathering "interesting" transforms.
        
        yields [the config, its transforms, its target transforms]
        '''
        for child_config in config.iter_config():
            for desc, transforms, target_transforms in self.gather(child_config):
                if config.config_filter(desc):
                    target_transforms = target_transforms
                else:
                    transform_filter = partial(config.transform_filter, config=desc)
                    target_transforms = list(filter(transform_filter, target_transforms))
                yield desc, transforms, target_transforms

        transforms = list(config.iter_transforms())
        transform_filter = partial(config.transform_filter, config=config)
        target_transforms = list(filter(transform_filter, transforms))
        yield (config, transforms, target_transforms)

    def _run(self, ctx, root: Config):
        '''
        Internally called method to run the workflow
        '''
        # Join interfaces together and get transform dependencies
        output_interfaces: list[Interface] = []
        dependency_map: dict[Transform, set[Transform]] = {}
        targets = []

        for _config, transforms, target_transforms in self.gather(root):
            for transform in transforms:
                dependency_map[transform] = set()
                for interface in transform.real_output_interfaces:
                    output_interfaces.append(interface)
            targets += target_transforms
            
        # We only need to look at output interfaces since an output must
        # exist in order for a dependency to exist
        for interface in output_interfaces:
            input_transform = cast(Transform, interface.input_transform)
            for output_transform in interface.output_transforms:
                dependency_map[output_transform].add(input_transform)

        # Run everything in order serially
        scheduler = Scheduler(dependency_map, targets=targets)
        while scheduler.incomplete:
            for transform in scheduler.schedulable:
                scheduler.schedule(transform)
                # Note this message is info for now for demonstrative purposes only
                logging.info("Running transform: %s", transform)
                transform.run(ctx)
                scheduler.finish(transform)
