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
from typing import Generic, Hashable, TypeVar

class SchedulingError(RuntimeError):
    'Base class for scheduling errors'

class CyclicError(SchedulingError):
    'Graph contains a cycle'


_Schedulable = TypeVar("_Schedulable", bound=Hashable)
class Scheduler(Generic[_Schedulable]):
    '''
    Generic scheduler for a directed acyclic graphs.

    Usage example::

        dependant_map = {"x": set(("y")), "y": set(("z"))}
        scheduler = Schedular(dependant_map)
        while scheduler.get_incomplete():
            for item in scheduler.get_schedulable():
                scheduler.schedule(item)
                ...run the step related to the item...
                scheduler.finish(item)                
    '''
    def __init__(self, dependent_map: dict[_Schedulable, set[_Schedulable]]):
        '''
        :param dependent_map: A map between items and the items that depend on them
            (NOT THE ITEMS THAT THEY DEPEND ON).
        '''
        self._dependent_map = dependent_map
        self._dependency_map: dict[_Schedulable, set[_Schedulable]] = defaultdict(set)
        for dependency, dependents in dependent_map.items():
            for dependent in dependents:
                self._dependency_map[dependent].add(dependency)

        self._remaining = set(dependent_map.keys()) | set(self._dependency_map.keys())
        self._all = set(self._remaining)
        self._unscheduled = set(self._all)
        self._scheduled: set[_Schedulable] = set()
        self._complete: set[_Schedulable] = set()

    def get_leaves(self) -> set[_Schedulable]:
        """
        Get leaf items which don't depend on anything else.
        Note: dependencies are dropped as items finish so this
              will change as the scheduler runs.
        """
        dependents = set(self._dependency_map.keys())
        return self._remaining - dependents

    def get_schedulable(self) -> set[_Schedulable]:
        "Get schedulable items (leaves which haven't been scheduled)"
        leaves = self.get_leaves()
        if not leaves and not self._scheduled and self.get_incomplete():
            # Detects cycles in the graph
            raise CyclicError(f"{self._dependency_map}")
        return leaves - self._scheduled

    def get_blocked(self) -> set[_Schedulable]:
        "Get non-leaf items which depend on something else"
        return self._unscheduled - self.get_leaves()

    def get_unscheduled(self) -> set[_Schedulable]:
        "Get any items that haven't been scheduled yet"
        return set(self._unscheduled)

    def get_scheduled(self) -> set[_Schedulable]:
        "Get any items that have been scheduled, but are not complete"
        return set(self._scheduled)

    def get_incomplete(self) -> set[_Schedulable]:
        "Get any items that are not complete"
        return self._unscheduled | self._scheduled

    def get_complete(self) -> set[_Schedulable]:
        "Get any items that are complete"
        return set(self._complete)
    
    def schedule(self, item: _Schedulable):
        """
        Schedule an item. This item must come from the get_schedulable result
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

