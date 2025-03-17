from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pytest

from blockwork.build.caching import Cache
from blockwork.config import CacheConfig
from blockwork.config.api import ConfigApi
from blockwork.config.base import Config
from blockwork.tools import Invocation, tools
from blockwork.transforms import Transform, transforms
from blockwork.workflows.workflow import Workflow


class DummyCache(Cache):
    """
    For use in unittests only
    """

    def __init__(self):
        self.cfg = CacheConfig(path="", name="dummy")
        self.content_store = {}

    @property
    def target_size(self) -> int:
        return 1024**2

    def store_item(self, key: str, frm: Path) -> bool:
        self.content_store[key] = frm.read_text() if frm.exists() else None
        return True

    def drop_item(self, key: str) -> bool:
        if key in self.content_store:
            del self.content_store[key]
        return True

    def fetch_item(self, key: str, to: Path, peek: bool = False) -> bool:
        if key in self.content_store:
            if self.content_store[key] is not None:
                to.write_text(self.content_store[key])
            return True
        return False

    def get_last_fetch_utc(self, key: str) -> float:
        return 0

    def set_last_fetch_utc(self, key: str):
        return None

    def iter_keys(self) -> Iterable[str]:
        yield from list(self.content_store.keys())


def match_gather(gather, expected_types):
    for actual, expected in zip(gather, expected_types, strict=True):
        (actual_config, actual_transforms, actual_targets) = actual
        (expected_config, expected_transforms, expected_targets) = expected
        assert isinstance(actual_config, expected_config)

        for actual_transform, expected_transform in zip(
            actual_transforms, expected_transforms, strict=True
        ):
            assert isinstance(actual_transform, expected_transform)

        for actual_target, expected_target in zip(actual_targets, expected_targets, strict=True):
            assert isinstance(actual_target, expected_target)


def match_transform_tree(transform_tree, expected_types):
    targets, depies, depents = transform_tree
    exp_targets, exp_depies = expected_types

    exp_depents = {}
    for k in exp_depies:
        exp_depents[k] = set()
    for k, vs in exp_depies.items():
        for v in vs:
            exp_depents[v].add(k)

    ttargets = {type(t) for t in targets}

    assert ttargets == set(exp_targets)

    tdepies = {}
    for k, vs in depies.items():
        tdepies[type(k)] = {type(v) for v in vs}

    tdepents = {}
    for k, vs in depents.items():
        tdepents[type(k)] = {type(v) for v in vs}

    assert set(tdepies.keys()) == set(exp_depies.keys())
    assert set(tdepents.keys()) == set(exp_depents.keys())

    for k in tdepies:
        assert tdepies[k] == exp_depies[k]

    for k in tdepents:
        assert tdepents[k] == exp_depents[k]


def match_results(results, run, stored, fetched, skipped):
    assert {type(i) for i in results.run} == set(run)
    assert {type(i) for i in results.stored} == set(stored)
    assert {type(i) for i in results.fetched} == set(fetched)
    assert {type(i) for i in results.skipped} == set(skipped)


@pytest.mark.usefixtures("api")
class TestWorkFlowDeps:
    class DummyTransform(Transform):
        def run(self, *args, **kwargs):
            return SimpleNamespace(run_time=1, exit_code=0)

    class TFAutoA(DummyTransform):
        test_ip: Path = Transform.IN()
        test_op: Path = Transform.OUT()

    class TFAutoB(DummyTransform):
        test_ip: Path = Transform.IN()
        test_op: Path = Transform.OUT()

    class TFControlled(DummyTransform):
        test_ip: Path = Transform.IN()
        test_op: Path = Transform.OUT(init=True)

    def test_gather(self, api: ConfigApi):
        workflow = Workflow("test")

        TransformA, TransformB = self.TFAutoA, self.TFAutoB  # noqa N806

        test_ip = api.ctx.host_scratch / "x"
        test_ip.touch()

        # Does it yield transforms and where they came from
        class ConfigA(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                yield TransformA(test_ip=test_ip)

        match_gather(workflow.gather(ConfigA()), [(ConfigA, [TransformA], [TransformA])])

        # Does the transform filter correctly identify targets
        class ConfigB(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                yield TransformA(test_ip=test_ip)

            def transform_filter(self, transform: Transform, config: Config):
                return isinstance(transform, TransformB)

        match_gather(workflow.gather(ConfigB()), [(ConfigB, [TransformA], [])])

        # Can we correctly get child config
        class ConfigC(Config):
            child: ConfigA

            def iter_config(self) -> Iterable[Config]:
                yield self.child

        match_gather(
            workflow.gather(ConfigC(child=ConfigA())),
            [(ConfigA, [TransformA], [TransformA]), (ConfigC, [], [])],
        )

        # Can we correctly filter child config transforms
        class ConfigD(Config):
            child: ConfigA

            def iter_config(self) -> Iterable[Config]:
                yield self.child

            def transform_filter(self, transform: Transform, config: Config):
                return isinstance(transform, TransformB)

        match_gather(
            workflow.gather(ConfigD(child=ConfigA())),
            [(ConfigA, [TransformA], []), (ConfigD, [], [])],
        )

        # Can we correctly allow child config to filter its own transforms
        class ConfigE(Config):
            child: ConfigA

            def iter_config(self) -> Iterable[Config]:
                yield self.child

            def transform_filter(self, transform: Transform, config: Config):
                return isinstance(transform, TransformB)

            def config_filter(self, config: Config):
                return isinstance(config, ConfigA)

        match_gather(
            workflow.gather(ConfigE(child=ConfigA())),
            [(ConfigA, [TransformA], [TransformA]), (ConfigE, [], [])],
        )

    def test_transform_tree(self, api: ConfigApi):
        workflow = Workflow("test")

        TransformA, TransformB = self.TFControlled, self.TFAutoB  # noqa N806

        test_ip = api.ctx.host_scratch / "x"
        test_ip.touch()

        # Do we get a single transform come out
        class ConfigA(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                yield TransformA(test_ip=test_ip, test_op=api.path("y"))

        match_transform_tree(
            workflow.get_transform_tree(ConfigA()),
            (
                {
                    TransformA,
                },
                {TransformA: set()},
            ),
        )

        # Do we see a dependency tree come out
        class ConfigB(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                test_path = api.ctx.host_scratch / "test0"
                b = TransformB(test_ip=test_path)
                a = TransformA(test_ip=api.path("tests"), test_op=test_path)
                yield b
                yield a

        match_transform_tree(
            workflow.get_transform_tree(ConfigB()),
            (
                {TransformA, TransformB},
                {
                    TransformA: set(),
                    TransformB: {
                        TransformA,
                    },
                },
            ),
        )

        # Do we see a dependency tree come out across configs
        test_path = api.ctx.host_scratch / "test1"

        class ConfigC(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                a = TransformA(test_ip=api.path("tests"), test_op=test_path)
                yield a

        class ConfigD(Config):
            child: ConfigC

            def iter_config(self) -> Iterable[Config]:
                yield self.child

            def iter_transforms(self) -> Iterable[Transform]:
                b = TransformB(test_ip=test_path)
                yield b

        match_transform_tree(
            workflow.get_transform_tree(ConfigD(child=ConfigC())),
            (
                [TransformA, TransformB],
                {
                    TransformA: set(),
                    TransformB: {
                        TransformA,
                    },
                },
            ),
        )

    def test_run(self, api: ConfigApi, tmp_path):
        workflow = Workflow("test")

        class Ctx:
            host_root = tmp_path
            host_scratch = tmp_path
            caches: ClassVar[list[Cache]] = [DummyCache()]
            cache_targets = False

        TransformA, TransformB = self.TFAutoA, self.TFAutoB  # noqa N806

        test_ip = api.ctx.host_scratch / "ip"
        test_ip.touch()

        # Do we see a dependency tree come out
        class ConfigA(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                yield (a := TransformA(test_ip=test_ip))
                yield TransformB(test_ip=a.test_op)

            def transform_filter(self, transform: Transform, config: Config):
                return isinstance(transform, TransformB)

        match_transform_tree(
            workflow.get_transform_tree(ConfigA()),
            (
                {
                    TransformB,
                },
                {
                    TransformA: set(),
                    TransformB: {
                        TransformA,
                    },
                },
            ),
        )

        orig_hash_content = Cache.hash_content
        Cache.hash_content = lambda path: ""
        results_1 = workflow._run(
            Ctx, *workflow.get_transform_tree(ConfigA()), parallel=False, concurrency=1
        )
        results_2 = workflow._run(
            Ctx, *workflow.get_transform_tree(ConfigA()), parallel=False, concurrency=1
        )
        Cache.hash_content = orig_hash_content

        match_results(
            results_1,
            run=[TransformA, TransformB],
            stored=[TransformA, TransformB],
            fetched=[],
            skipped=[],
        )

        match_results(
            results_2,
            run=[TransformB],
            stored=[TransformB],
            fetched=[TransformA],
            skipped=[],
        )

    class TFCp(Transform):
        bash: tools.Bash = Transform.TOOL()
        file: Path = Transform.IN()
        result: Path = Transform.OUT()

        def execute(self, ctx) -> Iterable[Invocation]:
            yield self.bash.cp(ctx, frm=self.file, to=self.result)

    def test_multistep(self, api: ConfigApi):
        "Test chain of transforms with multiple steps"
        cp = self.TFCp

        class MyConfig(Config):
            input_path: str
            output_path: str | None

            def iter_transforms(self):
                # Run step1 on the input_path
                yield (step1 := cp(file=Path(self.input_path)))
                # Run step2 with the output from step1
                yield (step2 := cp(file=step1.result))
                # Expose the output of the chain (need to think about the syntax for this more)
                if self.output_path:
                    yield transforms.Copy(frm=step2.result, to=Path(self.output_path))

        i = api.ctx.host_root / "in"
        o = api.ctx.host_root / "out"

        text = "this is some text"
        i.write_text(text)

        workflow = Workflow("test")
        with ConfigApi(api.ctx):
            cfg = MyConfig(input_path=i.as_posix(), output_path=o.as_posix())
        workflow._run(api.ctx, *workflow.get_transform_tree(cfg), parallel=False, concurrency=1)

        assert o.read_text() == text
