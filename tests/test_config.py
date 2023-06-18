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

import pytest

from blockwork.config import Blockwork, Config, ConfigError

class TestConfig:

    def test_config(self) -> None:
        """ Custom project configuration """
        cfg = Config.parse_str("!Blockwork\n"
                               "project: test_project\n"
                               "root: /my_root\n"
                               "state_dir: .my_state\n"
                               "bootstrap:\n"
                               "  - infra.bootstrap.step_a\n"
                               "  - infra.bootstrap.step_b\n"
                               "tooldefs:\n"
                               "  - infra.tools.set_a\n"
                               "  - infra.tools.set_b\n")
        assert isinstance(cfg, Blockwork)
        assert cfg.project == "test_project"
        assert cfg.root == "/my_root"
        assert cfg.state_dir == ".my_state"
        assert cfg.bootstrap == ["infra.bootstrap.step_a", "infra.bootstrap.step_b"]
        assert cfg.tooldefs == ["infra.tools.set_a", "infra.tools.set_b"]

    def test_config_default(self) -> None:
        """ Simple project configuration using mostly default values """
        cfg = Config.parse_str("!Blockwork\n"
                               "project: test_project\n")
        assert isinstance(cfg, Blockwork)
        assert cfg.project == "test_project"
        assert cfg.root == "/project"
        assert cfg.state_dir == ".bw_state"
        assert cfg.bootstrap == []
        assert cfg.tooldefs == []

    def test_config_error(self) -> None:
        """ Different syntax errors """
        # Missing project name
        with pytest.raises(ConfigError) as exc:
            Config.parse_str("!Blockwork\n"
                             "tooldefs: [a, b, c]\n")
        assert isinstance(exc.value.obj, Blockwork)
        assert exc.value.field == "project"
        assert str(exc.value) == "Project name has not been specified"
        # Bad root directory (integer)
        with pytest.raises(ConfigError) as exc:
            Config.parse_str("!Blockwork\n"
                             "project: test\n"
                             "root: 123\n")
        assert isinstance(exc.value.obj, Blockwork)
        assert exc.value.field == "root"
        assert str(exc.value) == "Root must be an absolute path"
        # Bad root directory (relative path)
        with pytest.raises(ConfigError) as exc:
            Config.parse_str("!Blockwork\n"
                             "project: test\n"
                             "root: a/b\n")
        assert isinstance(exc.value.obj, Blockwork)
        assert exc.value.field == "root"
        assert str(exc.value) == "Root must be an absolute path"
        # Bad state directory (integer)
        with pytest.raises(ConfigError) as exc:
            Config.parse_str("!Blockwork\n"
                             "project: test\n"
                             "state_dir: 123\n")
        assert isinstance(exc.value.obj, Blockwork)
        assert exc.value.field == "state_dir"
        assert str(exc.value) == "State directory must be a relative path"
        # Bad state directory (absolute path)
        with pytest.raises(ConfigError) as exc:
            Config.parse_str("!Blockwork\n"
                             "project: test\n"
                             "state_dir: /a/b\n")
        assert isinstance(exc.value.obj, Blockwork)
        assert exc.value.field == "state_dir"
        assert str(exc.value) == "State directory must be a relative path"
        # Bootstrap and tool definitions
        for key, name in (("bootstrap", "Bootstrap"), ("tooldefs", "Tool")):
            # Definitions not a list
            with pytest.raises(ConfigError) as exc:
                Config.parse_str("!Blockwork\n"
                                 "project: test\n"
                                 f"{key}: abcd\n")
            assert isinstance(exc.value.obj, Blockwork)
            assert exc.value.field == key
            assert str(exc.value) == f"{name} definitions must be a list"
            # Definitions not a list of strings
            with pytest.raises(ConfigError) as exc:
                Config.parse_str("!Blockwork\n"
                                 "project: test\n"
                                 f"{key}: [1, 2, 3]\n")
            assert isinstance(exc.value.obj, Blockwork)
            assert exc.value.field == key
            assert str(exc.value) == f"{name} definitions must be a list of strings"
