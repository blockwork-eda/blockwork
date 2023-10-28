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

from ..common.checkeddataclasses import dataclass, field

@dataclass
class Blockwork:
    project      : str
    site         : str       = "./site.yaml"
    root         : str       = field(default="/project")
    scratch      : str       = field(default="/scratch")
    tools        : str       = field(default="/tools")
    host_scratch : str       = "../{project}.scratch"
    host_state   : str       = "../{project}.state"
    host_tools   : str       = "../{project}.tools"
    config       : list[str] = field(default_factory=list)
    bootstrap    : list[str] = field(default_factory=list)
    tooldefs     : list[str] = field(default_factory=list)
    transforms   : list[str] = field(default_factory=list)
    workflows    : list[str] = field(default_factory=list)
    caches       : list[str] = field(default_factory=list)
    'Caches in order of fetch preference (fastest should be first)'

    @root.check
    @scratch.check
    def abs_path(_field, value):
        if not value.startswith("/"):
            raise TypeError(f"Expected absolute path, but got {value}")
