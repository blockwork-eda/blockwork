from pathlib import Path
from typing import List

from blockwork.tools import Invocation, Tool, Version

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
            "rm -rf objdir gcc-13.1.0"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )
