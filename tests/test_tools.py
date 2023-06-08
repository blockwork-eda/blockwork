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

from blockwork.tools import Tool, ToolError, Version

class TestTools:
    """ Exercise tool and version definitions """

    def test_tool(self, tmp_path : Path) -> None:
        """ Basic functionality """
        tool_loc = tmp_path / "widget-1.1"
        tool_loc.mkdir()
        # Define the tool
        class Widget(Tool):
            vendor   = "company"
            versions = [
                Version(location = tool_loc,
                        version  = "1.1",
                        env      = { "KEY_A": "VAL_A" },
                        paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] })
            ]
        # Create an instance
        inst = Widget()
        # Check that instance is a singleton
        assert inst is Widget()
        # Check attributes
        assert inst.vendor == "company"
        assert len(inst.versions) == 1
        assert inst.versions[0].version == "1.1"
        assert inst.versions[0].location == tool_loc
        assert inst.versions[0].env == { "KEY_A": "VAL_A" }
        assert inst.versions[0].paths == { "PATH": [Tool.TOOL_ROOT / "bin"] }
        assert inst.versions[0].default
        # Check default version pointer
        assert inst.default is inst.versions[0]
        # Check mapping location
        assert inst.default.id == "company_widget_1.1"
        assert inst.default.path_chunk == Path("company/widget/1.1")

    def test_tool_no_vendor(self, tmp_path : Path) -> None:
        """ Tool without a vendor is assigned to Tool.NO_VENDOR """
        tool_loc = tmp_path / "widget-1.1"
        tool_loc.mkdir()
        # Define the tool
        class Widget(Tool):
            versions = [
                Version(location = tool_loc,
                        version  = "1.1",
                        env      = { "KEY_A": "VAL_A" },
                        paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] })
            ]
        # Create an instance
        inst = Widget()
        # Check that instance is a singleton
        assert inst is Widget()
        # Check attributes
        assert inst.vendor is Tool.NO_VENDOR
        assert len(inst.versions) == 1
        assert inst.versions[0].version == "1.1"
        assert inst.versions[0].location == tool_loc
        assert inst.versions[0].env == { "KEY_A": "VAL_A" }
        assert inst.versions[0].paths == { "PATH": [Tool.TOOL_ROOT / "bin"] }
        assert inst.versions[0].default
        # Check default version pointer
        assert inst.default is inst.versions[0]
        # Check mapping location
        assert inst.default.id == "widget_1.1"
        assert inst.default.path_chunk == Path("widget/1.1")

    def test_tool_multiple_versions(self, tmp_path : Path) -> None:
        """ Multiple versions for a tool """
        loc_1_1 = tmp_path / "widget-1.1"
        loc_1_1.mkdir()
        loc_1_2 = tmp_path / "widget-1.2"
        loc_1_2.mkdir()
        # Define the tool
        class Widget(Tool):
            vendor   = "company"
            versions = [
                Version(location = loc_1_1,
                        version  = "1.1",
                        env      = { "KEY_A": "VAL_A" },
                        paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                        default  = True),
                Version(location = loc_1_2,
                        version  = "1.2",
                        env      = { "KEY_A": "VAL_B" },
                        paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] })
            ]
        # Checks
        inst = Widget()
        assert inst.default is Widget.versions[0]
        assert inst.default.location == loc_1_1
        assert inst.default.version == "1.1"
        assert inst.default.default
        assert inst.default.path_chunk == Path("company/widget/1.1")
        # Lookup a version
        assert inst.get("1.2") is Widget.versions[1]
        assert inst.get("1.2").location == loc_1_2
        assert inst.get("1.2").version == "1.2"
        assert not inst.get("1.2").default 
        assert inst.get("1.2").path_chunk == Path("company/widget/1.2")
        # Iterate all versions
        assert [x for x in inst] == [Widget.versions[0], Widget.versions[1]]

    def test_tool_bad_versions(self, tmp_path : Path) -> None:
        """ Test bad version lists """
        # Not a list
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = { "1.1": True }
            Widget()
        assert str(exc.value) == "Versions of tool widget must be a list"
        # Not a list of version objects
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = ["1.1", False]
            Widget()
        assert str(exc.value) == "Versions of tool widget must be a list of Version objects"
        # Bad location
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [Version(version="1.0", location=tmp_path / "widget")]
            Widget()
        assert str(exc.value) == f"Bad location given for version 1.0: {tmp_path / 'widget'}"
        # Missing version
        (tmp_path / "widget").mkdir()
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [Version(version="", location=tmp_path / "widget")]
            Widget()
        assert str(exc.value) == "A version must be specified"
        # Bad paths
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [Version(version="1.0", location=tmp_path / "widget", paths=[tmp_path / "hi"])]
            Widget()
        assert str(exc.value) == "Paths must be specified as a dictionary"
        # Bad path dictionary
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [Version(version="1.0", location=tmp_path / "widget", paths={ "A": tmp_path / "hi" })]
            Widget()
        assert str(exc.value) == "Path keys must be strings and values must be lists"
        # Bad path objects
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [Version(version="1.0", location=tmp_path / "widget", paths={ "A": ["/a/b/c"] })]
            Widget()
        assert str(exc.value) == "Path entries must be of type pathlib.Path"
        # Bad default
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [Version(version="1.0", location=tmp_path / "widget", default=123)]
            Widget()
        assert str(exc.value) == "Default must be either True or False"

    def test_tool_version_clashes(self, tmp_path : Path) -> None:
        """ Colliding versions or multiple defaults """
        tool_loc = tmp_path / "widget"
        tool_loc.mkdir()
        # Duplicate versions
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [
                    Version(version="1.1", location=tool_loc),
                    Version(version="1.1", location=tool_loc),
                ]
            Widget()
        assert str(exc.value) == "Duplicate version 1.1 for tool widget from vendor N/A"
        # Multiple defaults
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [
                    Version(version="1.1", location=tool_loc, default=True),
                    Version(version="1.2", location=tool_loc, default=True),
                ]
            Widget()
        assert str(exc.value) == "Multiple versions marked default for tool widget from vendor N/A"
        # No default
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [
                    Version(version="1.1", location=tool_loc),
                    Version(version="1.2", location=tool_loc),
                ]
            Widget()
        assert str(exc.value) == "No version of tool widget from vendor N/A marked as default"

