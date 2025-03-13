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

import asyncio
import itertools
import json
import logging
import multiprocessing
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime
from functools import cache, partial, reduce
from pathlib import Path
from types import SimpleNamespace

import click
from gator.launch import MessageLimits, launch
from gator.launch_progress import launch as launch_progress
from gator.specs import Cores, Job, JobGroup, Memory
from ordered_set import OrderedSet as OSet

from ..activities.workflow import wf
from ..build.caching import Cache
from ..config.api import ConfigApi
from ..config.base import Config, Project, Site
from ..config.scheduler import Scheduler
from ..context import Context, DebugScope
from ..transforms.transform import Medial, Transform

re_ident_prefix = re.compile(r"[0-9]+_[0-9]:")


class WorkflowError(Exception):
    pass


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
        @click.option(
            "--parallel",
            "-P",
            is_flag=True,
            default=False,
            help=(
                "Use Gator to run workflows in parallel, with the maximum number"
                "of jobs set by the concurrency parameter"
            ),
        )
        @click.option(
            "--concurrency",
            "-c",
            type=int,
            default=max(1, multiprocessing.cpu_count() // 2),
            help="Specify the maximum number of jobs allowed to run in parallel",
        )
        @click.option(
            "--hub",
            type=str,
            default=None,
            help="The gator hub url",
        )
        @click.pass_obj
        def command(
            ctx, project=None, target=None, parallel=False, concurrency=1, hub=None, *args, **kwargs
        ):
            site_api = ConfigApi(ctx).with_site(ctx.site, self.SITE_TYPE)

            if project:
                project_api = site_api.with_project(project, self.project_type)
                kwargs["project"] = project_api.project.config
                if target:
                    target_api = project_api.with_target(target, self.target_type)
                    kwargs["target"] = target_api.target.config

            with site_api:
                inst = fn(ctx, *args, **kwargs)
            self._run(
                ctx,
                *self.get_transform_tree(inst),
                concurrency=concurrency,
                parallel=parallel,
                hub=hub,
            )

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
        medial_transforms_consumers: dict[Medial, OSet[Transform]] = defaultdict(OSet)
        medial_transform_producers: dict[Medial, OSet[Transform]] = defaultdict(OSet)
        dependency_map: dict[Transform, OSet[Transform]] = {}
        dependent_map: dict[Transform, OSet[Transform]] = {}
        targets: OSet[Transform] = OSet()

        for _config, transforms, target_transforms in self.gather(root):
            for transform in transforms:
                dependency_map[transform] = OSet()
                dependent_map[transform] = OSet()

                # Record transform inputs and outputs
                for serial in transform._serial_interfaces.values():
                    for medial in serial.medials:
                        if serial.direction.is_input:
                            medial_transforms_consumers[medial].add(transform)
                        else:
                            medial_transform_producers[medial].add(transform)
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

    def _run_serial(self, ctx: Context, scheduler: Scheduler[Transform], status: SimpleNamespace):
        """
        Run a scheduled workflow in series
        """
        # Whether a cache is in place
        is_caching = Cache.enabled(ctx)

        while scheduler.incomplete:
            # Place all currently schedulable jobs into this group
            for transform in scheduler.schedulable:
                scheduler.schedule(transform)
                if transform in status.fetched:
                    logging.info(f"Skipped cached {transform}")
                elif transform in status.skipped:
                    logging.info(f"Skipped transform (due to cached dependents): {transform}")
                else:
                    logging.info("Running transform: %s", transform)
                    result = transform.run(ctx)
                    status.run.add(transform)
                    if is_caching and Cache.store_transform_to_any(ctx, transform, result.run_time):
                        status.stored.add(transform)
                        logging.info("Stored transform to cache: %s", transform)

                scheduler.finish(transform)

    def _run_parallel(
        self,
        ctx: Context,
        scheduler: Scheduler[Transform],
        status: SimpleNamespace,
        concurrency: int,
        hub: str | None = None,
    ):
        """
        Run a scheduled workflow in parallel
        """
        # Create a directory for this run
        run_dirx = ctx.host_scratch / "flows" / datetime.now().strftime(r"D%Y%m%d-%H%M%S")
        spec_dirx = run_dirx / "spec"
        track_dirx = run_dirx / "tracking"
        spec_dirx.mkdir(parents=True, exist_ok=True)

        logging.info(
            f"Launching workflow under: {run_dirx}" + (f" with concurrency of {concurrency}")
        )

        root_group = JobGroup(ident="blockwork", cwd=ctx.host_root.as_posix())

        # Create groups out of transforms with the same set of input and
        # output dependencies to simplify ordering requirements.
        transform_dependencies = {}
        transform_dependents = {}

        _dependency_map = scheduler._dependency_map.copy()
        _dependent_map = scheduler._dependent_map.copy()
        for transform in scheduler._all:
            transform_dependencies[transform] = frozenset(_dependency_map[transform])
            transform_dependents[transform] = frozenset(_dependent_map[transform])

        group_counter = itertools.count()

        def make_group():
            return {"idx": next(group_counter), "jobs": [], "group": None}

        groups = defaultdict(make_group)
        group_by_transform = {}

        # Create a Gator job tree out of the blockwork schedule
        while scheduler.incomplete:
            for transform in scheduler.schedulable:
                scheduler.schedule(transform)
                group = None
                if transform in status.fetched:
                    logging.info(f"Skipped cached {transform}")
                elif transform in status.skipped:
                    logging.info(f"Skipped transform (due to cached dependents): {transform}")
                else:
                    dependencies = transform_dependencies[transform]
                    dependents = transform_dependents[transform]
                    group = groups[dependencies, dependents]
                    idx_group = group["idx"]
                    group_jobs = group["jobs"]
                    idx_job = len(group_jobs)

                    # Assemble a unique job ID
                    job_id = f"{idx_group}_{idx_job}"
                    # Serialise the transform
                    spec_file = spec_dirx / f"{job_id}.json"
                    logging.debug(
                        f"Serializing scheduled {type(transform).__name__} -> "
                        f"{spec_file.relative_to(ctx.host_scratch)}"
                    )
                    with spec_file.open("w", encoding="utf-8") as fh:
                        json.dump(transform.serialize(), fh)
                    # Launch the job
                    # TODO @intuity: Make the resource requests parameterisable
                    args = [
                        "--scratch",
                        ctx.host_scratch.as_posix(),
                    ]
                    if ctx.cache_config_path is not None:
                        args += ["--cache-config", ctx.cache_config_path.as_posix()]
                    args += [
                        "_wf_step",
                        spec_file.as_posix(),
                    ]
                    if DebugScope.current.VERBOSE:
                        args.insert(0, "--verbose")
                    # Give jobs a descriptive name where possible
                    job = Job(
                        ident=f"{transform.api.pathname}_{job_id}",
                        cwd=ctx.host_root.as_posix(),
                        command="bw",
                        args=args,
                        resources=[Cores(count=1), Memory(size=1, unit="GB")],
                    )
                    group_jobs.append(job)
                group_by_transform[transform] = group

                # Mark transform as finished (if running in parallel, Gator will
                # maintain the ordering requirements)
                scheduler.finish(transform)

        # Create job groups out of jobs that can be scheduled together
        for group in groups.values():
            jobs = group["jobs"]
            if len(jobs) == 1:
                # Don't bother with groups of one item
                group["group"] = jobs[0]
            else:
                # Attempt to give the group a nice name
                if len(jobs):
                    ident = re_ident_prefix.sub(str(group["idx"]), jobs[0].ident)
                else:
                    ident = str(group["idx"])
                group["group"] = JobGroup(ident=ident, jobs=jobs)

            root_group.jobs.append(group["group"])

        # Link the group dependencies
        for (dependencies, _dependents), group in groups.items():
            for dep in dependencies:
                dep_group = group_by_transform[dep]
                if dep_group:
                    group["group"].on_pass.append(dep_group["group"].ident)

        # If parallel run is enabled, start up a Gator process
        if root_group.expected_jobs:
            # Suppress messages coming from websockets within Gator
            logging.getLogger("websockets.server").setLevel(logging.CRITICAL)

            # Launch the Gator run
            logging.info(
                f"Executing {root_group.expected_jobs} jobs with concurrency of {concurrency}"
            )
            summary = asyncio.run(
                (launch if DebugScope.current.VERBOSE else launch_progress)(
                    spec=root_group,
                    tracking=track_dirx,
                    sched_opts={"concurrency": concurrency},
                    glyph="🧱 Blockwork",
                    hub=hub or ctx.hub_url,
                    # TODO @intuity: In the long term a waiver system should be
                    #                introduced to suppress errors if they are
                    #                false, for now just set to a high value
                    limits=MessageLimits(error=10000),
                )
            )

            if DebugScope.current.VERBOSE:
                # For any failed IDs, resolve them to their log files
                for job_id in summary.failed_ids:
                    ptr = root_group
                    # Resolve the job
                    for idx, part in enumerate(job_id[1:]):
                        for sub in ptr.jobs:
                            if sub.ident == part:
                                ptr = sub
                                break
                        else:
                            raise Exception(
                                f"Failed to resolve '{part}' within {'.'.join(job_id[:idx])}"
                            )
                    # Grab the spec JSON
                    *_, spec_json = ptr.args
                    with Path(spec_json).open("r", encoding="utf-8") as fh:
                        spec_data = json.load(fh)
                    # Grab the tracking directory
                    job_trk_dirx = track_dirx / "/".join(job_id[1:])
                    logging.error(f"{spec_data['name']} failed: {job_trk_dirx / 'messages.log'}")

            # Check for failure
            if summary.failed:
                raise WorkflowError("Some jobs failed!")

    def _run(
        self,
        ctx: Context,
        targets: OSet[Transform],
        dependency_map: dict[Transform, OSet[Transform]],
        dependent_map: dict[Transform, OSet[Transform]],
        parallel: bool,
        concurrency: int,
        hub: str | None = None,
    ):
        """
        Run the workflow from transform dependency data.

        :param ctx:            Context object
        :param targets:        Complete list of targets to build
        :param dependency_map: Dependencies between targets, used to form the
                               graph structure and schedule work
        :param dependent_map:  Reversed listing of dependencies, used to check
                               for cached results
        :param parallel:       Enable/disable the parallel executor (using Gator)
        :param concurrency:    Set the desired concurrency
        """
        status = SimpleNamespace(
            # Record the transforms we actually ran
            run=OSet(),
            # Record the transforms we pulled from the cache
            fetched=OSet(),
            # Record the transforms that don't need to be run since they were were
            # pulled from the cahce or only transforms pulled from the cache
            # depend on them.
            skipped=OSet(),
            # And those that made it into the cache
            stored=OSet(),
        )

        # Whether a cache is in place
        is_caching = Cache.enabled(ctx)

        # Run in reverse order, pulling from the cache if items exits
        if is_caching:
            cache_scheduler = Scheduler(dependency_map, targets=targets, reverse=True)
            while cache_scheduler.incomplete:
                for transform in cache_scheduler.schedulable:
                    cache_scheduler.schedule(transform)
                    if ctx.caching_forced or transform not in targets:
                        if not (
                            dependent_map[transform] - status.skipped
                            or dependent_map[transform] - status.fetched
                        ):
                            status.skipped.add(transform)
                        elif Cache.fetch_transform_from_any(ctx, transform):
                            logging.info("Fetched transform from cache: %s", transform)
                            status.fetched.add(transform)
                    cache_scheduler.finish(transform)

        # Push everything into Gator based on scheduling order
        run_scheduler = Scheduler(dependency_map, targets=targets)

        try:
            if parallel:
                self._run_parallel(ctx, run_scheduler, status, concurrency=concurrency, hub=hub)
            else:
                self._run_serial(ctx, run_scheduler, status)
        finally:
            # Prune the caches down to size at the end
            if is_caching:
                Cache.prune_all(ctx)

            # Run reporting stages
            run_transform_instances = defaultdict(OSet)
            for transform in status.run:
                run_transform_instances[type(transform)].add(transform)
                if (tf_report := getattr(transform, "tf_report", None)) is not None:
                    tf_report(ctx)

            for transform_class, transforms in run_transform_instances.items():
                if (tf_cls_report := getattr(transform_class, "tf_cls_report", None)) is not None:
                    tf_cls_report(ctx, list(transforms))

        # This is primarily returned for unit-testing
        return status
