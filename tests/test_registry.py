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

from blockwork.tools import Registry, Tool, ToolError, Version


class TestToolRegistry:
    """ Exercise the tool registry """

    def test_registry(self, tmp_path : Path) -> None:
        """ Exercise search functionality of the registry """
        # Create some tool definitions
        tools = tmp_path / "tools"
        infra = tmp_path / "infra"
        tools.mkdir()
        infra.mkdir()
        with (infra / "toolset_one.py").open("w", encoding="utf-8") as fh:
            fh.writelines(["from blockwork.tools import Tool, Version\n",
                           "from pathlib import Path\n",
                           "class ToolA(Tool):\n",
                           f"  versions = [Version('1.1', Path('{tools}'))]\n",
                           "\n",
                           "class ToolB(Tool):\n",
                           "  vendor = 'company'\n",
                           f"  versions = [Version('2.3', Path('{tools}'))]\n",
                           "\n",
                           ])
        with (infra / "toolset_two.py").open("w", encoding="utf-8") as fh:
            fh.writelines(["from blockwork.tools import Tool, Version\n",
                           "from pathlib import Path\n",
                           "class ToolC(Tool):\n",
                           "  vendor = 'other'\n",
                           f"  versions = [Version('3.4', Path('{tools}'))]\n",
                           "\n",
                           ])
        # Create  registry
        reg = Registry(tmp_path, ["infra.toolset_one", "infra.toolset_two"])
        assert set(reg.tools.keys()) == {("n/a", "toola"),
                                         ("company", "toolb"),
                                         ("other", "toolc")}
        # Try getting tools
        assert isinstance(reg.get("ToolA"), Version)
        assert isinstance(reg.get("company", "ToolB"), Version)
        assert isinstance(reg.get("other", "ToolC"), Version)
        assert isinstance(reg.get("other", "ToolC", "3.4"), Version)
        # Bad tool lookups
        assert reg.get("blah", "ToolA") is None
        assert reg.get("ToolB") is None
        assert reg.get("company", "ToolC") is None
        assert reg.get("other", "ToolC", "1.2.3") is None
        # Iterate through tool registrations
        tools = [x for x in reg]
        assert all(isinstance(x, Tool) for x in tools)
        assert {x.name for x in tools} == {"toola", "toolb", "toolc"}

    def test_registry_bad_file(self, tmp_path : Path) -> None:
        """ Registry should flag if no Tool definitions found """
        infra = tmp_path / "infra"
        infra.mkdir()
        with (infra / "toolset.py").open("w", encoding="utf-8") as fh:
            fh.writelines(["\n"])
        with pytest.raises(ToolError) as exc:
            Registry(tmp_path, ["infra.toolset"])
        assert str(exc.value) == "Located no subclasses of Tool in infra.toolset"
