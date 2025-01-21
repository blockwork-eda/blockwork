from collections.abc import Sequence
from pathlib import Path

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
    def script(self, *script: str) -> Invocation:
        return Invocation(tool=self, execute="bash", args=["-c", " && ".join(script)])

    @Tool.action()
    def cp(self, frm: str, to: str) -> Invocation:
        return Invocation(tool=self, execute="cp", args=["-r", frm, to])

    @Tool.action()
    def cmd(self, command: str, args: Sequence[str | Path]) -> Invocation:
        return Invocation(tool=self, execute=command, args=args)
