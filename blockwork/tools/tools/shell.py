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

    @Tool.action("Bash", default=True)
    def script(self, ctx, version, *script: str) -> Invocation:
        return Invocation(version=version, execute="bash", args=["-c", " && ".join(script)])

    @Tool.action("Bash")
    def cp(self, ctx, version, frm: str, to: str) -> Invocation:
        return Invocation(version=version, execute="cp", args=["-r", frm, to])
