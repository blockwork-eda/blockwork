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
from typing import ClassVar

from blockwork.context import Context
from blockwork.tools import Invocation, Require, Tool, Version

from .compilers import Autoconf, Bison, CCache, Flex, GPerf, Help2Man


@Tool.register()
class IVerilog(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "iverilog" / "12.0",
            version="12.0",
            requires=[
                Require(Autoconf, "2.71"),
                Require(Bison, "3.8"),
                Require(Flex, "2.6.4"),
                Require(GPerf, "3.1"),
            ],
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum.replace(".", "_")
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/steveicarus/iverilog/archive/refs/tags/v{vernum}.tar.gz",
            f"tar -xf v{vernum}.tar.gz",
            f"cd iverilog-{vernum}",
            "autoconf",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf iverilog-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class Verilator(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "verilator" / "5.014",
            version="5.014",
            env={
                "VERILATOR_BIN": "../../bin/verilator_bin",
                "VERILATOR_ROOT": Tool.CNTR_ROOT / "share" / "verilator",
            },
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            requires=[
                Require(Autoconf, "2.71"),
                Require(Bison, "3.8"),
                Require(CCache, "4.8.2"),
                Require(Flex, "2.6.4"),
                Require(Help2Man, "1.49.3"),
            ],
            default=True,
        ),
    ]

    @Tool.action()
    def run(self, ctx: Context, *args: str) -> Invocation:
        return Invocation(tool=self, execute="verilator", args=args)

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/verilator/verilator/archive/refs/tags/v{vernum}.tar.gz",
            f"tar -xf v{vernum}.tar.gz",
            f"cd verilator-{vernum}",
            "autoconf",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            f"rm -rf verilator-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )
