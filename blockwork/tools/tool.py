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
from typing import Dict, Iterable, List, Optional


class ToolError(Exception):
    pass


class Version:

    def __init__(self,
                 version  : str,
                 location : Path,
                 env      : Optional[Dict[str, str]]       = None,
                 paths    : Optional[Dict[str, List[str]]] = None,
                 requires : Optional[List["Tool"]]         = None,
                 default  : bool                           = False) -> None:
        self.version = version
        self.location = location
        self.env = env or {}
        self.paths = paths or {}
        self.requires = requires
        self.default = default
        self.tool : Optional["Tool"] = None
        # Sanitise arguments
        self.requires = self.requires or []
        self.paths    = self.paths or {}
        self.env      = self.env or {}
        if not isinstance(self.location, Path) or not self.location.exists():
            raise ToolError(f"Bad location given for version {self.version}: {self.location}")
        if not isinstance(self.version, str) or len(self.version.strip()) == 0:
            raise ToolError("A version must be specified")
        if not isinstance(self.paths, dict):
            raise ToolError("Paths must be specified as a dictionary")
        if not all(isinstance(k, str) and isinstance(v, list) for k, v in self.paths.items()):
            raise ToolError("Path keys must be strings and values must be lists")
        if not all(isinstance(y, Path) for x in self.paths.values() for y in x):
            raise ToolError("Path entries must be of type pathlib.Path")
        if not isinstance(self.default, bool):
            raise ToolError("Default must be either True or False")

    @property
    @functools.lru_cache()
    def id_tuple(self) -> str:
        return (*self.tool.base_id_tuple, self.version)

    @property
    @functools.lru_cache()
    def id(self) -> str:
        return "_".join(self.id_tuple)

    @property
    def path_chunk(self) -> Path:
        if self.tool.vendor is not Tool.NO_VENDOR:
            return Path(self.tool.vendor.lower()) / self.tool.name / self.version
        else:
            return Path(self.tool.name) / self.version


class Tool(ABC):
    """ Base class for tools """
    # Tool root locator
    TOOL_ROOT : Path = Path("/__tool_root__")

    # Default vendor
    NO_VENDOR = "N/A"

    # Singleton handling
    INSTANCES = {}

    # Placeholders
    vendor   : Optional[str]           = None
    versions : Optional[List[Version]] = None

    def __new__(cls) -> "Tool":
        # Maintain a singleton instance of each tool definition
        tool_id = id(cls)
        if tool_id not in Tool.INSTANCES:
            Tool.INSTANCES[tool_id] = super().__new__(cls)
        return Tool.INSTANCES[tool_id]

    def __init__(self) -> None:
        self.vendor = self.vendor.strip() if isinstance(self.vendor, str) else Tool.NO_VENDOR
        self.versions = self.versions or []
        if not isinstance(self.versions, list):
            raise ToolError(f"Versions of tool {self.name} must be a list")
        if not all(isinstance(x, Version) for x in self.versions):
            raise ToolError(f"Versions of tool {self.name} must be a list of Version objects")
        # If only one version is defined, make that the default
        if len(self.versions) == 1:
            self.versions[0].default = True
            self.versions[0].tool = self
            self.default = self.versions[0]
        else:
            # Check for collisions between versions and multiple defaults
            self.default = None
            version_nums = []
            for version in self.versions:
                version.tool = self
                # Check for multiple defaults
                if version.default:
                    if self.default is not None:
                        raise ToolError(f"Multiple versions marked default for tool {self.name} "
                                        f"from vendor {self.vendor}")
                    self.default = version
                # Check for repeated version numbers
                if version.version in version_nums:
                    raise ToolError(f"Duplicate version {version.version} for tool "
                                    f"{self.name} from vendor {self.vendor}")
                version_nums.append(version.version)
            # Check the default has been identified
            if self.default is None:
                raise ToolError(f"No version of tool {self.name} from vendor "
                                f"{self.vendor} marked as default")

    def __iter__(self) -> Iterable[Version]:
        yield from self.versions

    @property
    @functools.lru_cache()
    def name(self) -> str:
        return type(self).__name__.lower()
    
    @property
    @functools.lru_cache()
    def base_id_tuple(self) -> str:
        if self.vendor is Tool.NO_VENDOR:
            return (self.name, )
        else:
            return (self.vendor, self.name)

    @functools.lru_cache()
    def get(self, version : str) -> Version:
        match = [x for x in self.versions if x.version == version]
        return match[0] if match else None
