import os
from pathlib import Path
from typing import Any

import pytest

from blockwork.config.api import ConfigApi
from blockwork.containers import ContainerBindError
from blockwork.tools import tools
from blockwork.transforms import EnvPolicy, IEnv, IFace, Transform, transforms


def create_with_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class ComplexOutIface(IFace):
    base: Path

    def resolve(self):
        return {"p0": self.base / "p0", "p1": self.base / "p1"}

    @classmethod
    def from_field(cls, transform, field, name):
        return cls(base=transform.api.path(name))


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
        t.i.parent.mkdir(parents=True)
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
        nestedfrm: Any = Transform.IN()
        to: Path = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            arbitrary = 1
            frm = self.nestedfrm["some"][arbitrary]["complex"]["value"]
            yield tools.bash.get_action("script")(ctx, f"cat {frm} > {self.to}")

    def test_input_nest(self, api: ConfigApi):
        text = "input_nest"
        frm = create_with_text(api.ctx.host_scratch / "_/i", text)

        tf = self.TFInputNest(nestedfrm={"some": ["arbitrary", {"complex": {"value": Path(frm)}}]})
        tf.run(api.ctx)
        tf = transforms.Copy(frm=tf.to)
        tf.run(api.ctx)

        assert tf.to.read_text() == text

    class TFSimpleFieldEnv(Transform):
        frm: str = Transform.IN(env="TEST")
        to1: Path = Transform.OUT()
        to2: Path = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, f"echo -n $TEST > {self.to1}")
            yield tools.bash.get_action("script")(ctx, f"echo -n {self.frm} > {self.to2}")

    def test_simple_field_env(self, api: ConfigApi):
        text = "input_nest"

        with pytest.raises(ValueError):
            tf = self.TFSimpleFieldEnv(frm={"x": "y"})

        tf = self.TFSimpleFieldEnv(frm=text)
        tf.run(api.ctx)

        assert tf.to1.read_text() == text
        assert tf.to2.read_text() == text

    class TFComplexFieldEnvAppend(Transform):
        frm: str = Transform.IN(env="TEST")
        frm2: str = Transform.IN(env="TEST", env_policy=EnvPolicy.APPEND)
        to: Path = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, f"echo -n $TEST > {self.to}")

    class TFComplexFieldEnvPrepend(Transform):
        frm: str = Transform.IN(env="TEST")
        frm2: list[str] = Transform.IN(env="TEST", env_policy=EnvPolicy.PREPEND)
        to: Path = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, f"echo -n $TEST > {self.to}")

    class TFComplexFieldEnvReplace(Transform):
        frm: str = Transform.IN(env="TEST")
        frm2: list[str] = Transform.IN(env="TEST", env_policy=EnvPolicy.REPLACE)
        to: Path = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, f"echo -n $TEST > {self.to}")

    class TFComplexFieldEnvConflict(Transform):
        frm: str = Transform.IN(env="TEST")
        frm2: str = Transform.IN(env="TEST", env_policy=EnvPolicy.CONFLICT)
        to: Path = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, f"echo -n $TEST > {self.to}")

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
        frm: IEnv = Transform.IN()
        to1: Path = Transform.OUT()
        to2: Path = Transform.OUT()
        to3: Path = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, f"echo -n $TEST > {self.to1}")
            yield tools.bash.get_action("script")(ctx, f"echo -n ${self.frm.key} > {self.to2}")
            yield tools.bash.get_action("script")(ctx, f"echo -n {self.frm.val} > {self.to3}")

    class TFComplexArgEnvDeep(Transform):
        frm: Any = Transform.IN()
        to: Path = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, f"echo -n $TEST > {self.to}")

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
        frm: str = Transform.IN()
        to: ComplexOutIface = Transform.OUT()
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, f"echo -n {self.frm} > {self.to['p0']}")

    def test_complex_out(self, api: ConfigApi):
        text = "hello world"

        tf = self.TFComplexOut(frm=text)
        tf.run(api.ctx)
        assert (tf.to.base / "p0").read_text() == text

    class TFDefaultBadExit(Transform):
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, "exit 1")

    class TFDefaultGoodExit(Transform):
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            yield tools.bash.get_action("script")(ctx, "exit 0")

    class TFAcceptBadExit(Transform):
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            result = yield tools.bash.get_action("script")(ctx, "exit 1")
            if result.exit_code == 1:
                result.accept()

    class TFRejectBadExit(Transform):
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            result = yield tools.bash.get_action("script")(ctx, "exit 1")
            if result.exit_code == 1:
                result.reject()

    class TFAcceptExitAndContinue(Transform):
        tools = (tools.Bash,)

        def execute(self, ctx, tools):
            r1 = yield tools.bash.get_action("script")(ctx, "exit 1")
            if r1.exit_code == 1 and r1.accept():
                yield tools.bash.get_action("script")(ctx, "exit 0")

    class TFRetryAndContinue(Transform):
        tools = (tools.Bash,)
        retries: int = Transform.IN()

        def execute(self, ctx, tools):
            retries_left = self.retries
            while retries_left > 0:
                result = yield tools.bash.get_action("script")(ctx, "exit 1")
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
