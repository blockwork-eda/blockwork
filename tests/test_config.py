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
        """ Simple project configuration """
        cfg = Config.parse_str("!Blockwork\n"
                               "project: test_project\n"
                               "tooldefs:\n"
                               "  - infra.tools.set_a\n"
                               "  - infra.tools.set_b\n")
        assert isinstance(cfg, Blockwork)
        assert cfg.project == "test_project"
        assert cfg.tooldefs == ["infra.tools.set_a", "infra.tools.set_b"]

    def test_config_error(self) -> None:
        """ Different syntax errors """
        # Missing project name
        with pytest.raises(ConfigError) as exc:
            Config.parse_str("!Blockwork\n"
                             "tooldefs: [a, b, c]\n")
        assert isinstance(exc.value.obj, Blockwork)
        assert exc.value.field == "project"
        assert str(exc.value) == "Project name has not been specified"
        # Tool definitions not a list
        with pytest.raises(ConfigError) as exc:
            Config.parse_str("!Blockwork\n"
                             "project: test\n"
                             "tooldefs: abcd\n")
        assert isinstance(exc.value.obj, Blockwork)
        assert exc.value.field == "tooldefs"
        assert str(exc.value) == "Tool definitions must be a list"
        # Tool definitions not a list of strings
        with pytest.raises(ConfigError) as exc:
            Config.parse_str("!Blockwork\n"
                             "project: test\n"
                             "tooldefs: [1, 2, 3]\n")
        assert isinstance(exc.value.obj, Blockwork)
        assert exc.value.field == "tooldefs"
        assert str(exc.value) == "Tool definitions must be a list of strings"
