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
from typing import List, Optional, Union

from .tool import Tool, ToolError

class Registry:

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
        vendor      = vend_or_name if name else Tool.NO_VENDOR
        name        = name if name else vend_or_name
        tool : Tool = self.tools.get((vendor, name), None)
        if not tool:
            return None
        elif version:
            return tool.get(version)
        else:
            return tool.default
