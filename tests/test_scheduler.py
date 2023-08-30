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

from typing import Any
import pytest

from blockwork.config.scheduler import Scheduler, CyclicError

class StateRecord:
    def __init__(self):
        self.states = []
        self.keys = {"leaves","schedulable","blocked","unscheduled","scheduled","incomplete","complete"}

    def record(self, scheduler):
        self.states.append({key: getattr(scheduler, f"get_{key}")() for key in self.keys})

    def __getattr__(self, __name: str) -> Any:
        if __name in self.keys:
            return tuple(state.get(__name) for state in self.states)
        return super().__getattribute__(__name)


class TestScheduler:

    def test_basic(self):
        'Tests a basic chain'
        dependant_map = {
            "x": {"y"}, 
            "y": {"z"}
        }
        scheduler = Scheduler(dependant_map)
        
        states = StateRecord()

        while scheduler.get_incomplete():
            states.record(scheduler)
            for item in scheduler.get_schedulable():
                scheduler.schedule(item)
                scheduler.finish(item)

        assert states.schedulable == ({"x"},{"y"},{"z"})
        assert states.blocked == ({"y","z"},{"z"}, set())
        assert states.incomplete == ({"x", "y", "z"}, {"y", "z"}, {"z"})
        assert states.complete == (set(), {"x"}, {"x", "y"})

    def test_cycle(self):
        'Tests that cycles are detected'
        mapping = {
            "x": {"y"},
            "y": {"z"},
            "z": {"x"}
        }
        scheduler = Scheduler(mapping)

        with pytest.raises(CyclicError):
            scheduler.get_schedulable()

    def test_complex(self) -> None:
        'Tests a more complex tree is scheduled correctly'
        dependant_map = {
            "a": {"b"}, 
            "b": {"c", "d"},
            "c": {"e"},
            "d": {"f"},
            "e": {"f"},
            "g": {"f"}
        }
        scheduler = Scheduler(dependant_map)
        
        states = StateRecord()

        while scheduler.get_incomplete():
            states.record(scheduler)
            for item in scheduler.get_schedulable():
                scheduler.schedule(item)
                scheduler.finish(item)

        assert states.schedulable == ({"a", "g"}, {"b"}, {"c", "d"}, {"e"}, {"f"})
