from pathlib import Path
from typing import List

from blockwork.context import HostArchitecture
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
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://mirrorservice.org/sites/sourceware.org/pub/gcc/releases/gcc-{vernum}/gcc-{vernum}.tar.gz",
            f"tar -xf gcc-{vernum}.tar.gz",
            f"cd gcc-{vernum}"
            "bash ./contrib/download_prerequisites",
            "cd ..",
            "mkdir -p objdir",
            "cd objdir",
            f"bash ../gcc-{vernum}/configure --prefix={tool_dir.as_posix()} "
            "--enable-languages=c,c++ --build=$(uname -m)-linux-gnu",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf objdir gcc-{vernum} ./*.tar.*"
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
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://ftp.gnu.org/gnu/m4/m4-{vernum}.tar.gz",
            f"tar -xf m4-{vernum}.tar.gz",
            f"cd m4-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf m4-{vernum} ./*.tar.*"
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
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://github.com/westes/flex/releases/download/v{vernum}/flex-{vernum}.tar.gz",
            f"tar -xf flex-{vernum}.tar.gz",
            f"cd flex-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf flex-{vernum} ./*.tar.*"
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
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://ftp.gnu.org/gnu/bison/bison-{vernum}.tar.gz",
            f"tar -xf bison-{vernum}.tar.gz",
            f"cd bison-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf bison-{vernum} ./*.tar.*"
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
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://ftp.gnu.org/gnu/autoconf/autoconf-{vernum}.tar.gz",
            f"tar -xf autoconf-{vernum}.tar.gz",
            f"cd autoconf-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf autoconf-{vernum} ./*.tar.*"
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
            paths={"PATH": [Tool.ROOT / "bin"]},
            default=True,
        ),
    ]

    @Tool.action("CMake")
    def install(self, version : Version, *args : List[str]) -> Invocation:
        vernum = version.version
        arch_str = ["x86_64", "aarch64"][HostArchitecture.identify() is HostArchitecture.ARM]
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://github.com/Kitware/CMake/releases/download/v{vernum}/cmake-{vernum}-linux-{arch_str}.sh",
            f"bash ./cmake-{vernum}-linux-aarch64.sh --prefix={tool_dir.as_posix()} --skip-license"
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
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
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
            f"rm -rf ccache-{vernum} ./*.tar.*"
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
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet http://mirror.koddos.net/gnu/help2man/help2man-{vernum}.tar.xz",
            f"tar -xf help2man-{vernum}.tar.xz",
            f"cd help2man-{vernum}",
            f"./configure --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf help2man-{vernum} ./*.tar.*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )
