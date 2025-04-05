from pathlib import Path

from blockwork.context import Context, HostArchitecture
from blockwork.tools import Invocation, Tool, Version


@Tool.register()
class CMake(Tool):
    versions = (
        Version(
            location=Tool.HOST_ROOT / "cmake" / "3.27.1",
            version="3.27.1",
            paths={"PATH": [Tool.CNTR_ROOT / "bin"]},
            default=True,
        ),
    )

    @Tool.installer()
    def install(self, ctx: Context, *args: list[str]) -> Invocation:
        vernum = self.vernum
        arch_str = ["x86_64", "aarch64"][ctx.host_architecture is HostArchitecture.ARM]
        tool_dir = self.get_container_path(ctx)
        script = [
            f"wget --quiet https://github.com/Kitware/CMake/releases/download/"
            f"v{vernum}/cmake-{vernum}-linux-{arch_str}.sh",
            f"bash ./cmake-{vernum}-linux-{arch_str}.sh --prefix={tool_dir.as_posix()} "
            f"--skip-license",
        ]
        return Invocation(
            tool=self,
            execute="bash",
            args=["-c", " && ".join(script)],
            workdir=tool_dir,
        )

    @Tool.action(default=True)
    def run(self, ctx: Context, *args: str | Path) -> Invocation:
        return Invocation(tool=self, execute="cmake", args=args)
