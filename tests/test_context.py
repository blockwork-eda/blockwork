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

from pathlib import Path

import pytest

from blockwork.common.yaml import YamlConversionError
from blockwork.config import Blockwork
from blockwork.context import Context
from blockwork.state import State


class TestContext:
    def test_context(self, tmp_path: Path) -> None:
        """Context should recognise the .bw.yaml file"""
        root = tmp_path / "project"
        bw_yaml = root / ".bw.yaml"
        infra = root / "infra"
        infra.mkdir(parents=True)
        # Create a tool definition
        with (infra / "tools.py").open("w", encoding="utf-8") as fh:
            fh.write(
                "from pathlib import Path\n"
                "from blockwork.tools import Tool, Version\n"
                "class ToolA(Tool):\n"
                f"  versions = [Version('1.1', Path('{infra}'))]\n"
            )
        # Create a configuration file
        with bw_yaml.open("w", encoding="utf-8") as fh:
            fh.write("!Blockwork\nproject: test_project\nroot: /a/b\ntooldefs:\n  - infra.tools\n")
        # Create a context
        ctx = Context(root)
        assert ctx.host_root == root
        assert ctx.host_scratch.samefile(tmp_path / "test_project.scratch")
        assert ctx.host_state.samefile(tmp_path / "test_project.state")
        assert ctx.host_scratch.exists()
        assert ctx.host_state.exists()
        assert ctx.container_root == Path("/a/b")
        assert ctx.container_scratch == Path("/scratch")
        assert ctx.file == Path(".bw.yaml")
        assert ctx.config_path == bw_yaml
        assert isinstance(ctx.config, Blockwork)
        assert ctx.config.project == "test_project"

    def test_context_dig(self, tmp_path: Path) -> None:
        """Context should recognise the .bw.yaml file in a parent layer"""
        bw_yaml = tmp_path / ".bw.yaml"
        infra = tmp_path / "infra"
        infra.mkdir()
        # Create a tool definition
        with (infra / "tools.py").open("w", encoding="utf-8") as fh:
            fh.write(
                "from pathlib import Path\n"
                "from blockwork.tools import Tool, Version\n"
                "class ToolA(Tool):\n"
                f"  versions = [Version('1.1', Path('{infra}'))]\n"
            )
        # Create a configuration file
        with bw_yaml.open("w", encoding="utf-8") as fh:
            fh.write("!Blockwork\nproject: test_project\nroot: /a/b\ntooldefs:\n  - infra.tools\n")
        # Create a context in a sub-path
        sub_path = tmp_path / "a" / "b" / "c"
        sub_path.mkdir(parents=True)
        ctx = Context(sub_path)
        assert ctx.host_root == tmp_path
        assert ctx.container_root == Path("/a/b")
        assert ctx.file == Path(".bw.yaml")
        assert ctx.config_path == bw_yaml
        assert isinstance(ctx.config, Blockwork)
        assert ctx.config.project == "test_project"

    def test_context_bad_path(self, tmp_path: Path) -> None:
        """A bad root should raise an exception"""
        with pytest.raises(Exception) as exc:
            Context(tmp_path)
        assert str(exc.value) == f"Could not identify work area in parents of {tmp_path}"

    def test_context_bad_config(self, tmp_path: Path) -> None:
        """A malformed configuration should raise an exception"""
        bw_yaml = tmp_path / ".bw.yaml"
        with bw_yaml.open("w", encoding="utf-8") as fh:
            fh.write("blargh\n")
        with pytest.raises(YamlConversionError):
            _ = Context(tmp_path).config

    def test_context_state(self, tmp_path: Path) -> None:
        """Check that a state object is created at the right path"""
        bw_yaml = tmp_path / ".bw.yaml"
        with bw_yaml.open("w", encoding="utf-8") as fh:
            fh.write("!Blockwork\nproject: test\nhost_state: .my_{project}_state\n")
        ctx = Context(tmp_path)
        assert isinstance(ctx.state, State)
        assert ctx.state._State__location == tmp_path / ".my_test_state"

    def test_context_root_dir(self, tmp_path: Path) -> None:
        """Test that {root_dir} substitution works for scratch and state directories"""
        root = tmp_path / "other_dir"
        root.mkdir(exist_ok=True)
        bw_yaml = root / ".bw.yaml"
        # Create a configuration file
        with bw_yaml.open("w", encoding="utf-8") as fh:
            fh.write(
                "!Blockwork\n"
                "project: test_project\n"
                "host_scratch: ../{root_dir}.scratch\n"
                "host_state: ../{root_dir}.state\n"
            )
        # Create a context
        ctx = Context(root)
        assert ctx.host_root == root
        assert ctx.host_scratch.samefile(tmp_path / "other_dir.scratch")
        assert ctx.host_state.samefile(tmp_path / "other_dir.state")
        assert ctx.host_scratch.exists()
        assert ctx.host_state.exists()
