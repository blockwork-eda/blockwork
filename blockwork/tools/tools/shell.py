from blockwork.context import Context

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
    def script(self, ctx: Context, *script: str) -> Invocation:
        return Invocation(tool=self, execute="bash", args=["-c", " && ".join(script)])

    @Tool.action()
    def cp(self, ctx: Context, frm: str, to: str) -> Invocation:
        return Invocation(tool=self, execute="cp", args=["-r", frm, to])
