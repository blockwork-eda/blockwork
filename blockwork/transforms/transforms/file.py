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

from pathlib import Path

from ...context import Context
from ...tools.shells.bash import Bash
from ..transform import Transform


class Copy(Transform):
    frm: Path = Transform.IN()
    to: Path = Transform.OUT(init=True, default=...)
    bash: Bash = Transform.TOOL()

    def execute(self, ctx: Context):
        yield self.bash.cp(ctx, frm=self.frm, to=self.to)
