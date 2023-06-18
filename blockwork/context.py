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
from pathlib import Path
from typing import Optional

from .config import Blockwork, Config
from .state import State
from .tools.registry import Registry

class Context:
    """ Tracks the working directory and project configuration """

    def __init__(self,
                 root     : Optional[Path] = None,
                 cfg_file : str            = ".bw.yaml") -> None:
        self.__file      = cfg_file
        self.__host_root = self.locate_root(root or Path.cwd())

    @property
    def host_root(self) -> Path:
        return self.__host_root

    @property
    @functools.lru_cache()
    def host_scratch(self) -> Path:
        # Substitute for {project} if required
        subbed = self.config.host_scratch.format(project=self.config.project)
        # Resolve to an absolute path
        if subbed.startswith("/"):
            path = Path(subbed)
        else:
            path = self.__host_root / subbed
        # Fully resolve
        path = path.resolve().absolute()
        # Ensure it exists
        path.mkdir(exist_ok=True, parents=True)
        return path

    @property
    @functools.lru_cache()
    def host_state(self) -> Path:
        # Substitute for {project} if required
        subbed = self.config.host_state.format(project=self.config.project)
        # Resolve to an absolute path
        if subbed.startswith("/"):
            path = Path(subbed)
        else:
            path = self.__host_root / subbed
        # Fully resolve
        path = path.resolve().absolute()
        # Ensure it exists
        path.mkdir(exist_ok=True, parents=True)
        return path

    @property
    def container_root(self) -> Path:
        return Path(self.config.root)

    @property
    def container_scratch(self) -> Path:
        return Path(self.config.scratch)

    @property
    def file(self) -> str:
        return self.__file

    @property
    def config_path(self) -> Path:
        return self.__host_root / self.__file

    def locate_root(self, under : Path) -> Path:
        current = under
        while True:
            if (path := (current / self.__file)).exists() and path.is_file():
                return current
            if (nxtdir := current.parent).samefile(current):
                break
            current = nxtdir
        raise Exception(f"Could not identify work area in parents of {under}")

    @property
    @functools.lru_cache()
    def config(self) -> Blockwork:
        obj = Config.parse(self.config_path)
        if not isinstance(obj, Blockwork):
            raise Exception(f"Expected Blockwork object got {type(obj).__name__}: {self.config_path}")
        return obj

    @property
    @functools.lru_cache()
    def state(self) -> State:
        return State(self.host_state)

    @property
    @functools.lru_cache()
    def registry(self) -> Registry:
        return Registry(self.host_root, self.config.tooldefs)
