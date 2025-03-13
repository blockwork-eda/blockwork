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

# Expose activities
from .bootstrap import bootstrap
from .cache import cache
from .exec import exec
from .info import info
from .shell import shell
from .tools import tool, tools
from .workflow import wf, wf_step

# List all activities
activities = (bootstrap, cache, info, exec, shell, tool, tools, wf, wf_step)

# Lint guard
assert activities
