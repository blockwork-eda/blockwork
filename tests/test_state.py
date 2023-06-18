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

import json
import time
from pathlib import Path

import pytest

from blockwork.state import State, StateError


class TestState:

    def test_state(self, tmp_path : Path) -> None:
        """ Exercise state preservation and retrieval """
        state_dirx = tmp_path / "state"
        # Create state object
        state = State(state_dirx)
        # Create multiple namespaces
        ns_1 = state.ns_1
        ns_2 = state.ns_2
        ns_3 = state.ns_3
        # Check that they're all distinct
        assert len({ns_1, ns_2, ns_3}) == 3
        # Check no data has been written yet
        assert not state_dirx.exists()
        # Setup some variables in each namespace
        ns_1.a = 123
        ns_1.b = "abc"
        ns_2.c = 234.567
        ns_2.d = False
        ns_3.e = 456
        ns_3.f = "def"
        # Check variables read back correctly
        assert ns_1.a == 123
        assert ns_1.b == "abc"
        assert ns_2.c == 234.567
        assert ns_2.d == False
        assert ns_3.e == 456
        assert ns_3.f == "def"
        # Check non-existing values return None
        assert ns_1.c is None
        assert ns_3.a is None
        # Save all state to disk, then check files were written out
        state.save_all()
        assert state_dirx.exists()
        assert (state_dirx / "ns_1.json").is_file()
        assert (state_dirx / "ns_2.json").is_file()
        assert (state_dirx / "ns_3.json").is_file()
        # Check file contents
        with (state_dirx / "ns_1.json").open("r", encoding="utf-8") as fh:
            assert json.load(fh) == {"a": 123, "b": "abc"}
        with (state_dirx / "ns_2.json").open("r", encoding="utf-8") as fh:
            assert json.load(fh) == {"c": 234.567, "d": False}
        with (state_dirx / "ns_3.json").open("r", encoding="utf-8") as fh:
            assert json.load(fh) == {"e": 456, "f": "def"}
        # Create a new state object and read back
        state_two = State(state_dirx)
        assert state_two.ns_1.a == 123
        assert state_two.ns_1.b == "abc"
        assert state_two.ns_2.c == 234.567
        assert state_two.ns_2.d == False
        assert state_two.ns_3.e == 456
        assert state_two.ns_3.f == "def"

    def test_state_autosave(self, mocker, tmp_path : Path) -> None:
        """ Check that state registers 'save_all' with atexit """
        # Mock atexit so the save event can be properly triggered
        registered = []
        mk_atexit  = mocker.patch("blockwork.state.atexit")
        def _register(method):
            nonlocal registered
            registered.append(method)
        mk_atexit.register.side_effect = _register
        # Check nothing is registered
        assert len(registered) == 0
        # Create a state object
        state_dirx = tmp_path / "state"
        state      = State(state_dirx)
        # Check for the registration
        assert len(registered) == 1
        assert registered[0] == state.save_all
        # Write some values
        state.test_ns.test_var = 123
        # Trigger atexit
        for func in registered:
            func()
        # Check state written out
        with (state_dirx / "test_ns.json").open("r", encoding="utf-8") as fh:
            assert json.load(fh) == {"test_var": 123}

    def test_state_bad_value(self, tmp_path : Path) -> None:
        """ Attempt to store an unsupported value """
        state_dirx = tmp_path / "state"
        state      = State(state_dirx)
        with pytest.raises(StateError) as exc:
            state.test_ns.test_var = [1, 2, 3]
        assert str(exc.value) == "Value of type list is not supported"

    def test_state_alterations(self, tmp_path : Path) -> None:
        """ Namespaces should only write to disk when alterations have been made """
        # Create a namespace
        state_dirx = tmp_path / "state"
        state      = State(state_dirx)
        test_ns    = state.test_ns
        # Check that the alteration flag starts low
        assert not test_ns._StateNamespace__altered
        # Make a change and check the flag is now set
        test_ns.some_var = 123
        assert test_ns._StateNamespace__altered
        # File should be written on save
        ns_file = state_dirx / "test_ns.json"
        assert not ns_file.exists()
        state.save_all()
        assert ns_file.exists()
        mtime = ns_file.stat().st_mtime
        # Check alteration flag is now low
        assert not test_ns._StateNamespace__altered
        # Delay a second to ensure modification time moves forward
        time.sleep(1)
        # Save again, and check no modification occurred
        state.save_all()
        assert ns_file.stat().st_mtime == mtime
        # Delay a second to ensure modification time moves forward
        time.sleep(1)
        # Alter a value
        test_ns.some_var = 234
        assert test_ns._StateNamespace__altered
        # Save again, and check file is updated
        state.save_all()
        new_mtime = ns_file.stat().st_mtime
        assert new_mtime > mtime
        mtime = new_mtime
        # Write the same value a second time, no alteration should be recorded
        test_ns.some_var = 234
        assert not test_ns._StateNamespace__altered
        # Delay a second to ensure modification time moves forward
        time.sleep(1)
        # Save again, and check no modification occurred
        state.save_all()
        assert ns_file.stat().st_mtime == mtime
