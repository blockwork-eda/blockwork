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

import functools
import logging
from pathlib import Path
from typing import Iterable, cast

from ..config.scheduler import Scheduler

from ..context import Context

from ..build.interface import Interface

from ..build.transform import Transform
from ..common.registry import RegisteredClass
from ..common.singleton import Singleton
from ..config import base


class Workflow(RegisteredClass, metaclass=Singleton):
    """ Base class for workflows """

    # Tool root locator
    ROOT : Path = Path("/__tool_root__")

    # Config types this workflow uses
    SITE_TYPE = base.Site
    PROJECT_TYPE = base.Project
    TARGET_TYPE = base.Element

    def __init__(self, ctx: Context, site: base.Site, project: base.Project, target: base.Element) -> None:
        self.ctx = ctx
        self.site = site
        self.project = project
        self.target = target

    def depth_first_elements(self, element: base.Element) -> Iterable[base.Element]:
        'Recures elements and yields depths first'
        for sub_element in element.iter_elements():
            yield from self.depth_first_elements(sub_element)
        yield element

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
                for interface in transform.output_interfaces:
                    output_interfaces.append(interface)

        # We only need to look at output interfaces since an output must
        # exist in order for a dependency to exist
        for interface in output_interfaces:
            input_transform = cast(Transform, interface.input_transform)
            for output_transform in interface.output_transforms:
                dependency_map[output_transform].add(input_transform)

        # Use the filters to pick out targets
        targets = (t for e,t in element_transforms if self.transform_filter(t, e))

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

    @classmethod
    @property
    @functools.lru_cache()
    def name(cls) -> str:
        return cls.__name__.lower()

    # ==========================================================================
    # Registry Handling
    # ==========================================================================

    @classmethod
    def wrap(cls, workflow : "Workflow") -> "Workflow":
        if workflow in RegisteredClass.LOOKUP_BY_OBJ[cls]:
            return workflow
        else:
            RegisteredClass.LOOKUP_BY_NAME[cls][workflow.name] = workflow
            RegisteredClass.LOOKUP_BY_OBJ[cls][workflow] = workflow
            return workflow
