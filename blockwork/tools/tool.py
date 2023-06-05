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

import functools
from abc import ABC
from pathlib import Path
from typing import Dict, List, Optional


class ToolError(Exception):
    pass


class Tool(ABC):
    """ Base class for tools """
    # Tool root locator
    TOOL_ROOT : Path = Path("/__tool_root__")

    # Overrideable properties
    requires : Optional[List["Tool"]]          = None
    location : Optional[Path]                  = None
    vendor   : Optional[str]                   = None
    version  : Optional[str]                   = None
    env      : Optional[Dict[str, str]]        = None
    paths    : Optional[Dict[str, List[Path]]] = None

    def __init__(self) -> None:
        # Sanitise arguments
        self.requires = self.requires or []
        self.vendor   = self.vendor.strip() if isinstance(self.vendor, str) else None
        self.paths    = self.paths or {}
        self.env      = self.env or {}
        if not isinstance(self.location, Path) or not self.location.exists():
            raise ToolError(f"Bad location given for tool {self.name}: {self.location}")
        if not isinstance(self.version, str) or len(self.version.strip()) == 0:
            raise ToolError(f"A version must be specified for {self.name}")
        if not isinstance(self.paths, dict):
            raise ToolError("Paths must be specified as a dictionary")
        if not all(isinstance(k, str) and isinstance(v, list) for k, v in self.paths.items()):
            raise ToolError("Path keys must be strings and values must be lists")
        if not all(isinstance(y, Path) for x in self.paths.values() for y in x):
            raise ToolError("Path entries must be of type pathlib.Path")

    @property
    @functools.lru_cache()
    def name(self) -> str:
        return type(self).__name__.lower()

    @property
    @functools.lru_cache()
    def id(self) -> str:
        return f"{self.vendor}_{self.name}_{self.version}"

    @property
    def path_chunk(self) -> Path:
        if self.vendor:
            return Path(self.vendor.lower()) / self.name / self.version
        else:
            return Path(self.name) / self.version
