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

from blockwork.context import Context, HostArchitecture
from blockwork.tools import Invocation, Require, Tool, Version


@Tool.register()
class Flex(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "flex" / "2.6.4",
            version="2.6.4",
            paths={
                "PATH": [Tool.CNTR_ROOT / "bin"],
                "LD_LIBRARY_PATH": [Tool.CNTR_ROOT / "lib"],
                "C_INCLUDE_PATH": [Tool.CNTR_ROOT / "include"],
                "CPLUS_INCLUDE_PATH": [Tool.CNTR_ROOT / "include"],
            },
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/westes/flex/releases/download/v{vernum}/flex-{vernum}.tar.gz",
            f"tar -xf flex-{vernum}.tar.gz",
            f"cd flex-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf flex-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class Bison(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "bison" / "3.8",
            version="3.8",
            paths={
                "PATH": [Tool.CNTR_ROOT / "bin"],
                "LD_LIBRARY_PATH": [Tool.CNTR_ROOT / "lib"],
            },
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://ftp.gnu.org/gnu/bison/bison-{vernum}.tar.gz",
            f"tar -xf bison-{vernum}.tar.gz",
            f"cd bison-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf bison-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class Autoconf(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "autoconf" / "2.71",
            version="2.71",
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://ftp.gnu.org/gnu/autoconf/autoconf-{vernum}.tar.gz",
            f"tar -xf autoconf-{vernum}.tar.gz",
            f"cd autoconf-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf autoconf-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class CMake(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "cmake" / "3.27.1",
            version="3.27.1",
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        arch_str = ["x86_64", "aarch64"][ctx.host_architecture is HostArchitecture.ARM]
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/Kitware/CMake/releases/download/v{vernum}/cmake-{vernum}-linux-{arch_str}.sh",
            f"bash ./cmake-{vernum}-linux-{arch_str}.sh"
            f" --prefix={tool_dir.as_posix()} --skip-license",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class CCache(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "ccache" / "4.8.2",
            version="4.8.2",
            requires=[
                Require(Flex, "2.6.4"),
                Require(Bison, "3.8"),
                Require(Autoconf, "2.71"),
                Require(CMake, "3.27.1"),
            ],
            paths={"PATH": [Tool.CNTR_ROOT]},
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://github.com/ccache/ccache/releases/download/v{vernum}/ccache-{vernum}.tar.gz",
            f"tar -xf ccache-{vernum}.tar.gz",
            f"cd ccache-{vernum}",
            "mkdir -p build",
            "cd build",
            f"cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX={tool_dir.as_posix()} ..",
            "make -j4",
            "make install",
            "cd ../..",
            f"rm -rf ccache-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class Help2Man(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "help2man" / "1.49.3",
            version="1.49.3",
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet http://mirror.koddos.net/gnu/help2man/help2man-{vernum}.tar.xz",
            f"tar -xf help2man-{vernum}.tar.xz",
            f"cd help2man-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf help2man-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class GPerf(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "gperf" / "3.1",
            version="3.1",
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet http://ftp.gnu.org/pub/gnu/gperf/gperf-{vernum}.tar.gz",
            f"tar -xf gperf-{vernum}.tar.gz",
            f"cd gperf-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf gperf-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class Automake(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "automake" / "1.16.5",
            version="1.16.5",
            requires=[Require(Autoconf, "2.71")],
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget --quiet https://ftp.gnu.org/gnu/automake/automake-{vernum}.tar.gz",
            f"tar -xf automake-{vernum}.tar.gz",
            f"cd automake-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf automake-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )


@Tool.register()
class PkgConfig(Tool):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "pkgconfig" / "0.29.2",
            version="0.29.2",
            requires=[Require(Autoconf, "2.71")],
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        tool_dir = Path("/tools") / self.location.relative_to(Tool.HOST_ROOT)
        script = [
            f"wget https://pkgconfig.freedesktop.org/releases/pkg-config-{vernum}.tar.gz",
            f"tar -xf pkg-config-{vernum}.tar.gz",
            f"cd pkg-config-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()} --with-internal-glib",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf pkg-config-{vernum} ./*.tar.*",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
            interactive=True,
        )
