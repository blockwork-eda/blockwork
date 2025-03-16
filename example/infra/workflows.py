# Copyright 2023, Blockwork, github.com/intuity/blockwork
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Iterable

import click

from blockwork.common.checkeddataclasses import field
from blockwork.config.base import Config, ConfigProtocol
from blockwork.transforms import Transform
from blockwork.workflows.workflow import Workflow

from .config.config import Testbench
from .transforms.lint import VerilatorLintTransform
from .transforms.sim import SimTransform, TbCompileVerilatorTransform


class Build(Config):
    target: Config
    match: str | None

    @Workflow("build").with_target()
    @click.option("--match", type=str, default=None)
    @staticmethod
    def from_command(ctx, project, target, match):
        return Build(target=target, match=match)

    def iter_config(self) -> Iterable[Config]:
        yield self.target

    def transform_filter(self, transform: Transform, config: ConfigProtocol) -> bool:
        return self.match is None or self.match.lower() in transform.__class__.__name__.lower()


class Test(Config):
    tests: list[Config]

    @Workflow("test").with_target()
    @staticmethod
    def from_command(ctx, project, target):
        tests = [Build(target=target, match=None)]
        return Test(tests=tests)

    def iter_config(self) -> Iterable[ConfigProtocol]:
        yield from self.tests

    def config_filter(self, config: ConfigProtocol):
        return config in self.tests

    def transform_filter(self, transform: Transform, config: ConfigProtocol) -> bool:
        return isinstance(transform, SimTransform)


class Lint(Config):
    target: Config

    @Workflow("lint").with_target()
    @staticmethod
    def from_command(ctx, project, target):
        return Lint(target=target)

    def transform_filter(self, transform: Transform, config: ConfigProtocol) -> bool:
        return isinstance(transform, VerilatorLintTransform)

    def iter_config(self) -> Iterable[Config]:
        yield self.target


class Sim(Config):
    testbench: Testbench
    tests: list[dict] = field(default_factory=list)

    # @Workflow("sim").with_target(Testbench)
    # @staticmethod
    # def from_command(
    #     ctx,
    #     project,
    #     target,
    # ):
    #     return Sim(
    #         testbench=target,
    #         tests=[]
    #     )

    def iter_config(self) -> Iterable[Config]:
        yield self.testbench

    def transform_filter(self, transform: Transform, config: ConfigProtocol):
        return config is self and isinstance(transform, SimTransform)

    def iter_transforms(self) -> Iterable[Transform]:
        tb = self.testbench
        yield (
            tf := TbCompileVerilatorTransform(
                design=tb.design.as_design_interface(),
                vtop=tb.design.top,
            )
        )

        yield SimTransform(
            pytop=tb.python.top,
            vtop=tb.design.top,
            exe=tf.exe,
            seed=0,
            testcase="",
            python=tb.python.as_python_interface(),
        )
