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
import logging
import platform
from enum import StrEnum, auto
from pathlib import Path
from typing import Optional

from .config import Blockwork
from .state import State
import blockwork.common.yamldataclasses as yamldataclasses


BlockworkConfig = yamldataclasses.SimpleParser(Blockwork)


class HostArchitecture(StrEnum):
    X86 = auto()
    ARM = auto()

    @classmethod
    @functools.lru_cache()
    def identify(cls) -> "HostArchitecture":
        if "arm" in platform.processor().lower():
            return HostArchitecture.ARM
        else:
            return HostArchitecture.X86


class ContextError(Exception):
    pass


class ContextHostPathError(ContextError):
    pass


class ContextContainerPathError(ContextError):
    pass


class Context:
    """ Tracks the working directory and project configuration """

    def __init__(self,
                 root     : Optional[Path] = None,
                 cfg_file : str            = ".bw.yaml") -> None:
        self.__file      = cfg_file
        self.__host_root = self.locate_root(root or Path.cwd())
        self.__host_arch = HostArchitecture.identify()

    @property
    def host_architecture(self) -> HostArchitecture:
        return self.__host_arch

    @host_architecture.setter
    def host_architecture(self, value : HostArchitecture) -> None:
        if not isinstance(value, HostArchitecture):
            raise ContextError("Must use HostArchitecture enumerated values")
        logging.debug(f"Host architecture set to '{value}'")
        self.__host_arch = value

    @property
    def host_root(self) -> Path:
        return self.__host_root

    @property
    @functools.lru_cache()
    def host_scratch(self) -> Path:
        # Substitute for {project} if required
        subbed = self.config.host_scratch.format(project=self.config.project,
                                                 root_dir=self.host_root.name)
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
        subbed = self.config.host_state.format(project=self.config.project,
                                               root_dir=self.host_root.name)
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
        return BlockworkConfig.parse(self.config_path)

    @property
    @functools.lru_cache()
    def state(self) -> State:
        return State(self.host_state)

    def map_to_container(self, h_path : Path) -> Path:
        """
        Map a path from the host into its equivalent location in the container.

        :param h_path:  Host-side path
        :returns:       Container-side path
        """
        for rel_host, rel_cont in ((self.host_root, self.container_root),
                                   (self.host_scratch, self.container_scratch)):
            if h_path.is_relative_to(rel_host):
                c_path = rel_cont / h_path.relative_to(rel_host)
                break
        else:
            raise ContextHostPathError(f"Path {h_path} is not within the project "
                                       f"working directory {self.host_root} or "
                                       f"scratch area {self.host_scratch}")
        return c_path

    def map_to_host(self, c_path : Path) -> Path:
        """
        Map a path from the container into its equivalent location on the host.

        :param c_path:  Container-side path
        :returns:       Host-side path
        """
        for rel_host, rel_cont in ((self.host_root, self.container_root),
                                   (self.host_scratch, self.container_scratch)):
            if c_path.is_relative_to(rel_cont):
                h_path = rel_host / c_path.relative_to(rel_cont)
                break
        else:
            raise ContextContainerPathError(f"Path {c_path} is not within the project "
                                            f"working directory {self.container_root} "
                                            f"or scratch area {self.container_scratch}")
        return h_path
