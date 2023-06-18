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
from datetime import datetime
from pathlib import Path

import pytest

from blockwork.bootstrap import Bootstrap, BootstrapStep
from blockwork.context import Context


class TestBootstrap:

    @pytest.fixture(autouse=True)
    def reset_bootstrap(self):
        yield
        Bootstrap.REGISTERED.clear()

    @pytest.fixture()
    def context(self, tmp_path : Path) -> Context:
        bw_yaml = tmp_path / ".bw.yaml"
        with bw_yaml.open("w", encoding="utf-8") as fh:
            fh.write("!Blockwork\n"
                     "project: test\n")
        return Context(tmp_path)

    def test_bootstrap(self, mocker, context : Context) -> None:
        """ Exercise bootstrap registration and invocation """
        # Mock logging
        mk_log = mocker.patch("blockwork.bootstrap.logging")
        # Choose test directories
        bs_dir    = context.host_root / "bootstrap"
        test_file = context.host_root / "test.txt"
        bs_dir.mkdir(parents=True, exist_ok=True)
        # Define a bootstrapping step
        with (bs_dir / "step_a.py").open("w", encoding="utf-8") as fh:
            fh.write("from blockwork.bootstrap import Bootstrap\n"
                     "from pathlib import Path\n"
                     "@Bootstrap.register()\n"
                     "def bs_step_a(context, last_run):\n"
                     f"    Path('{test_file.as_posix()}').write_text('hello world\\n')\n"
                     "    return False\n")
        # Setup bootstrapping
        # NOTE: Deliberate repeat in the paths list to check items are registered
        #       only once
        assert len(Bootstrap.REGISTERED.keys()) == 0
        Bootstrap.setup(context.host_root, ["bootstrap.step_a", "bootstrap.step_a"])
        assert len(Bootstrap.REGISTERED.keys()) == 1
        assert list(Bootstrap.REGISTERED.keys())[0] == "bootstrap__step_a__bs_step_a"
        # Check registered step
        step = list(Bootstrap.REGISTERED.values())[0]
        assert isinstance(step, BootstrapStep)
        assert step.full_path == "bootstrap.step_a.bs_step_a"
        assert callable(step.method)
        assert step.check_point is None
        # Check test file does not exist yet
        assert not test_file.exists()
        # Invoke bootstrap steps
        ts_pre = datetime.now()
        Bootstrap.invoke(context)
        ts_post = datetime.now()
        # Check that the test file exists now
        assert test_file.exists()
        assert test_file.read_text() == "hello world\n"
        # Check that state recorded bootstrap step being run
        assert isinstance(context.state.bootstrap.get(step.id), str)
        ts_step = datetime.fromisoformat(context.state.bootstrap.get(step.id))
        assert ts_pre < ts_step
        assert ts_post > ts_step
        # Check for log messages
        mk_log.info.assert_called_with(f"Ran bootstrap step '{step.full_path}'")

    def test_bootstrap_check_pointing(self, mocker, context : Context) -> None:
        """ Use a check point file to reduce redundant invocations """
        # Mock logging
        mk_log = mocker.patch("blockwork.bootstrap.logging")
        mk_log.info.side_effect = print
        # Choose test directories
        bs_dir    = context.host_root / "bootstrap"
        test_file = context.host_root / "test.txt"
        chk_point = context.host_root / "check_point.txt"
        bs_dir.mkdir(parents=True, exist_ok=True)
        chk_point.write_text("abc\n")
        # Define a bootstrapping step
        with (bs_dir / "step_b.py").open("w", encoding="utf-8") as fh:
            fh.write("from blockwork.bootstrap import Bootstrap\n"
                     "from pathlib import Path\n"
                     f"@Bootstrap.register(check_point=Path('{chk_point}'))\n"
                     "def bs_step_b(context, last_run):\n"
                     f"    Path('{test_file.as_posix()}').write_text('hello world\\n')\n"
                     "    return False\n")
        # Setup and run bootstrapping for the first time
        Bootstrap.setup(context.host_root, ["bootstrap.step_b"])
        ts_pre_a = datetime.now()
        Bootstrap.invoke(context)
        ts_post_a = datetime.now()
        # Check bs_step_b was run
        ts_step = datetime.fromisoformat(context.state.bootstrap.get("bootstrap__step_b__bs_step_b"))
        assert ts_pre_a <= ts_step
        assert ts_post_a >= ts_step
        mk_log.info.assert_called_with("Ran bootstrap step 'bootstrap.step_b.bs_step_b'")
        mk_log.info.reset_mock()
        assert test_file.exists()
        # Remove test file (to help detect if method runs again)
        test_file.unlink()
        # Invoke bootstrapping again
        ts_pre_b = datetime.now()
        Bootstrap.invoke(context)
        # Check bs_step_b was NOT run
        ts_step = datetime.fromisoformat(context.state.bootstrap.get("bootstrap__step_b__bs_step_b"))
        assert ts_step < ts_pre_b
        # mk_log.info.assert_called_with("Bootstrap step 'bootstrap.step_b.bs_step_b' is already up to date")
        mk_log.info.reset_mock()
        assert not test_file.exists()
        # Modify the checkpoint file
        pre_mtime = datetime.fromtimestamp(chk_point.stat().st_mtime)
        print(f"PRE MTIME: {pre_mtime}")
        chk_point.write_text("def\n")
        post_mtime = datetime.fromtimestamp(chk_point.stat().st_mtime)
        print(f"POST MTIME: {post_mtime}")
        print(f"POST > PRE: {post_mtime > pre_mtime}")
        # Invoke bootstrapping again
        ts_pre_c = datetime.now()
        Bootstrap.invoke(context)
        ts_post_c = datetime.now()
        # Check bs_step_b WAS run
        print(f"OLD TS: {ts_step}")
        ts_step = datetime.fromisoformat(context.state.bootstrap.get("bootstrap__step_b__bs_step_b"))
        print(f"TS: {ts_step}, C: {ts_pre_c}, {ts_post_c}, B: {ts_pre_b}, A: {ts_pre_a}, {ts_post_a}")
        assert ts_pre_c <= ts_step
        assert ts_post_c >= ts_step
        mk_log.info.assert_called_with("Ran bootstrap step 'bootstrap.step_b.bs_step_b'")
        mk_log.info.reset_mock()
        assert test_file.exists()
        assert False

    def test_bootstrap_last_run(self, mocker, context : Context) -> None:
        """ Use the 'last_run' variable to manually test out-of-date-ness """
        # Mock logging
        mk_log = mocker.patch("blockwork.bootstrap.logging")
        # Choose test directories
        bs_dir    = context.host_root / "bootstrap"
        test_file = context.host_root / "test.txt"
        bs_dir.mkdir(parents=True, exist_ok=True)
        # Define a bootstrapping step
        with (bs_dir / "step_c.py").open("w", encoding="utf-8") as fh:
            fh.write("from blockwork.bootstrap import Bootstrap\n"
                     "from pathlib import Path\n"
                     "from datetime import datetime\n"
                     f"@Bootstrap.register()\n"
                     "def bs_step_c(context, last_run):\n"
                     "    if last_run > datetime.min:\n"
                     "        return True\n"
                     f"    Path('{test_file.as_posix()}').write_text('hello world\\n')\n"
                     "    return False\n")
        # Setup and run bootstrapping for the first time
        Bootstrap.setup(context.host_root, ["bootstrap.step_c"])
        ts_pre_a = datetime.now()
        Bootstrap.invoke(context)
        ts_post_a = datetime.now()
        # Check bs_step_c was run
        ts_step = datetime.fromisoformat(context.state.bootstrap.get("bootstrap__step_c__bs_step_c"))
        assert ts_pre_a <= ts_step
        assert ts_post_a >= ts_step
        mk_log.info.assert_called_with("Ran bootstrap step 'bootstrap.step_c.bs_step_c'")
        mk_log.info.reset_mock()
        assert test_file.exists()
        # Remove test file (to help detect if method runs again)
        test_file.unlink()
        # Invoke bootstrapping again
        ts_pre_b = datetime.now()
        Bootstrap.invoke(context)
        # Check bs_step_c was NOT run
        ts_step = datetime.fromisoformat(context.state.bootstrap.get("bootstrap__step_c__bs_step_c"))
        assert ts_step < ts_pre_b
        mk_log.info.assert_called_with("Bootstrap step 'bootstrap.step_c.bs_step_c' is already up to date")
        mk_log.info.reset_mock()
        assert not test_file.exists()
