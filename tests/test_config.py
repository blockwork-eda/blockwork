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

from blockwork.config import Blockwork
import blockwork.common.yamldataclasses as yamldataclasses

BlockworkConfig = yamldataclasses.SimpleParser(Blockwork)

class TestConfig:

    def test_config(self) -> None:
        """ Custom project configuration """
        cfg = BlockworkConfig.parse_str("!Blockwork\n"
                                        "project: test_project\n"
                                        "root: /my_root\n"
                                        "scratch: /my_scratch\n"
                                        "host_state: ../my_{project}_state\n"
                                        "host_scratch: ../my_{project}_scratch\n"
                                        "bootstrap:\n"
                                        "  - infra.bootstrap.step_a\n"
                                        "  - infra.bootstrap.step_b\n"
                                        "tooldefs:\n"
                                        "  - infra.tools.set_a\n"
                                        "  - infra.tools.set_b\n")
        assert isinstance(cfg, Blockwork)
        assert cfg.project == "test_project"
        assert cfg.root == "/my_root"
        assert cfg.scratch == "/my_scratch"
        assert cfg.host_state == "../my_{project}_state"
        assert cfg.host_scratch == "../my_{project}_scratch"
        assert cfg.bootstrap == ["infra.bootstrap.step_a", "infra.bootstrap.step_b"]
        assert cfg.tooldefs == ["infra.tools.set_a", "infra.tools.set_b"]

    def test_config_default(self) -> None:
        """ Simple project configuration using mostly default values """
        cfg = BlockworkConfig.parse_str("!Blockwork\n"
                                        "project: test_project\n")
        assert isinstance(cfg, Blockwork)
        assert cfg.project == "test_project"
        assert cfg.root == "/project"
        assert cfg.scratch == "/scratch"
        assert cfg.host_state == "../{project}.state"
        assert cfg.host_scratch == "../{project}.scratch"
        assert cfg.bootstrap == []
        assert cfg.tooldefs == []

    def test_config_error(self) -> None:
        """ Different syntax errors """
        # Missing project name
        with pytest.raises(yamldataclasses.YamlMissingFieldsError) as exc:
            BlockworkConfig.parse_str("!Blockwork\n"
                                      "tooldefs: [a, b, c]\n")
        assert "project" in exc.value.fields
        # Bad root directory (integer)
        with pytest.raises(yamldataclasses.YamlFieldError) as exc:
            BlockworkConfig.parse_str("!Blockwork\n"
                                      "project: test\n"
                                      "root: 123\n")
        assert exc.value.field == "root"
        assert isinstance(exc.value.orig_ex, TypeError)
        # Bad root directory (relative path)
        with pytest.raises(yamldataclasses.YamlFieldError) as exc:
            BlockworkConfig.parse_str("!Blockwork\n"
                                      "project: test\n"
                                      "root: a/b\n")
        assert exc.value.field == "root"
        # Bad scratch directory (integer)
        with pytest.raises(yamldataclasses.YamlFieldError) as exc:
            BlockworkConfig.parse_str("!Blockwork\n"
                                      "project: test\n"
                                      "scratch: 123\n")
        assert exc.value.field == "scratch"
        # Bad scratch directory (relative path)
        with pytest.raises(yamldataclasses.YamlFieldError) as exc:
            BlockworkConfig.parse_str("!Blockwork\n"
                                      "project: test\n"
                                      "scratch: a/b\n")
        assert exc.value.field == "scratch"
        # Bad scratch directory (integer)
        with pytest.raises(yamldataclasses.YamlFieldError) as exc:
            BlockworkConfig.parse_str("!Blockwork\n"
                                      "project: test\n"
                                      "host_scratch: 123\n")
        assert exc.value.field == "host_scratch"
        # Bad state directory (integer)
        with pytest.raises(yamldataclasses.YamlFieldError) as exc:
            BlockworkConfig.parse_str("!Blockwork\n"
                                      "project: test\n"
                                      "host_state: 123\n")
        assert exc.value.field == "host_state"
        # Bootstrap and tool definitions
        for key, name in (("bootstrap", "Bootstrap"), ("tooldefs", "Tool")):
            # Definitions not a list
            with pytest.raises(yamldataclasses.YamlFieldError) as exc:
                BlockworkConfig.parse_str("!Blockwork\n"
                                          "project: test\n"
                                          f"{key}: abcd\n")
            assert exc.value.field == key
            # Definitions not a list of strings
            with pytest.raises(yamldataclasses.YamlFieldError) as exc:
                BlockworkConfig.parse_str("!Blockwork\n"
                                          "project: test\n"
                                          f"{key}: [1, 2, 3]\n")
            assert exc.value.field == key
