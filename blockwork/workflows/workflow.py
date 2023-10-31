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
from types import SimpleNamespace

from ..build.caching import Cache

from ..context import Context

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
            self._run(ctx, *self.get_transform_tree(inst))

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
        
        :return: An iterable of tuples of 'the config', 'its transforms', 'its target transforms'
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

    def get_transform_tree(self, root: Config) -> tuple[set[Transform], 
                                                        dict[Transform, set[Transform]], 
                                                        dict[Transform, set[Transform]]]:
        '''
        Gather transform dependency data.

        :return: Tuple of 'the targets', 'the dependency tree', 'the depenent tree (inverted dependency tree)'
        '''
        # Join interfaces together and get transform dependencies
        output_interfaces: list[Interface] = []
        dependency_map: dict[Transform, set[Transform]] = {}
        dependent_map: dict[Transform, set[Transform]] = {}
        targets: set[Transform] = set()

        for _config, transforms, target_transforms in self.gather(root):
            for transform in transforms:
                dependency_map[transform] = set()
                dependent_map[transform] = set()
                for interface in transform.real_output_interfaces:
                    output_interfaces.append(interface)
            targets.update(target_transforms)
            
        # We only need to look at output interfaces since an output must
        # exist in order for a dependency to exist
        for interface in output_interfaces:
            input_transform = cast(Transform, interface.input_transform)
            for output_transform in interface.output_transforms:
                dependency_map[output_transform].add(input_transform)
                dependent_map[input_transform].add(output_transform)
        
        return targets, dependency_map, dependent_map
    
    def _run(self,
             ctx: Context,
             targets: set[Transform],
             dependency_map: dict[Transform, set[Transform]],
             dependent_map: dict[Transform, set[Transform]]):
        '''
        Run the workflow from transform dependency data.
        '''

        # Record the transforms we pulled from the cache
        fetched_transforms: set[Transform] = set()
        # Record the transforms that don't need to be run since they were were
        # pulled from the cahce or only transforms pulled from the cache 
        # depend on them.
        skipped_transforms: set[Transform] = set()
        # Record the transforms we actually ran
        run_transforms: set[Transform] = set()
        # And those that made it into the cache
        stored_transforms: set[Transform] = set()

        # Run in reverse order, pulling from the cache if items exits
        cache_scheduler = Scheduler(dependency_map, targets=targets, reverse=True)
        while cache_scheduler.incomplete:
            for transform in cache_scheduler.schedulable:
                cache_scheduler.schedule(transform)
                if transform not in targets:
                    if not (dependent_map[transform] - skipped_transforms or
                            dependent_map[transform] - fetched_transforms):
                        skipped_transforms.add(transform)
                    elif Cache.fetch_transform(ctx, transform):
                        logging.info("Fetched transform from cache: %s", transform)
                        fetched_transforms.add(transform)
                cache_scheduler.finish(transform)

        # Run everything in order, skipping cached entries, and pushing to the cache when possible
        run_scheduler = Scheduler(dependency_map, targets=targets)
        while run_scheduler.incomplete:
            for transform in run_scheduler.schedulable:
                run_scheduler.schedule(transform)
                if transform in fetched_transforms:
                    logging.info("Skipped cached transform: %s", transform)
                elif transform in skipped_transforms:
                    logging.info("Skipped transform (due to cached dependents): %s", transform)
                else:
                    logging.info("Running transform: %s", transform)
                    transform.run(ctx)
                    run_transforms.add(transform)
                    if Cache.store_transform(ctx, transform):
                        stored_transforms.add(transform)
                        logging.info("Stored transform to cache: %s", transform)
                run_scheduler.finish(transform)

        # This is primarily returned for unit-testing
        return SimpleNamespace(
            run=run_transforms,
            stored=stored_transforms,
            fetched=fetched_transforms,
            skipped=skipped_transforms
        )