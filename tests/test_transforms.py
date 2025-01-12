import os
import stat
import tarfile
from collections.abc import Generator
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from blockwork.config.api import ConfigApi
from blockwork.containers import ContainerBindError
from blockwork.context import Context
from blockwork.tools import Invocation, tools
from blockwork.transforms import EnvPolicy, IEnv, IFace, Transform, transforms
from blockwork.transforms.transform import Result


def create_with_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class ComplexOutIface(IFace):
    base: Path = IFace.FIELD()
    paths: dict[str, Path] = IFace.FIELD(derive=(base, lambda b: {"p0": b / "p0", "p1": b / "p1"}))


class ScriptUtil(Transform):
    """
    Generic factory for creating a script and adding it to the path
    """

    bash: tools.Bash = Transform.TOOL()
    script: str = Transform.IN()
    name: str = Transform.IN()
    bin: Path = Transform.OUT(default=..., init=False, env="PATH", env_policy=EnvPolicy.APPEND)

    def execute(self, ctx: Context) -> Generator[Invocation, Result, None]:
        bin_dir = ctx.map_to_host(self.bin)
        bin_dir.mkdir(exist_ok=True)
        script = bin_dir / self.name
        script.write_text(self.script)
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        yield from []

    def call(self, *args: str | Path):
        yield self.bash.cmd(self.name, args)


class TFTar(Transform):
    bash: tools.Bash = Transform.TOOL()

    ipaths: list[Path] = Transform.IN()
    opath: Path = Transform.OUT()

    def execute(self, ctx: Context):
        yield self.bash.cmd("tar", ["-cf", self.opath, *self.ipaths])


@pytest.mark.usefixtures("api")
class TestTransforms:
    class IOSameDirTransform(Transform):
        i: Path = Transform.IN()
        o: Path = Transform.OUT(init=True)

    def test_io_same_dir(self, api: ConfigApi):
        """
        Test that we get a bind error if a directory is used for both input and output.

        This may be something we want to (carefully) change later.
        """
        t = self.IOSameDirTransform(
            i=api.ctx.host_scratch / "_/i",
            o=api.ctx.host_scratch / "_/o",
        )
        # Create the input
        t.i.parent.mkdir(parents=True, exist_ok=True)
        t.i.touch()

        with pytest.raises(ContainerBindError):
            t.run(api.ctx)

    def test_cp(self, api: ConfigApi):
        """
        Test that we get a bind error if a directory is used for both input and output.

        This may be something we want to (carefully) change later.
        """
        text = "cp"
        frm = create_with_text(api.ctx.host_scratch / "_/i", text)

        tf = transforms.Copy(frm=frm)
        tf.run(api.ctx)

        to = tf.to
        assert to.read_text() == text

    class TFInputNest(Transform):
        bash: tools.Bash = Transform.TOOL()
        nestedfrm: Any = Transform.IN()
        to: Path = Transform.OUT()

        def execute(self, ctx):
            arbitrary = 1
            frm = self.nestedfrm["some"][arbitrary]["complex"]["value"]
            yield self.bash.script(f"cat {frm} > {self.to}")

    def test_input_nest(self, api: ConfigApi):
        text = "input_nest"
        frm = create_with_text(api.ctx.host_scratch / "_/i", text)

        tf = self.TFInputNest(nestedfrm={"some": ["arbitrary", {"complex": {"value": Path(frm)}}]})
        tf.run(api.ctx)
        tf = transforms.Copy(frm=tf.to)
        tf.run(api.ctx)

        assert tf.to.read_text() == text

    class TFSimpleFieldEnv(Transform):
        bash: tools.Bash = Transform.TOOL()
        frm: str = Transform.IN(env="TEST")
        to1: Path = Transform.OUT()
        to2: Path = Transform.OUT()

        def execute(self, ctx):
            yield self.bash.script(f"echo -n $TEST > {self.to1}")
            yield self.bash.script(f"echo -n {self.frm} > {self.to2}")

    def test_simple_field_env(self, api: ConfigApi):
        text = "input_nest"

        with pytest.raises(ValueError):
            tf = self.TFSimpleFieldEnv(frm={"x": "y"})

        tf = self.TFSimpleFieldEnv(frm=text)
        tf.run(api.ctx)

        assert tf.to1.read_text() == text
        assert tf.to2.read_text() == text

    class TFComplexFieldEnvAppend(Transform):
        bash: tools.Bash = Transform.TOOL()
        frm: str = Transform.IN(env="TEST")
        frm2: str = Transform.IN(env="TEST", env_policy=EnvPolicy.APPEND)
        to: Path = Transform.OUT()

        def execute(self, ctx):
            yield self.bash.script(f"echo -n $TEST > {self.to}")

    class TFComplexFieldEnvPrepend(Transform):
        bash: tools.Bash = Transform.TOOL()
        frm: str = Transform.IN(env="TEST")
        frm2: list[str] = Transform.IN(env="TEST", env_policy=EnvPolicy.PREPEND)
        to: Path = Transform.OUT()

        def execute(self, ctx):
            yield self.bash.script(f"echo -n $TEST > {self.to}")

    class TFComplexFieldEnvReplace(Transform):
        bash: tools.Bash = Transform.TOOL()
        frm: str = Transform.IN(env="TEST")
        frm2: list[str] = Transform.IN(env="TEST", env_policy=EnvPolicy.REPLACE)
        to: Path = Transform.OUT()

        def execute(self, ctx):
            yield self.bash.script(f"echo -n $TEST > {self.to}")

    class TFComplexFieldEnvConflict(Transform):
        bash: tools.Bash = Transform.TOOL()
        frm: str = Transform.IN(env="TEST")
        frm2: str = Transform.IN(env="TEST", env_policy=EnvPolicy.CONFLICT)
        to: Path = Transform.OUT()

        def execute(self, ctx):
            yield self.bash.script(f"echo -n $TEST > {self.to}")

    def test_complex_field_env(self, api: ConfigApi):
        text = ["hello", "world"]
        tf = self.TFComplexFieldEnvAppend(frm=text[0], frm2=text[1])
        tf.run(api.ctx)
        assert tf.to.read_text() == os.pathsep.join(text)

        text = ["good", "morning", "world"]
        tf = self.TFComplexFieldEnvPrepend(frm=text[0], frm2=text[1:])
        tf.run(api.ctx)
        assert tf.to.read_text() == os.pathsep.join(reversed(text))

        text = ["good", "morning", "world"]
        tf = self.TFComplexFieldEnvReplace(frm=text[0], frm2=text[1:])
        tf.run(api.ctx)
        assert tf.to.read_text() == "world"

        text = ["hello", "world"]
        with pytest.raises(ValueError):
            tf = self.TFComplexFieldEnvConflict(frm=text[0], frm2=text[1])
            tf.run(api.ctx)

        tf = self.TFComplexFieldEnvConflict(frm=text[0], frm2=text[0])
        tf.run(api.ctx)
        assert tf.to.read_text() == "hello"

    class TFComplexArgEnvShallow(Transform):
        bash: tools.Bash = Transform.TOOL()
        frm: IEnv = Transform.IN()
        to1: Path = Transform.OUT()
        to2: Path = Transform.OUT()
        to3: Path = Transform.OUT()

        def execute(self, ctx):
            yield self.bash.script(f"echo -n $TEST > {self.to1}")
            yield self.bash.script(f"echo -n ${self.frm.key} > {self.to2}")
            yield self.bash.script(f"echo -n {self.frm.val} > {self.to3}")

    class TFComplexArgEnvDeep(Transform):
        bash: tools.Bash = Transform.TOOL()
        frm: Any = Transform.IN()
        to: Path = Transform.OUT()

        def execute(self, ctx):
            yield self.bash.script(f"echo -n $TEST > {self.to}")

    def test_complex_arg_env(self, api: ConfigApi):
        text = "hello world"

        tf = self.TFComplexArgEnvShallow(frm=IEnv("TEST", text))
        tf.run(api.ctx)
        assert tf.to1.read_text() == text
        assert tf.to2.read_text() == text
        assert tf.to3.read_text() == text

        tf = self.TFComplexArgEnvDeep(frm={"some": ["deeply", {"nested": IEnv("TEST", text)}]})
        tf.run(api.ctx)
        assert tf.to.read_text() == text

    class TFComplexOut(Transform):
        bash: tools.Bash = Transform.TOOL()
        frm: str = Transform.IN()
        to: ComplexOutIface = Transform.OUT()

        def execute(self, ctx):
            yield self.bash.script(f"echo -n {self.frm} > {self.to.paths['p0']}")

    def test_complex_out(self, api: ConfigApi):
        text = "hello world"

        tf = self.TFComplexOut(frm=text)
        tf.run(api.ctx)
        assert (tf.to.base / "p0").read_text() == text

    class TFDefaultBadExit(Transform):
        bash: tools.Bash = Transform.TOOL()

        def execute(self, ctx):
            yield self.bash.script("exit 1")

    class TFDefaultGoodExit(Transform):
        bash: tools.Bash = Transform.TOOL()

        def execute(self, ctx):
            yield self.bash.script("exit 0")

    class TFAcceptBadExit(Transform):
        bash: tools.Bash = Transform.TOOL()

        def execute(self, ctx):
            result = yield self.bash.script("exit 1")
            if result.exit_code == 1:
                result.accept()

    class TFRejectBadExit(Transform):
        bash: tools.Bash = Transform.TOOL()

        def execute(self, ctx):
            result = yield self.bash.script("exit 1")
            if result.exit_code == 1:
                result.reject()

    class TFAcceptExitAndContinue(Transform):
        bash: tools.Bash = Transform.TOOL()

        def execute(self, ctx):
            r1 = yield self.bash.script("exit 1")
            if r1.exit_code == 1 and r1.accept():
                yield self.bash.script("exit 0")

    class TFRetryAndContinue(Transform):
        bash: tools.Bash = Transform.TOOL()
        retries: int = Transform.IN()

        def execute(self, ctx):
            retries_left = self.retries
            while retries_left > 0:
                result = yield self.bash.script("exit 1")
                result.accept()
                if result.exit_code == 0:
                    break
                retries_left -= 1
                if retries_left == 0:
                    result.reject(f"Retried {self.retries - retries_left} times")

    def test_exits(self, api: ConfigApi):
        "Test various exit modes"
        tf = self.TFDefaultBadExit()
        with pytest.raises(RuntimeError):
            tf.run(api.ctx)

        tf = self.TFDefaultGoodExit()
        tf.run(api.ctx)

        tf = self.TFAcceptBadExit()
        tf.run(api.ctx)

        with pytest.raises(RuntimeError):
            tf = self.TFRejectBadExit()
            tf.run(api.ctx)

        with pytest.raises(RuntimeError, match="Retried 5 times"):
            tf = self.TFRetryAndContinue(retries=5)
            tf.run(api.ctx)

    class TFConcat(Transform):
        @staticmethod
        def mkconcat():
            return ScriptUtil(
                script=dedent(
                    """
            #!/bin/bash
            output="$1";
            shift;
            for var in "$@"
            do
                cat "$var" >> "$output";
            done
            """
                ).lstrip(),
                name="concat",
            )

        concat: ScriptUtil = Transform.IN(default_factory=mkconcat)

        ipaths: list[Path] = Transform.IN()
        opath: Path = Transform.OUT()

        def execute(self, ctx: Context):
            yield from self.concat.call(self.opath, *self.ipaths)

    def test_nested_input_transform_default(self, api: ConfigApi):
        "Use a transform with another transform as an input (default value)"
        p0 = create_with_text(api.ctx.host_scratch / "_/p0", "hello")
        p1 = create_with_text(api.ctx.host_scratch / "_/p1", " world")

        t = self.TFConcat(ipaths=[p0, p1])

        t.run(api.ctx)

        output = t.opath.read_text()

        assert output == "hello world"

    def test_nested_input_transform_override(self, api: ConfigApi):
        "Use a transform with another transform as an input (non-default value)"

        p0 = create_with_text(api.ctx.host_scratch / "_/p0", "hello")
        p1 = create_with_text(api.ctx.host_scratch / "_/p1", "world")

        # Create a modified util (concat with newlines) and use it instead
        concat = ScriptUtil(
            script=dedent(
                """
        #!/bin/bash
        output="$1";
        shift;
        for var in "$@"
        do
            cat "$var" >> "$output";
            echo "" >>  "$output";
        done
        """
            ).lstrip(),
            name="concat_w_newline",
        )

        t = self.TFConcat(concat=concat, ipaths=[p0, p1])

        t.run(api.ctx)

        output = t.opath.read_text()

        assert output == "hello\nworld\n"

    class TFCollect(Transform):
        bash: tools.Bash = Transform.TOOL()
        ipaths: list[Path] = Transform.IN()
        opath: Path = Transform.OUT()
        archive: TFTar = Transform.OUT(derive=(opath, lambda o: TFTar(ipaths=[o])))

        def execute(self, ctx: Context):
            yield self.bash.cmd("mkdir", [self.opath.as_posix()])
            for f in self.ipaths:
                yield self.bash.cp(f.as_posix(), self.opath.as_posix() + "/")

    def test_nested_output_transform(self, api: ConfigApi):
        "Use a transform with another transform as an output"

        p0 = create_with_text(api.ctx.host_scratch / "_/p0", "hello")
        p1 = create_with_text(api.ctx.host_scratch / "_/p1", "world")

        t = self.TFCollect(ipaths=[p0, p1])

        t.run(api.ctx)

        tar = tarfile.TarFile(t.archive.opath)
        names = tar.getnames()
        assert any("opath" in name for name in names)
        assert any("p0" in name for name in names)
        assert any("p1" in name for name in names)
