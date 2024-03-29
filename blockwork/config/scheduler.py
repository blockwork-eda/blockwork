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
from collections import defaultdict
from collections.abc import Hashable, Iterable
from typing import Generic, TypeVar

from ordered_set import OrderedSet as OSet


class SchedulingError(RuntimeError):
    "Base class for scheduling errors"


class CyclicError(SchedulingError):
    "Graph contains a cycle"


_Schedulable = TypeVar("_Schedulable", bound=Hashable)


class Scheduler(Generic[_Schedulable]):
    """
    Generic scheduler for a directed acyclic graphs.

    Usage example::

        dependant_map = {"x": OSet(("y", )), "y": OSet(("z", ))}
        scheduler = Schedular(dependant_map)
        while scheduler.incomplete:
            for item in scheduler.schedulable:
                scheduler.schedule(item)
                ...run the step related to the item...
                scheduler.finish(item)
    """

    def __init__(
        self,
        dependency_map: dict[_Schedulable, OSet[_Schedulable]],
        targets: Iterable[_Schedulable] | None = None,
        reverse: bool = False,
    ):
        """
        :param dependency_map: A map between items and the items that they depend on.
                               This must be dense, containing empty values for items
                               with no dependencies.
        :param targets: The target items, only (recursive) dependencies of these items
                        will be scheduled. If None, all items will be scheduled.
        :param reverse: Schedule in reverse order - as if the dependency map is flipped.
        """
        if targets is None:
            # Assume any item in the dependency map needs to be built
            level_targets = OSet(dependency_map.keys())
        else:
            level_targets = OSet(targets)

        # Navigate down the tree and find all items that need to
        # be scheduled based on the targets
        self._all: OSet[_Schedulable] = OSet()
        count = 0
        while True:
            self._all |= level_targets
            if count == (count := len(self._all)):
                break
            next_level_targets = OSet()
            for level_target in level_targets:
                next_level_targets |= dependency_map.get(level_target, OSet())
            level_targets = next_level_targets
            if not level_targets:
                break

        # Iterate over the dependency map and prune it to the items that
        # we need to schedule for the targets
        self._dependent_map: dict[_Schedulable, OSet[_Schedulable]] = defaultdict(OSet)
        self._dependency_map: dict[_Schedulable, OSet[_Schedulable]] = defaultdict(OSet)
        for dependant, dependencies in dependency_map.items():
            if dependant not in self._all:
                continue
            if dependencies:
                self._dependency_map[dependant] |= dependencies
            for dependency in dependencies:
                self._dependent_map[dependency].add(dependant)

        if reverse:
            self._dependency_map, self._dependent_map = (
                self._dependent_map,
                self._dependency_map,
            )

        self._remaining = OSet(self._all)
        self._unscheduled = OSet(self._all)
        self._scheduled: OSet[_Schedulable] = OSet()
        self._complete: OSet[_Schedulable] = OSet()

    @property
    def leaves(self) -> OSet[_Schedulable]:
        """
        Get leaf items which don't depend on anything else.
        Note: dependencies are dropped as items finish so this
              will change as the scheduler runs.
        """
        dependents = OSet(self._dependency_map.keys())
        return self._remaining - dependents

    @property
    def schedulable(self) -> OSet[_Schedulable]:
        "Get schedulable items (leaves which haven't been scheduled)"
        leaves = self.leaves
        if not leaves and not self._scheduled and self.incomplete:
            # Detects cycles in the graph
            raise CyclicError(f"{self._dependency_map}")
        return leaves - self._scheduled

    @property
    def blocked(self) -> OSet[_Schedulable]:
        "Get non-leaf items which depend on something else"
        return self._unscheduled - self.leaves

    @property
    def unscheduled(self) -> OSet[_Schedulable]:
        "Get any items that haven't been scheduled yet"
        return OSet(self._unscheduled)

    @property
    def scheduled(self) -> OSet[_Schedulable]:
        "Get any items that have been scheduled, but are not complete"
        return OSet(self._scheduled)

    @property
    def incomplete(self) -> OSet[_Schedulable]:
        "Get any items that are not complete"
        return self._unscheduled | self._scheduled

    @property
    def complete(self) -> OSet[_Schedulable]:
        "Get any items that are complete"
        return OSet(self._complete)

    def schedule(self, item: _Schedulable):
        """
        Schedule an item. This item must come from `schedulable`
        or bad things will happen.
        """
        self._unscheduled.remove(item)
        self._scheduled.add(item)

    def finish(self, item: _Schedulable):
        """
        Mark an item as being complete. This will drop it from the graph.
        This should only be a previously scheduled item, and must only
        be called once per item.
        """
        if item in self._dependent_map:
            for dependent in self._dependent_map[item]:
                self._dependency_map[dependent].remove(item)
                if not self._dependency_map[dependent]:
                    del self._dependency_map[dependent]

        self._remaining.remove(item)
        self._scheduled.remove(item)
        self._complete.add(item)
