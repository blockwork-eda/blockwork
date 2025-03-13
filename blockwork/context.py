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

import dataclasses
import functools
import hashlib
import importlib
import logging
import os
import platform
import sys
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .build.caching import Cache

from .common import scopes
from .config import Blockwork, BlockworkParser, CachingConfig, CachingParser
from .state import State


@scopes.scope
@dataclasses.dataclass
class DebugScope:
    VERBOSE: bool = False
    VERBOSE_LOCALS: bool = False
    POSTMORTEM: bool = False


class HostArchitecture(StrEnum):
    X86 = auto()
    ARM = auto()

    @classmethod
    @functools.lru_cache
    def identify(cls) -> "HostArchitecture":
        host_proc = platform.processor().lower()
        if "arm" in host_proc or "aarch" in host_proc:
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
    """
    Tracks the working directory and project configuration

    :param root:     Root directory of the project
    :param cfg_file: Name of the Blockwork configuration file to look for
    :param scratch:  Override the scratch folder defined in Blockwork configuration
    """

    def __init__(
        self,
        root: Path | None = None,
        cfg_file: Path = Path(".bw.yaml"),
        scratch: Path | None = None,
        cache_config: Path | None = None,
        cache_enable: bool | None = None,
        cache_targets: bool | None = None,
        cache_expect: bool | None = None,
    ) -> None:
        self.__file = cfg_file
        self.__host_root = self.locate_root(root or Path.cwd())
        self.__host_arch = HostArchitecture.identify()
        self.__scratch = scratch
        self.__timestamp = datetime.now().strftime("D%Y%m%dT%H%M%S")
        self.__cache_config = cache_config
        self.__cache_enable = cache_enable
        self.__cache_targets = cache_targets
        self.__cache_expect = cache_expect

    @property
    def host_architecture(self) -> HostArchitecture:
        return self.__host_arch

    @host_architecture.setter
    def host_architecture(self, value: HostArchitecture) -> None:
        if not isinstance(value, HostArchitecture):
            raise ContextError("Must use HostArchitecture enumerated values")
        logging.debug(f"Host architecture set to '{value}'")
        self.__host_arch = value

    @property
    def host_root(self) -> Path:
        return self.__host_root

    @property
    def host_root_hash(self) -> str:
        return hashlib.md5(self.host_root.absolute().as_posix().encode("utf-8")).hexdigest()

    @property
    @functools.lru_cache  # noqa: B019
    def host_scratch(self) -> Path:
        # If scratch has been provided, use it
        if self.__scratch:
            path = self.__scratch
        else:
            # Substitute for {project} or {root_dir} if required
            subbed = self.config.host_scratch.format(
                project=self.config.project, root_dir=self.host_root.name
            )
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
    @functools.lru_cache  # noqa: B019
    def host_state(self) -> Path:
        # Substitute for {project} or {root_dir} if required
        subbed = self.config.host_state.format(
            project=self.config.project, root_dir=self.host_root.name
        )
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
    @functools.lru_cache  # noqa: B019
    def host_tools(self) -> Path:
        # Substitute for {project} or {root_dir} if required
        subbed = self.config.host_tools.format(
            project=self.config.project, root_dir=self.host_root.name
        )
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
    @functools.lru_cache  # noqa: B019
    def site(self) -> Path:
        # Substitute for {project} or {root_dir} if required
        subbed = self.config.site.format(project=self.config.project, root_dir=self.host_root.name)
        # Resolve to an absolute path
        if subbed.startswith("/"):
            path = Path(subbed)
        else:
            path = self.__host_root / subbed
        # Fully resolve
        path = path.resolve().absolute()
        return path

    @property
    def container_root(self) -> Path:
        return Path(self.config.root)

    @property
    def container_scratch(self) -> Path:
        return Path(self.config.scratch)

    @property
    def container_tools(self) -> Path:
        return Path(self.config.tools)

    @property
    def file(self) -> str:
        return self.__file

    @property
    def config_path(self) -> Path:
        return self.__host_root / self.__file

    def locate_root(self, under: Path) -> Path:
        current = under
        while True:
            if (path := (current / self.__file)).exists() and path.is_file():
                return current
            if (nxtdir := current.parent).samefile(current):
                break
            current = nxtdir
        raise Exception(f"Could not identify work area in parents of {under}")

    @functools.cached_property
    def config(self) -> Blockwork:
        return BlockworkParser.parse(self.config_path)

    @functools.cached_property
    def cache_config_path(self) -> Path | None:
        config_path = self.__cache_config or self.config.default_cache_config
        if config_path is not None:
            config_path = Path(config_path)
        return config_path

    @functools.cached_property
    def cache_config(self) -> CachingConfig:
        config_path = self.cache_config_path
        if config_path is None:
            return CachingConfig()
        return CachingParser.parse(Path(config_path))

    @functools.cached_property
    def caches(self) -> list["Cache"]:
        "Import and initialise the caches from config"
        cache_enabled = (
            self.cache_config.enabled if self.__cache_enable is None else self.__cache_enable
        )
        if not cache_enabled:
            return []

        if self.host_root.absolute().as_posix() not in sys.path:
            sys.path.append(self.host_root.absolute().as_posix())

        caches = []
        for cache_config in self.cache_config.caches:
            module_path, class_name = cache_config.path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cache_cls = getattr(module, class_name)
            cache = cache_cls(self, cache_config)
            caches.append(cache)

        return caches

    @property
    def cache_targets(self):
        """
        True if caching is forced (even targetted objects are retrieved from
        cache)
        """
        return self.cache_config.targets if self.__cache_targets is None else self.__cache_targets

    @property
    def cache_expect(self):
        """
        True if all objects are expected to be in a cache. Will throw if this
        is not the case.
        """
        return self.cache_config.expect if self.__cache_expect is None else self.__cache_expect

    @property
    def hub_url(self):
        return os.environ.get("BW_HUB_URL", "") or self.config.hub_url

    @property
    @functools.lru_cache  # noqa: B019
    def state(self) -> State:
        return State(self.host_state)

    @property
    def timestamp(self) -> str:
        return self.__timestamp

    def map_to_container(self, h_path: Path) -> Path:
        """
        Map a path from the host into its equivalent location in the container.

        :param h_path:  Host-side path
        :returns:       Container-side path
        """
        for rel_host, rel_cont in (
            (self.host_root, self.container_root),
            (self.host_scratch, self.container_scratch),
        ):
            if h_path.is_relative_to(rel_host):
                c_path = rel_cont / h_path.relative_to(rel_host)
                break
            elif not h_path.is_absolute():
                raise ContextHostPathError(f"Path {h_path} is required to be absolute.")
        else:
            raise ContextHostPathError(
                f"Path {h_path} is not within the project "
                f"working directory {self.host_root} or "
                f"scratch area {self.host_scratch}"
            )
        return c_path

    def map_to_host(self, c_path: Path) -> Path:
        """
        Map a path from the container into its equivalent location on the host.

        :param c_path:  Container-side path
        :returns:       Host-side path
        """
        for rel_host, rel_cont in (
            (self.host_root, self.container_root),
            (self.host_scratch, self.container_scratch),
        ):
            if c_path.is_relative_to(rel_cont):
                h_path = rel_host / c_path.relative_to(rel_cont)
                break
        else:
            raise ContextContainerPathError(
                f"Path {c_path} is not within the project "
                f"working directory {self.container_root} "
                f"or scratch area {self.container_scratch}"
            )
        return h_path
