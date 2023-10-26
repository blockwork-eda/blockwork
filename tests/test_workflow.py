from pathlib import Path
from typing import Any, Iterable, Optional
import pytest
from blockwork.build.caching import Cache
from blockwork.build.interface import Interface
from blockwork.build.transform import Transform

from blockwork.config.base import Config
from blockwork.workflows.workflow import Workflow

class DummyCache(Cache):
    '''
    For use in unittests only
    '''
    def __init__(self):
        self.key_store = {}
        self.content_store = {}

    def store_hash(self, key_hash: str, content_hash: str) -> bool:
        self.key_store[key_hash] = content_hash
        return True

    def drop_hash(self, key_hash: str, content_hash: str) -> bool:
        del self.key_store[key_hash]
        return True
    
    def fetch_hash(self, key_hash: str) -> Optional[str]:
        return self.key_store.get(key_hash, None)

    def store_item(self, content_hash: str, frm: Path) -> bool:
        self.content_store[content_hash] = frm
        return True

    def drop_item(self, content_hash: str) -> bool:
        del self.content_store[content_hash]
        return True

    def fetch_item(self, content_hash: str, to: Path) -> bool:
        if content_hash in self.content_store:
            return True
        return False

def match_gather(gather, expected_types):
    for actual, expected in zip(gather, expected_types, strict=True):
        (actual_config, actual_transforms, actual_targets) = actual
        (expected_config, expected_transforms, expected_targets) = expected
        assert isinstance(actual_config, expected_config)

        for actual_transform, expected_transform in zip(actual_transforms, expected_transforms, strict=True):
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

    ttargets = set(type(t) for t in targets)

    assert ttargets == set(exp_targets)

    tdepies = {}
    for k, vs in depies.items():
        tdepies[type(k)] = set(type(v) for v in vs)

    tdepents = {}
    for k, vs in depents.items():
        tdepents[type(k)] = set(type(v) for v in vs)

    assert set(tdepies.keys()) == set(exp_depies.keys())
    assert set(tdepents.keys()) == set(exp_depents.keys())

    for k in tdepies:
        assert tdepies[k] == exp_depies[k]

    for k in tdepents:
        assert tdepents[k] == exp_depents[k]

def match_results(results, run, stored, fetched, skipped):
    assert set(type(i) for i in results.run) == set(run)
    assert set(type(i) for i in results.stored) == set(stored)
    assert set(type(i) for i in results.fetched) == set(fetched)
    assert set(type(i) for i in results.skipped) == set(skipped)



class TestC:

    def test_gather(self):
        workflow = Workflow('test')

        class TransformA(Transform): ...
        class TransformB(Transform): ...

        # Does it yield transforms and where they came from
        class ConfigA(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                yield TransformA()

        match_gather(workflow.gather(ConfigA()), [
            (ConfigA, [TransformA], [TransformA])
        ])

        # Does the transform filter correctly identify targets
        class ConfigB(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                yield TransformA()

            def transform_filter(self, transform: Transform, config: Config):
                return isinstance(transform, TransformB)

        match_gather(workflow.gather(ConfigB()), [
            (ConfigB, [TransformA], [])
        ])

        # Can we correctly get child config
        class ConfigC(Config):
            child: ConfigA

            def iter_config(self) -> Iterable[Config]:
                yield self.child

        match_gather(workflow.gather(ConfigC(child=ConfigA())), [
            (ConfigA, [TransformA], [TransformA]),
            (ConfigC, [], [])
        ])

        # Can we correctly filter child config transforms
        class ConfigD(Config):
            child: ConfigA

            def iter_config(self) -> Iterable[Config]:
                yield self.child

            def transform_filter(self, transform: Transform, config: Config):
                return isinstance(transform, TransformB)

        match_gather(workflow.gather(ConfigD(child=ConfigA())), [
            (ConfigA, [TransformA], []),
            (ConfigD, [], [])
        ])

        # Can we correctly allow child config to filter its own transforms
        class ConfigE(Config):
            child: ConfigA

            def iter_config(self) -> Iterable[Config]:
                yield self.child

            def transform_filter(self, transform: Transform, config: Config):
                return isinstance(transform, TransformB)
            
            def config_filter(self, config: Config):
                return isinstance(config, ConfigA)
    
        match_gather(workflow.gather(ConfigE(child=ConfigA())), [
            (ConfigA, [TransformA], [TransformA]),
            (ConfigE, [], [])
        ])

    def test_transform_tree(self):
        workflow = Workflow('test')

        class TransformA(Transform): ...
        class TransformB(Transform): ...

        # Do we get a single transform come out
        class ConfigA(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                yield TransformA()

        match_transform_tree(workflow.get_transform_tree(ConfigA()), (
            set([TransformA]), {TransformA: set()}
        ))

        # Do we see a dependency tree come out
        class ConfigB(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                test_iface = Interface('test')
                yield TransformB().bind_inputs(test_ip=test_iface)
                yield TransformA().bind_outputs(test_op=test_iface)

        match_transform_tree(workflow.get_transform_tree(ConfigB()), (
            set([TransformA, TransformB]), {
                TransformA: set(),
                TransformB: set([TransformA])
            }
        ))

        # Do we see a dependency tree come out across configs
        test_iface = Interface('test')
        class ConfigC(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                yield TransformA().bind_outputs(test_op=test_iface)
        
        class ConfigD(Config):
            child: ConfigC

            def iter_config(self) -> Iterable[Config]:
                yield self.child

            def iter_transforms(self) -> Iterable[Transform]:
                yield TransformB().bind_inputs(test_ip=test_iface)

        match_transform_tree(workflow.get_transform_tree(ConfigD(child=ConfigC())), (
            [TransformA, TransformB], {
                TransformA: set(),
                TransformB: set([TransformA])
            }
        ))

    def test_run(self):
        workflow = Workflow('test')
        class ctx:
            caches = [DummyCache()]

        class DummyTransform(Transform):
            def run(self, *args, **kwargs): ...

        class TransformA(DummyTransform): ...

        class TransformB(DummyTransform): ...

        # Do we see a dependency tree come out
        class ConfigA(Config):
            def iter_transforms(self) -> Iterable[Transform]:
                test_iface = Interface(Path('xyztestpath'))
                yield TransformB().bind_inputs(test_ip=test_iface)
                yield TransformA().bind_outputs(test_op=test_iface)
            
            def transform_filter(self, transform: Transform, config: Config):
                return isinstance(transform, TransformB)

        match_transform_tree(workflow.get_transform_tree(ConfigA()), (
            set([TransformB]), {
                TransformA: set(),
                TransformB: set([TransformA])
            }
        ))

        orig_hash_content = Cache.hash_content
        Cache.hash_content = lambda path: ''
        results_1 = workflow._run(ctx, *workflow.get_transform_tree(ConfigA()))
        results_2 = workflow._run(ctx, *workflow.get_transform_tree(ConfigA()))
        Cache.hash_content = orig_hash_content

        match_results(results_1, 
                      run=[TransformA, TransformB],
                      stored=[TransformA, TransformB],
                      fetched=[],
                      skipped=[])
        
        match_results(results_2, 
                      run=[TransformB],
                      stored=[TransformB],
                      fetched=[TransformA],
                      skipped=[])
