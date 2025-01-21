import stat
from collections.abc import Generator
from pathlib import Path
from textwrap import dedent

import pytest

from blockwork.config.api import ConfigApi
from blockwork.context import Context
from blockwork.tools import Invocation, tools
from blockwork.transforms import EnvPolicy, Transform
from blockwork.transforms.transform import Result


def create_with_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class Util(Transform):
    name: str = Transform.IN(default="util", init=False)
    version: str = Transform.IN(default="0.1.0")

    # root: Path = Transform.OUT(
    #     derive=((name, version), lambda n, v: Tool.CNTR_ROOT / n / v), init=False)

    root: Path = Transform.OUT(default=..., init=False)
    bin: Path = Transform.OUT(
        derive=(root, lambda r: r / "bin"), init=False, env="PATH", env_policy=EnvPolicy.APPEND
    )

    def execute(self, ctx: Context):
        root = ctx.map_to_host(self.root)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        script = bin_dir / "concat"
        script.write_text(
            dedent(
                """
            #!/bin/bash

            output="$1";
            shift;
            for var in "$@"
            do
                cat "$var" >> "$output";
            done
            """
            ).lstrip()
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        yield from []

    def concat(self, ipaths: list[Path], opath: Path):
        yield Invocation(
            tools.Bash(), "concat", args=[opath.as_posix(), *(p.as_posix() for p in ipaths)]
        )


class UseUtil(Transform):
    util: Util = Transform.IN(default=...)
    ipaths: list[Path] = Transform.IN()
    opath: Path = Transform.OUT()

    def execute(self, ctx: Context) -> Generator[Invocation, Result, None]:
        yield from self.util.concat(self.ipaths, self.opath)


# class ToolIFace(IFace):
#     name: str = IFace.FIELD(default="util", init=False)
#     version: str = IFace.FIELD(default="0.1.0")
#     root: Path = IFace.FIELD(
#         derive=((name, version), lambda n, v: Tool.CNTR_ROOT / n / v), init=False)
#     bin: Path = IFace.FIELD(
#         derive=(root, lambda r: r / "bin"), init=False, env="PATH", env_policy=EnvPolicy.APPEND
#     )

#     # Use this as the execute method of an automatically created transform which gets
#     # added when this is used as a dependency
#     def create(self, ctx: Context):
#         root = ctx.map_to_host(self.root)
#         bin_dir = root / "bin"
#         bin_dir.mkdir()
#         script = bin_dir / "concat"
#         script.write_text(
#             dedent(
#                 """
#             #!/bin/bash

#             output="$1";
#             shift;
#             for var in "$@"
#             do
#                 cat "$var" >> "$output";
#             done
#             """
#             ).lstrip()
#         )
#         script.chmod(script.stat().st_mode | stat.S_IEXEC)
#         yield from []


#     def concat(self, ipaths: list[Path], opath: Path):
#         yield Invocation(
#             tools.Bash(), "concat", args=[opath.as_posix(), *(p.as_posix() for p in ipaths)]
#         )


# class UtilIFace(IFace):
#     root: Path = IFace.FIELD()
#     bin: Path = IFace.FIELD(
#         derive=(root, lambda r: r / "bin"), init=False, env="PATH", env_policy=EnvPolicy.APPEND
#     )
#     bash: tools.Bash = IFace.TOOL()

#     def concat(self, ipaths: list[Path], opath: Path):
#         yield Invocation(
#             self.bash, "concat", args=[opath.as_posix(), *(p.as_posix() for p in ipaths)]
#         )


# class MakeUtil(Transform):
#     util: UtilIFace = Transform.OUT()

#     def execute(self, ctx: Context) -> Generator[Invocation, Result, None]:
#         root = ctx.map_to_host(self.util.root)
#         bin_dir = root / "bin"
#         bin_dir.mkdir()
#         script = bin_dir / "concat"
#         script.write_text(
#             dedent(
#                 """
#             #!/bin/bash

#             output="$1";
#             shift;
#             for var in "$@"
#             do
#                 cat "$var" >> "$output";
#             done
#             """
#             ).lstrip()
#         )
#         script.chmod(script.stat().st_mode | stat.S_IEXEC)
#         yield from []


# class UseUtil(Transform):
#     util: UtilIFace = Transform.IN(default=...)
#     ipaths: list[Path] = Transform.IN()
#     opath: Path = Transform.OUT()

#     def execute(self, ctx: Context) -> Generator[Invocation, Result, None]:
#         yield from self.util.concat(self.ipaths, self.opath)


@pytest.mark.usefixtures("api")
class TestInterfaces:
    def test_io_same_dir(self, api: ConfigApi):
        """
        Test that we get a bind error if a directory is used for both input and output.

        This may be something we want to (carefully) change later.
        """
        # t = MakeUtil()

        p0 = create_with_text(api.ctx.host_scratch / "_/p0", "hello")
        p1 = create_with_text(api.ctx.host_scratch / "_/p1", " world")

        # t.run(api.ctx)

        t = UseUtil(ipaths=[p0, p1])

        # _s = InterfaceSerializer.serialize(t)

        # Create the input
        t.run(api.ctx)

        output = t.opath.read_text()

        assert output == "hello world"
