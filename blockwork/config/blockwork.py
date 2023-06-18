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

from typing import List, Optional

from .common import ConfigBase, ConfigError


class Blockwork(ConfigBase):
    yaml_tag = "!Blockwork"

    def __init__(self,
                 project      : Optional[str]       = None,
                 root         : Optional[str]       = "/project",
                 scratch      : Optional[str]       = "/scratch",
                 host_scratch : Optional[str]       = "../{project}.scratch",
                 host_state   : Optional[str]       = "../{project}.state",
                 bootstrap    : Optional[List[str]] = None,
                 tooldefs     : Optional[List[str]] = None) -> None:
        self.project      = project
        self.root         = root
        self.scratch      = scratch
        self.host_scratch = host_scratch
        self.host_state   = host_state
        self.bootstrap    = bootstrap or []
        self.tooldefs     = tooldefs or []

    def check(self) -> None:
        if not self.project or not isinstance(self.project, str):
            raise ConfigError(self, "project", "Project name has not been specified")
        if not isinstance(self.root, str) or not self.root or not self.root.startswith("/"):
            raise ConfigError(self, "root", "Root must be an absolute path")
        if not isinstance(self.scratch, str) or not self.scratch or not self.scratch.startswith("/"):
            raise ConfigError(self, "scratch", "Scratch must be an absolute path")
        if not isinstance(self.host_scratch, str) or not self.host_scratch:
            raise ConfigError(self, "host_scratch", "Host scratch directory must be a relative or absolute path")
        if not isinstance(self.host_state, str) or not self.host_state:
            raise ConfigError(self, "host_state", "Host state directory must be a relative or absolute path")
        for key, name in (("bootstrap", "Bootstrap"), ("tooldefs", "Tool")):
            obj = getattr(self, key)
            if not isinstance(obj, list):
                raise ConfigError(self, key, f"{name} definitions must be a list")
            if not all(isinstance(x, str) for x in obj):
                raise ConfigError(self, key, f"{name} definitions must be a list of strings")
