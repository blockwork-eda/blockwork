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
from collections import defaultdict
from collections.abc import Callable, Iterable
from functools import cache, partial, reduce
from pathlib import Path
from types import SimpleNamespace

import click
from ordered_set import OrderedSet as OSet

from ..activities.workflow import wf
from ..build.caching import Cache
from ..config.api import ConfigApi
from ..config.base import Config, Project, Site
from ..config.scheduler import Scheduler
from ..context import Context
from ..transforms.transform import Medial, Transform


class Workflow:
    """
    Wrapper for workflow functions.

    Workflows are implemented as functions which are run from the command
    line and that return a Config object. For example::

        @Workflow("<workflow_name>")
        @click.option("--match", type=str, required=True)
        def my_workflow(ctx, match):
            return Build(match=match)

    """

    # Type for Site object
    SITE_TYPE = Site

    def __init__(self, name: str):
        self.name = name
        self.project_type = None
        self.target_type = None

    def with_project(self, typ: type[Project] | None = None):
        "Convenience method to add a --project option"
        self.project_type = typ or Project
        return self

    def with_target(self, typ: type[Config] | None = None):
        "Convenience method to add --project and --target options"
        self.project_type = self.project_type or Project
        self.target_type = typ or Config
        return self

    @classmethod
    def parse(cls, typ, path: Path):
        return Config.parser(typ).parse(path)

    def __call__(self, fn: Callable[..., Config]) -> Callable[..., None]:
        @click.command()
        @click.pass_obj
        def command(ctx, project=None, target=None, *args, **kwargs):
            site_api = ConfigApi(ctx).with_site(ctx.site, self.SITE_TYPE)

            if project:
                project_api = site_api.with_project(project, self.project_type)
                kwargs["project"] = project_api.project.config
                if target:
                    target_api = project_api.with_target(target, self.target_type)
                    kwargs["target"] = target_api.target.config

            with site_api:
                inst = fn(ctx, *args, **kwargs)
            self._run(ctx, *self.get_transform_tree(inst))

        option_fns = []
        if self.project_type:
            option_fns.append(click.option("--project", "-p", type=str, required=True))
        if self.target_type:
            option_fns.append(click.option("--target", "-t", type=str, required=True))

        # Apply the additional options
        command = reduce(lambda f, o: o(f), option_fns, command)

        # This is a little horrible but this means click options
        # can be added before or after the workflow decorator
        command.params += getattr(fn, "__click_params__", [])

        wf.add_command(command, name=self.name)
        return command

    @cache  # noqa: B019
    def gather(self, config: Config) -> Iterable[tuple[Config, list[Transform], list[Transform]]]:
        """
        Iterate over the tree of configs gathering "interesting" transforms.

        Note it is functionally required that this is cached as we must only
        process each config once.

        :return: An iterable of tuples of 'the config', 'its transforms', 'its target transforms'
        """
        for child_config in config.iter_config():
            for desc, transforms, target_transforms in self.gather(child_config):
                if config.config_filter(desc):
                    target_transforms = target_transforms
                else:
                    transform_filter = partial(config.transform_filter, config=desc)
                    target_transforms = list(filter(transform_filter, target_transforms))
                yield desc, transforms, target_transforms

        with config.api:
            transforms = list(config.iter_transforms())
        transform_filter = partial(config.transform_filter, config=config)
        target_transforms = list(filter(transform_filter, transforms))
        yield (config, transforms, target_transforms)

    def get_transform_tree(
        self, root: Config
    ) -> tuple[
        OSet[Transform],
        dict[Transform, OSet[Transform]],
        dict[Transform, OSet[Transform]],
    ]:
        """
        Gather transform dependency data.

        :return: Tuple of 'the targets', 'the dependency tree', 'the dependent
                 tree (inverted dependency tree)'
        """
        # Join interfaces together and get transform dependencies
        medial_transforms_consumers: dict[Medial, list[Transform]] = defaultdict(list)
        medial_transform_producers: dict[Medial, list[Transform]] = defaultdict(list)
        dependency_map: dict[Transform, OSet[Transform]] = {}
        dependent_map: dict[Transform, OSet[Transform]] = {}
        targets: OSet[Transform] = OSet()

        for _config, transforms, target_transforms in self.gather(root):
            for transform in transforms:
                dependency_map[transform] = OSet()
                dependent_map[transform] = OSet()

                # Record transform inputs and outputs
                for direction, serial in transform._serial_interfaces.values():
                    for medial in serial.medials:
                        if direction.is_input:
                            medial_transforms_consumers[medial].append(transform)
                        else:
                            medial_transform_producers[medial].append(transform)
                        # Note this deliberately binds the consumer list by
                        # reference as it may be added to by later
                        # transforms
                        medial.bind_consumers(medial_transforms_consumers[medial])
                        medial.bind_producers(medial_transform_producers[medial])
            targets.update(target_transforms)

        # Build up dependencies between transforms
        for medial, consumers in medial_transforms_consumers.items():
            for consumer in consumers:
                producers = medial_transform_producers[medial]
                exists = medial._exists()
                # Working cases
                if exists and len(producers) == 0:
                    continue
                if not exists and len(producers) == 1:
                    dependency_map[consumer].add(producers[0])
                    dependent_map[producers[0]].add(consumer)
                    continue
                # Error cases
                if exists and len(producers) > 0:
                    raise RuntimeError(
                        f"Medial `{medial}` already exists, but"
                        f" has producer(s) `{producers}`."
                        f" Required by `{consumers}`."
                    )
                if len(producers) == 0:
                    raise RuntimeError(
                        f"Medial `{medial}` doesn't exist, and"
                        f" has no producers. Required by"
                        f" `{consumers}`."
                    )
                if len(producers) > 1:
                    raise RuntimeError(
                        f"Medial `{medial}` has multiple"
                        f" producers `{producers}`. Required"
                        f" by `{consumers}`."
                    )

        return targets, dependency_map, dependent_map

    def _run(
        self,
        ctx: Context,
        targets: OSet[Transform],
        dependency_map: dict[Transform, OSet[Transform]],
        dependent_map: dict[Transform, OSet[Transform]],
    ):
        """
        Run the workflow from transform dependency data.
        """
        # Record the transforms we pulled from the cache
        fetched_transforms: OSet[Transform] = OSet()
        # Record the transforms that don't need to be run since they were were
        # pulled from the cahce or only transforms pulled from the cache
        # depend on them.
        skipped_transforms: OSet[Transform] = OSet()
        # Record the transforms we actually ran
        run_transforms: OSet[Transform] = OSet()
        # And those that made it into the cache
        stored_transforms: OSet[Transform] = OSet()

        # Whether a cache is in place
        is_caching = Cache.enabled(ctx)

        # Run in reverse order, pulling from the cache if items exits
        if is_caching:
            cache_scheduler = Scheduler(dependency_map, targets=targets, reverse=True)
            while cache_scheduler.incomplete:
                for transform in cache_scheduler.schedulable:
                    cache_scheduler.schedule(transform)
                    if transform not in targets:
                        if not (
                            dependent_map[transform] - skipped_transforms
                            or dependent_map[transform] - fetched_transforms
                        ):
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
                    if is_caching and Cache.store_transform(ctx, transform):
                        stored_transforms.add(transform)
                        logging.info("Stored transform to cache: %s", transform)
                run_scheduler.finish(transform)

        # This is primarily returned for unit-testing
        return SimpleNamespace(
            run=run_transforms,
            stored=stored_transforms,
            fetched=fetched_transforms,
            skipped=skipped_transforms,
        )
