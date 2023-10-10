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
from ..common.complexnamespaces import ReadonlyNamespace
from ..config.base import Config
import click
import logging
from pathlib import Path
from typing import Iterable, cast

from ..config.scheduler import Scheduler
from ..config import parsers

from ..build.interface import Interface

from ..build.transform import Transform
from ..config import base
from ..activities.workflow import wf


class WrapType(click.ParamType):
    'An wrapped option with some context from creation time'
    name = "wrap"
    def __init__(self, option_type, **kwargs):
        super().__init__()
        self.option_type = option_type
        self.kwargs = kwargs

    def convert(self, value, param, ctx):
        if not isinstance(value, self.option_type):
            raise TypeError("...")
        return ReadonlyNamespace(value=value, **self.kwargs)

class Workflow(base.Config):
    '''
    Base class for workflows
    
    Workflows are implemented as configuration which can also be generated
    from a command line. This feature is useful for composition, for example
    a sim workflow could be run directly on the command line, or used several
    times in configuration and run via a ci workflow.
    '''

    # Tool root locator
    ROOT : Path = Path("/__tool_root__")

    # Type for Site object
    SITE_TYPE = base.Site

    # This init only exists to prevent a typechecking issue
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def from_command(cls, target):
        '''
        Create this workflow object from a command.

        This should be implemented in subclass workflows which need
        to add any custom argument parsing using click, for example::

            @classmethod
            @click.option('--match', type=str, default=None)
            def from_command(cls, target, match):
                return cls(target=target, match=match)
        '''
        return cls(target=target)
    
    class Options:
        'Container for standard workflow options'
        @staticmethod
        def project(*, project_type=base.Project):
            return click.option('--project', '-p', type=WrapType(str, type=project_type), required=True)

        @staticmethod
        def target(*, project_type=base.Project, target_type=base.Config):
            return partial(reduce, lambda f, o: o(f), [
                click.option('--project', '-p', type=WrapType(str, type=project_type), required=True),
                click.option('--target', '-t', type=WrapType(str, type=target_type), required=True)
            ])

    @classmethod
    def _run_command(cls, ctx, project=None, target=None, *args, **kwargs):
        '''
        Internally called method to run a workflow from the command line.
        '''
        SITE_TYPE = cls.SITE_TYPE
        site_parser = parsers.Site(ctx)
        site_path = ctx.site
        site_config = site_parser(SITE_TYPE).parse(site_path)

        if project:
            project_parser = parsers.Project(ctx, site_config)
            project_path = Path(site_config.projects[project.value])
            project_config = project_parser(project.type).parse(project_path)
            kwargs['project'] = project_config

            if target:
                target_parser = parsers.Element(ctx, site_config, project_config)
                target_config = target_parser.parse_target(target.value, target.type)
                kwargs['target'] = target_config

        inst = cls.from_command(*args, **kwargs)
        inst._run(ctx)

    def __init_subclass__(cls, *args, **kwargs):
        '''
        Registers the workflow as a click subcommand with some default 
        arguments attached.

        What this actually does is a bit of a hack, but it does hide the
        complexity from user code effectively, it:
            - pulls the workflow options from the `from_command` method
            - attaches them to the internal `_run_command` method
            - registers the internal `_run_command` method as a sub command

        '''
        super().__init_subclass__(*args, **kwargs)
        if getattr(cls.from_command, '__self__', None) is not cls:
            raise RuntimeError("from_command must be classmethod")
        
        run_command = cls._run_command
        run_command = click.pass_obj(run_command)
        run_command = click.command(run_command)

        # Inherit params from from_command
        run_command.params += getattr(cls.from_command, '__click_params__', [])

        cls._run_command = run_command
        wf.add_command(cls._run_command, name=cls.__name__.lower())

    def _pick(self) -> tuple[list[Transform], list[Transform]]:
        '''
        Internally called method to find the transforms and targets
        from the config tree based on the filter methods.
        '''
        workflows = []
        transforms = []
        config_by_transform = {}
        targets = []
    
        done = set()
        for config in self.depth_first_config(self):
            # Only process each config once
            if config in done:
                continue
            done.add(config)

            if isinstance(config, Workflow):
                if self.workflow_filter(config):
                    workflows.append(config)

            for transform in config.iter_transforms():
                config_by_transform[transform] = config
                transforms.append(transform)

        for transform in transforms:
            config = config_by_transform[transform]
            if any(wf.transform_filter(transform, config) for wf in workflows):
                targets.append(transform)

        return transforms, targets


    def _run(self, ctx):
        '''
        Internally called method to run the workflow
        '''
        # Join interfaces together and get transform dependencies
        output_interfaces: list[Interface] = []
        dependency_map: dict[Transform, set[Transform]] = {}
        transforms, targets = self._pick()

        for transform in transforms:
            dependency_map[transform] = set()
            for interface in transform.output_interfaces.values():
                output_interfaces.append(interface)

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



    def transform_filter(self, transform: Transform, config: base.Config) -> bool:
        'Return true for transforms that this workflow is interested in'
        raise NotImplementedError
    
    def workflow_filter(self, workflow: "Workflow"):
        'Return true for sub-workflows that this workflow is interested in'
        # @ed.kotarski - I'm not sure this is actually useful, but leaving in for now...
        return True

    def depth_first_config(self, config: base.Config) -> Iterable[base.Config]:
        'Recures elements and yields depths first'
        for sub_config in config.iter_config():
            yield from self.depth_first_config(sub_config)
        yield config

    def iter_config(self) -> Iterable[Config]:
        '''
        Generate config for this workflow.
        This will be useful to override in cases where config is generated
        based on command line arguments. For example, if a sim workflow
        allowed test generation to be specified on the command line.
        '''
        if isinstance(target:=getattr(self, 'target', None), Config):
            # This is a really common use-case 
            yield target
        else:
            raise NotImplementedError
