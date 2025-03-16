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

from infra.tools.misc import Make
from infra.tools.pythonsite import PythonSite
from infra.tools.simulators import Verilator

from blockwork.tools import Invocation
from blockwork.transforms import Transform

from ..interfaces.interfaces import DesignInterface, PythonInterface
from ..tools.python import Python


class TbCompileVerilatorTransform(Transform):
    verilator: Verilator = Transform.TOOL()
    pythonsite: PythonSite = Transform.TOOL()
    make: Make = Transform.TOOL()

    design: DesignInterface = Transform.IN()

    vtop: str = Transform.IN()
    exe: Path = Transform.OUT(init=True, default=...)

    def execute(self, ctx):
        source_args = []

        for header in self.design["headers"]:
            source_args.append(f"+incdir+{header.parent}")
        for source in self.design["sources"]:
            source_args.append(str(source))

        # Determine outdir
        out_dirx = self.exe.parent / (self.exe.name + ".scratch")

        # Build up Verilator arguments
        # NOTE: See https://docs.cocotb.org/en/stable/custom_flows.html#verilator
        py_site = self.pythonsite.get_container_path(ctx)
        pkg_root = py_site / "lib" / "python3.11" / "site-packages"
        cctb_libs = pkg_root / "cocotb" / "libs"
        cctb_share = pkg_root / "cocotb" / "share"
        arguments = [
            "-Wall",
            "-cc",
            "--exe",
            "-DCOCOTB_SIM=1",
            "--vpi",
            "--public-flat-rw",
            "--prefix",
            "Vtop",
            "-LDFLAGS",
            f"-Wl,-rpath,{cctb_libs} -L{cctb_libs} -lcocotbvpi_verilator",
            "--build",
            "-j",
            "4",
            "--top-module",
            self.vtop,
            "--no-timing",
        ]
        # Add include directories and source files
        arguments += source_args
        # Add Verilator support
        arguments.append(f"{cctb_share}/lib/verilator/verilator.cpp")
        # Invoke Verilator
        yield self.verilator.run(ctx, *arguments).where(workdir=out_dirx)

        src_vtop = (out_dirx / "obj_dir" / "Vtop").as_posix()
        dst_vtop = self.exe.as_posix()

        yield Invocation(
            tool=self.pythonsite,
            execute="mv",
            args=["-f", src_vtop, dst_vtop],
            interactive=False,
        )


class SimTransform(Transform):
    verilator: Verilator = Transform.TOOL()
    pythontool: Python = Transform.TOOL()
    pythonsite: PythonSite = Transform.TOOL()
    make: Make = Transform.TOOL()

    python: PythonInterface = Transform.IN()
    pytop: str = Transform.IN(env="MODULE")
    vtop: str = Transform.IN(env="TOPLEVEL")
    vlang: str = Transform.IN(env="TOPLEVEL_LANG", default="verilog")
    exe: Path = Transform.IN()
    testcase: str = Transform.IN(env="TESTCASE")
    seed: int = Transform.IN(env="RANDOM_SEED")
    binary: Path | None = Transform.IN(env="TESTCONFIG", default=None)
    result: Path = Transform.OUT()

    def execute(self, ctx):
        ctx.map_to_host(self.result).mkdir(parents=True, exist_ok=True)

        py_root = self.pythontool.get_container_path(ctx)

        env = {
            "LIBPYTHON_LOC": (py_root / "lib" / "libpython3.11.so").as_posix(),
        }

        yield Invocation(
            interactive=True,
            tool=self.pythonsite,
            workdir=self.result,
            execute=self.exe,
            env=env,
        )
