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

from typing import ClassVar

from blockwork.context import Context
from blockwork.tools import Invocation, Require, Tool, Version

from .python import Python


@Tool.register()
class PythonSite(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "pythonsite" / "3.11.4",
            version="3.11.4",
            env={"PYTHONUSERBASE": Tool.CNTR_ROOT},
            paths={
                "PATH": [Tool.CNTR_ROOT / "bin"],
                "PYTHONPATH": [Tool.CNTR_ROOT / "lib" / "python3.11" / "site-packages"],
            },
            requires=[Require(Python, "3.11.4")],
            default=True,
        ),
    ]

    @Tool.action()
    def run(self, ctx: Context, *args: list[str]) -> Invocation:
        return Invocation(tool=self, execute="python3", args=args, interactive=True)

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        requirements = ctx.host_root / "infra" / "tools" / "pythonsite.txt"

        return Invocation(
            tool=self,
            execute="python3",
            args=[
                "-m",
                "pip",
                "--no-cache-dir",
                "install",
                "--user",
                "-v",
                "-r",
                ctx.map_to_container(requirements),
            ],
            ro_binds=[requirements],
            interactive=True,
        )
