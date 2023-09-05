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
from typing import Callable, Hashable, Iterable, TYPE_CHECKING, Optional

from ..common.registry import RegisteredClass
from ..common.singleton import Singleton
from ..build.interface import Interface, InterfaceDirection
if TYPE_CHECKING:
    from ..build.transform import Transform
    from ..context import Context
from . import base
from .scheduler import Scheduler

class Config(RegisteredClass, metaclass=Singleton):
    'Configuration object which is passed into workflows'
    def __init__(self, ctx: "Context", site: base.Site, project: base.Project, target: base.Element) -> None:
        self.ctx = ctx
        self.site = site
        self.project = project
        self.target = target

    @classmethod
    def depth_first_elements(cls, element: base.Element) -> Iterable[base.Element]:
        'Recures elements and yields depths first'
        for sub_element in element.iter_elements():
            yield from cls.depth_first_elements(sub_element)
        yield element


    def run(self, transform_filter: Optional[Callable[[Iterable["Transform"]], Iterable["Transform"]]]=None):
        """
        Run every transform from the configuration.

        @ed.kotarski: This is a temporary implementation that I
                      intend to change soon
        """
        # Join interfaces together and get transform dependencies
        interfaces: list[Interface] = []
        transforms: list[Transform] = []
        dependency_map: dict[Transform, set[Transform]] = {}
        for element in Config.depth_first_elements(self.target):
            for transform in element.iter_transforms():
                transforms.append(transform)
                dependency_map[transform] = set()
                for interface in transform.interfaces:
                    interfaces.append(interface)

        interface_map: dict[Hashable, Interface] = {}
        for interface in interfaces:
            if interface.direction is InterfaceDirection.Output:
                for key in interface.keys():
                    if key in interface_map:
                        raise RuntimeError
                    interface_map[key] = interface

        for interface in interfaces:
            if interface.direction is InterfaceDirection.Input:
                for key in interface.keys():
                    if (output:=interface_map.get(key, None)) is not None:
                        interface.connect(output)
                        dependency_map[interface.transform].add(output.transform)
                        break
                else:
                    # If there's no matching output for an input interface
                    # we may later want to error ... but currently this is
                    # allowed so long as the interface specifies a 
                    # `resolve_input` method.
                    pass

        # Use the provided filter to pick out targets
        if transform_filter is None:
            targets = None
        else:
            targets = transform_filter(transforms)

        # Run everything in order serially
        scheduler = Scheduler(dependency_map, targets=targets)
        while scheduler.incomplete:
            for element in scheduler.schedulable:
                scheduler.schedule(element)
                # Note this message is info for now for demonstrative purposes only
                logging.info("Running transform: %s", element)
                element.run(self.ctx)
                scheduler.finish(element)
