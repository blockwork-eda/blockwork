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
from typing import List, Tuple, Union

import click
from click.core import Command, Option

from ..foundation import Foundation
from ..tools import Tool, ToolMode, Version

class BwExecCommand(Command):
    """ Standard argument handling for commands that launch a container """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params.insert(0,
                           Option(("--tool", "-t"),
                                  type=str,
                                  multiple=True,
                                  default=[],
                                  help="Bind specific tools into the shell, if "
                                       "omitted then all known tools will be "
                                       "bound. Either use the form "
                                       "'--tool <NAME>' or '--tool <NAME>=<VERSION>' "
                                       "where a specific version other than the "
                                       "default is desired. To specify a vendor use "
                                       "the form '--tool <VENDOR>:<NAME>(=<VERSION>)'."))
        self.params.insert(0,
                           Option(("--no-tools", ),
                                  is_flag=True,
                                  default=False,
                                  help="Do not bind any tools by default"))
        self.params.insert(0,
                           Option(("--tool-mode", ),
                                  type=click.Choice(ToolMode, case_sensitive=False),
                                  default="readonly",
                                  help="Set the file mode used when binding tools "
                                       "to enable write access. Legal values are "
                                       "either 'readonly' or 'readwrite', defaults "
                                       "to 'readonly'."))
        self.params.insert(0,
                           Option(("--no-tools", ),
                                  is_flag=True,
                                  default=False,
                                  help="Do not bind any tools by default"))

    @staticmethod
    def decode_tool(fullname : str) -> Tuple[str, str, Union[str, None]]:
        """
        Decode a tool vendor, name, and version from a string - in one of the
        forms <VENDOR>:<NAME>=<VERSION>, <NAME>=<VERSION>, <VENDOR>:<NAME>, or
        just <NAME>. Where a vendor is not provided, NO_VENDOR is assumed. Where
        no version is provided None is returned to select the default variant

        :param fullname:    Encoded tool using one of the forms described.
        :returns:           Tuple of vendor, name, and version
        """
        fullname, version, *_ = (fullname + "=").split("=")
        vendor, name = (Tool.NO_VENDOR + ":" + fullname).split(":")[-2:]
        return vendor, name, (version or None)

    @staticmethod
    def set_tool_versions(tools : List[str]) -> None:
        for vendor, name, version in map(BwExecCommand.decode_tool, tools):
            if version is not None:
                Tool.select_version(vendor, name, version)

    @staticmethod
    def bind_tools(container : Foundation,
                   no_tools  : bool,
                   tools     : List[str],
                   tool_mode : ToolMode) -> None:
        readonly = (tool_mode == ToolMode.READONLY)
        # If tools are provided, process them for default version overrides
        BwExecCommand.set_tool_versions(tools)
        # If auto-binding is disabled, only bind specified tools
        if no_tools:
            for vendor, name, version in map(BwExecCommand.decode_tool, tools):
                matched : Version = Tool.get(vendor, name, version or None)
                if not matched:
                    raise Exception(f"Failed to identify tool '{vendor}:{name}={version}'")
                logging.info(f"Binding tool {matched.tool.name} from {matched.tool.vendor} "
                            f"version {matched.version} into shell")
                container.add_tool(matched, readonly=readonly)
        # Otherwise, bind all default tool versions
        else:
            logging.info("Binding all tools into shell")
            for tool in Tool.get_all().values():
                container.add_tool(tool, readonly=readonly)
