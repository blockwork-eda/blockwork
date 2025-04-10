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
from blockwork.context import Context
from ..tool import Invocation, Tool, Version


@Tool.register()
class Bash(Tool):
    versions = (
        Version(
            location=Tool.HOST_ROOT / "bash" / "1.0",
            version="1.0",
            default=True,
        ),
    )

    @Tool.action(default=True)
    def script(self, ctx: Context, *script: str) -> Invocation:
        return Invocation(tool=self, execute="bash", args=["-c", " && ".join(script)])

    @Tool.action()
    def cp(self, ctx: Context, frm: str | Path, to: str | Path) -> Invocation:
        return Invocation(tool=self, execute="cp", args=["-r", frm, to])
