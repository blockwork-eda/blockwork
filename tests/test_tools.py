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
from typing import List

import pytest

from blockwork.tools import Invocation, Require, Tool, ToolError, Version

class TestTools:
    """ Exercise tool and version definitions """

    @pytest.fixture(autouse=True)
    def reset_tool(self) -> None:
        """ Clear registrations/singleton instances after each test """
        yield
        Tool.INSTANCES.clear()
        Tool.ACTIONS.clear()

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
        assert inst.base_id == "company_widget"
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
        assert inst.base_id == "widget"
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

    def test_tool_requirement(self, tmp_path : Path) -> None:
        """ Require one tool from another """
        ta_1_1 = tmp_path / "tool_a_1_1"
        ta_1_2 = tmp_path / "tool_a_1_2"
        tb_2_1 = tmp_path / "tool_b_2_1"
        tb_2_2 = tmp_path / "tool_b_2_2"
        for dirx in (ta_1_1, ta_1_2, tb_2_1, tb_2_2):
            dirx.mkdir()
        class ToolA(Tool):
            versions = [Version("1.1", ta_1_1),
                        Version("1.2", ta_1_2, default=True)]
        class ToolB(Tool):
            versions = [Version("2.1", tb_2_1, default=True, requires=[Require(ToolA, "1.1")]),
                        Version("2.2", tb_2_2, requires=[Require(ToolA, "1.2")])]
        inst_a = ToolA()
        inst_b = ToolB()
        assert inst_a.default.version == "1.2"
        assert inst_b.default.version == "2.1"
        assert inst_a.default.requires == []
        assert inst_b.default.requires[0].tool is ToolA
        assert inst_b.default.requires[0].version == "1.1"


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
                versions = [Version(version="1.0", location="/a/b/c")]
            Widget()
        assert str(exc.value) == "Bad location given for version 1.0: /a/b/c"
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

    def test_tool_bad_require(self, tmp_path : Path) -> None:
        tool_loc = tmp_path / "widget"
        tool_loc.mkdir()
        # Non-list of requirements
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [
                    Version(version="1.1", location=tool_loc, requires="ABC"),
                ]
            Widget()
        assert str(exc.value) == "Requirements must be a list"
        # List of non-Require objects
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [
                    Version(version="1.1", location=tool_loc, requires=["ABC"]),
                ]
            Widget()
        assert str(exc.value) == "Requirements must be a list of Require objects"
        # Requirement not referring to another tool
        with pytest.raises(ToolError) as exc:
            class Widget(Tool):
                versions = [
                    Version(version="1.1", location=tool_loc, requires=[Require("ABC")]),
                ]
            Widget()
        assert str(exc.value) == "Requirement tool must be of type Tool"
        # Requirement version not a string
        with pytest.raises(ToolError) as exc:
            class ToolA(Tool):
                versions = [Version(version="1.0", location=tool_loc)]
            class ToolB(Tool):
                versions = [
                    Version(version="1.1", location=tool_loc, requires=[Require(ToolA, 123)]),
                ]
            ToolB()
        assert str(exc.value) == "Requirement version must be None or a string"

    def test_tool_actions(self, tmp_path : Path) -> None:
        """ Define and invoke actions on a tool """
        tool_loc = tmp_path / "widget-1.1"
        tool_loc.mkdir()
        # Define the tool with an action
        class Widget(Tool):
            vendor   = "company"
            versions = [
                Version(location = tool_loc,
                        version  = "1.1",
                        env      = { "KEY_A": "VAL_A" },
                        paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] })
            ]
            @Tool.action("Widget")
            def do_something(self,
                             version : Version,
                             an_arg  : str,
                             *args   : List[str]) -> Invocation:
                return Invocation(
                    version = version,
                    execute = Tool.TOOL_ROOT / "bin" / "widget",
                    args    = [an_arg],
                    display = True,
                    binds   = [Path("/a/b/c")],
                )
            @Tool.action("Widget", default=True)
            def other_thing(self, version : Version, *args : List[str]) -> Invocation:
                return Invocation(version, execute=Tool.TOOL_ROOT / "bin" / "thing")
        # Invoke the 'do_something' action
        act = Widget().get("1.1").get_action("do_something")
        assert callable(act)
        ivk = act("the argument", "ignored")
        assert isinstance(ivk, Invocation)
        # Check attributes of the invocation
        assert ivk.version is Widget().get("1.1")
        assert ivk.execute == Tool.TOOL_ROOT / "bin" / "widget"
        assert ivk.args == ["the argument"]
        assert ivk.display
        assert ivk.interactive
        assert ivk.binds == [Path("/a/b/c")]
        # Get the default action
        act_dft = Widget().get_action("default")
        assert callable(act_dft)
        ivk_dft = act_dft(Widget().get("1.1"), "abc", "123")
        assert isinstance(ivk_dft, Invocation)
        assert ivk_dft.version is Widget().get("1.1")
        assert ivk_dft.execute == Tool.TOOL_ROOT / "bin" / "thing"
        assert ivk_dft.args == []
        assert not ivk_dft.display
        assert not ivk_dft.interactive
        assert ivk_dft.binds == []

    def test_tool_action_bad_register_default(self, tmp_path : Path) -> None:
        """ Attempt to register an action called 'default' """
        tool_loc = tmp_path / "widget-1.1"
        tool_loc.mkdir()
        with pytest.raises(Exception) as exc:
            class Widget(Tool):
                vendor   = "company"
                versions = [
                    Version(location = tool_loc,
                            version  = "1.1",
                            env      = { "KEY_A": "VAL_A" },
                            paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] })
                ]
                @Tool.action("Widget")
                def default(self, version : Version, *args : List[str]) -> Invocation:
                    return Invocation(version, Tool.TOOL_ROOT / "bin" / "blah")
        assert str(exc.value) == (
            "The action name 'default' is reserved, use the default=True option "
            "instead"
        )

    def test_tool_action_none(self, tmp_path : Path) -> None:
        """ Check that a widget with no actions registered returns none """
        tool_loc = tmp_path / "widget-1.1"
        tool_loc.mkdir()
        class Widget(Tool):
            vendor   = "company"
            versions = [
                Version(location = tool_loc,
                        version  = "1.1",
                        env      = { "KEY_A": "VAL_A" },
                        paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] })
            ]
        # Via the tool
        assert Widget().get_action("blah") is None
        # Via the version
        assert Widget().get("1.1").get_action("blah") is None

    def test_tool_action_bad_name(self, tmp_path : Path) -> None:
        """ Check that a non-existent action returns 'None' """
        tool_loc = tmp_path / "widget-1.1"
        tool_loc.mkdir()
        class Widget(Tool):
            vendor   = "company"
            versions = [
                Version(location = tool_loc,
                        version  = "1.1",
                        env      = { "KEY_A": "VAL_A" },
                        paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] })
            ]
            @Tool.action("Widget")
            def blah(self, version : Version, *args : List[str]) -> Invocation:
                return Invocation(version, Tool.TOOL_ROOT / "bin" / "blah")
        # Via the tool
        assert Widget().get_action("not_blah") is None
        # Via the version
        assert Widget().get("1.1").get_action("not_blah") is None
