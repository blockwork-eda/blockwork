from pathlib import Path
from typing import List

from blockwork.tools import Invocation, Require, Tool, Version

from .common import TOOL_ROOT

@Tool.register()
class GCC(Tool):
    versions = [
        Version(location = TOOL_ROOT / "gcc" / "13.1.0",
                version  = "13.1.0",
                paths    = { "PATH": [Tool.ROOT / "bin"] },
                default  = True),
    ]

    @Tool.action("GCC")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            "wget --quiet https://mirrorservice.org/sites/sourceware.org/pub/gcc/releases/gcc-13.1.0/gcc-13.1.0.tar.gz",
            "tar -xf gcc-13.1.0.tar.gz",
            "cd gcc-13.1.0"
            "bash ./contrib/download_prerequisites",
            "cd ..",
            "mkdir -p objdir",
            "cd objdir",
            f"bash ../gcc-13.1.0/configure --prefix={tool_dir.as_posix()} "
            "--enable-languages=c,c++ --build=$(uname -m)-linux-gnu",
            "make -j4",
            "make install",
            "cd ..",
            "rm -rf objdir gcc-13.1.0 ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )


@Tool.register()
class M4(Tool):
    versions = [
        Version(
            location=TOOL_ROOT / "m4" / "1.4.19",
            version="1.4.19",
            requires=[Require(GCC, "13.1.0")],
            paths={"PATH": [Tool.ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.action("M4")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            "wget --quiet https://ftp.gnu.org/gnu/m4/m4-1.4.19.tar.gz",
            "tar -xf m4-1.4.19.tar.gz",
            "cd m4-1.4.19",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            "rm -rf m4-1.4.19 ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )


@Tool.register()
class Flex(Tool):
    versions = [
        Version(
            location=TOOL_ROOT / "flex" / "2.6.4",
            version="2.6.4",
            requires=[Require(GCC, "13.1.0"),
                      Require(M4, "1.4.19")],
            paths={
                "PATH": [Tool.ROOT / "bin"],
                "LD_LIBRARY_PATH": [Tool.ROOT / "lib"],
                "C_INCLUDE_PATH": [Tool.ROOT / "include"],
                "CPLUS_INCLUDE_PATH": [Tool.ROOT / "include"],
            },
            default=True,
        ),
    ]

    @Tool.action("Flex")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            "wget --quiet https://github.com/westes/flex/releases/download/v2.6.4/flex-2.6.4.tar.gz",
            "tar -xf flex-2.6.4.tar.gz",
            "cd flex-2.6.4",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            "rm -rf flex-2.6.4 ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )


@Tool.register()
class Bison(Tool):
    versions = [
        Version(
            location=TOOL_ROOT / "bison" / "3.8",
            version="3.8",
            requires=[Require(GCC, "13.1.0"),
                      Require(M4, "1.4.19")],
            paths={"PATH": [Tool.ROOT / "bin"], "LD_LIBRARY_PATH": [Tool.ROOT / "lib"]},
            default=True,
        ),
    ]

    @Tool.action("Bison")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            "wget --quiet https://ftp.gnu.org/gnu/bison/bison-3.8.tar.gz",
            "tar -xf bison-3.8.tar.gz",
            "cd bison-3.8",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            "rm -rf bison-3.8 ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )


@Tool.register()
class Autoconf(Tool):
    versions = [
        Version(
            location=TOOL_ROOT / "autoconf" / "2.71",
            version="2.71",
            requires=[Require(GCC, "13.1.0"),
                      Require(M4, "1.4.19")],
            paths={"PATH": [Tool.ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.action("Autoconf")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            "wget --quiet https://ftp.gnu.org/gnu/autoconf/autoconf-2.71.tar.gz",
            "tar -xf autoconf-2.71.tar.gz",
            "cd autoconf-2.71",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            "rm -rf autoconf-2.71 ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )


@Tool.register()
class CMake(Tool):
    versions = [
        Version(
            location=TOOL_ROOT / "cmake" / "3.27.1",
            version="3.27.1",
            requires=[Require(GCC, "13.1.0")],
            paths={"PATH": [Tool.ROOT]},
            default=True,
        ),
    ]

    @Tool.action("CMake")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            "wget --quiet https://github.com/Kitware/CMake/releases/download/v3.27.1/cmake-3.27.1.tar.gz",
            "tar -xf cmake-3.27.1.tar.gz",
            "cd cmake-3.27.1",
            "./bootstrap",
            "make -j4",
            "make install",
            "cd ..",
            "rm -rf cmake-3.27.1 ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )


@Tool.register()
class CCache(Tool):
    versions = [
        Version(
            location=TOOL_ROOT / "ccache" / "4.8.2",
            version="4.8.2",
            requires=[Require(GCC, "13.1.0"),
                      Require(Flex, "2.6.4"),
                      Require(Bison, "3.8"),
                      Require(Autoconf, "2.71"),
                      Require(CMake, "3.27.1")],
            paths={"PATH": [Tool.ROOT]},
            default=True,
        ),
    ]

    @Tool.action("CCache")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            "wget --quiet https://github.com/ccache/ccache/releases/download/v4.8.2/ccache-4.8.2.tar.gz",
            "tar -xf ccache-4.8.2.tar.gz",
            "cd ccache-4.8.2",
            "autoconf",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            "rm -rf ccache-4.8.2 ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )


@Tool.register()
class Help2Man(Tool):
    versions = [
        Version(
            location=TOOL_ROOT / "help2man" / "1.49.3",
            version="1.49.3",
            requires=[Require(GCC, "13.1.0")],
            paths={"PATH": [Tool.ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.action("Help2Man")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            "wget --quiet http://mirror.koddos.net/gnu/help2man/help2man-1.49.3.tar.xz",
            "tar -xf help2man-1.49.3.tar.gz",
            "cd help2man-1.49.3",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            "rm -rf help2man-1.49.3 ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )
