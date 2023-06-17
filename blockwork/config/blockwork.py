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
                 project   : Optional[str]       = None,
                 root      : Optional[str]       = "/bw/project",
                 state_dir : Optional[str]       = ".bw_state",
                 bootstrap : Optional[List[str]] = None,
                 tooldefs  : Optional[List[str]] = None) -> None:
        self.project   = project
        self.root      = root
        self.state_dir = state_dir
        self.bootstrap = bootstrap or []
        self.tooldefs  = tooldefs or []

    def check(self) -> None:
        if not self.project or not isinstance(self.project, str):
            raise ConfigError(self, "project", "Project name has not been specified")
        if not isinstance(self.root, str) or not self.root:
            raise ConfigError(self, "root", "Root must be a string")
        if not isinstance(self.state_dir, str) or not self.state_dir:
            raise ConfigError(self, "state_dir", "State directory must be string")
        for key, name in (("bootstrap", "Bootstrap"), ("tooldefs", "Tool")):
            obj = getattr(self, key)
            if not isinstance(obj, list):
                raise ConfigError(self, "tooldefs", f"{name} definitions must be a list")
            if not all(isinstance(x, str) for x in obj):
                raise ConfigError(self, "tooldefs", f"{name} definitions must be a list of strings")
