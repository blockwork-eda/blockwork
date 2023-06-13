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

import importlib
import inspect
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, List, Optional, Union

from .tool import Tool, ToolError

class Registry:
    """
    Discovers and registers all tools defined in lists of Python modules

    :param root:    Root path under which Python modules are defined, this is added
                    to the PYTHONPATH prior to discovery
    :param imports: List of Python modules to import, either system wide or relative
                    to the root
    """

    def __init__(self, root : Path, imports : List[str]) -> None:
        self.root = root
        self.imports = imports
        # Gather all versions of all tools
        self.tools = defaultdict(dict)
        for path in self.imports:
            for tool in Registry.search(self.root, path):
                tool : Tool = tool()
                self.tools[tool.base_id_tuple] = tool

    @staticmethod
    def search(root : Path, import_from : str) -> List[Tool]:
        """
        Import all Tool definitions from a given Python module that's either system wide
        or relative to a given root path.

        :param root:        Root path under which Python modules are defined, this is added
                            to the PYTHONPATH prior to discovery
        :param import_from: Python module name to import from
        :returns:           List of discovered Tool classes
        """
        if root.absolute().as_posix() not in sys.path:
            sys.path.append(root.absolute().as_posix())
        mod   = importlib.import_module(import_from)
        tools = [y for _, y in inspect.getmembers(mod) if (y is not Tool) and
                                                          inspect.isclass(y) and
                                                          issubclass(y, Tool)]
        if len(tools) == 0:
            raise ToolError(f"Located no subclasses of Tool in {import_from}")
        return tools

    def get(self,
            vend_or_name : str,
            name         : Optional[str] = None,
            version      : Optional[str] = None) -> Union[Tool, None]:
        """
        Retrieve a tool registered for a given vendor, name, and version. If only a
        name is given, then NO_VENDOR is assumed for the vendor field. If no version
        is given, then the default version is returned. If no tool is known for the
        specification, then None is returned.

        :param vend_or_name:    Vendor or tool name is no associated vendor
        :param name:            Name if a vendor is specified
        :param version:         Version of the tool (optional)
        """
        vendor      = vend_or_name.lower() if name else Tool.NO_VENDOR.lower()
        name        = (name if name else vend_or_name).lower()
        tool : Tool = self.tools.get((vendor, name), None)
        if not tool:
            return None
        elif version:
            return tool.get(version)
        else:
            return tool.default

    def __iter__(self) -> Iterable[Tool]:
        """ Iterate through all registered tools """
        yield from self.tools.values()
