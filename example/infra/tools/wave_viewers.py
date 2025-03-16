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

from .compilers import Automake, GPerf


@Tool.register()
class GTKWave(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "gtkwave" / "3.3.116",
            version="3.3.116",
            requires=[
                Require(Automake, "1.16.5"),
                Require(GPerf, "3.1"),
            ],
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.action(default=True)
    def view(self, ctx: Context, wavefile: str, *args: list[str]) -> Invocation:
        path = Path(wavefile).absolute()
        return Invocation(
            tool=self,
            execute="gtkwave",
            args=[path, *args],
            display=True,
            binds=[path.parent],
        )

    @Tool.action()
    def gtk_version(self, ctx: Context, *args: list[str]) -> Invocation:
        return Invocation(
            tool=self,
            execute="gtkwave",
            args=["--version", *args],
            display=True,
        )

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/gtkwave/gtkwave/archive/refs/tags/v{vernum}.tar.gz",
            f"tar -xf v{vernum}.tar.gz",
            f"cd gtkwave-{vernum}/gtkwave3-gtk3",
            f"./configure --prefix={tool_dir.as_posix()} --enable-gtk3",
            "make -j4",
            "make install",
            "cd ../..",
            f"rm -rf gtkwave-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
            interactive=True,
        )
