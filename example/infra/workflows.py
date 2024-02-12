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

import shlex
from collections.abc import Iterable
from pathlib import Path

import click

from blockwork.build.interface import ArgsInterface, FileInterface
from blockwork.build.transform import Transform
from blockwork.common.checkeddataclasses import field
from blockwork.config.base import Config
from blockwork.tools.tool import Invocation
from blockwork.workflows.workflow import Workflow

from .tools.misc import PythonSite
from .transforms.examples import CapturedTransform
from .transforms.lint import VerilatorLintTransform


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

    def transform_filter(self, transform: Transform, config: Config) -> bool:
        return self.match is None or self.match.lower() in transform.__class__.__name__.lower()


class Test(Config):
    tests: list[Config]

    @Workflow("test").with_target()
    @staticmethod
    def from_command(ctx, project, target):
        tests = [Build(target=target, match="mako")]
        return Test(tests=tests)

    def iter_config(self) -> Iterable[Config]:
        yield from self.tests

    def config_filter(self, config: Config):
        return config in self.tests

    def iter_transforms(self) -> Iterable[Transform]:
        yield CapturedTransform(output=FileInterface(Path("./captured_stdout")))


class Lint(Config):
    target: Config

    @Workflow("lint").with_target()
    @staticmethod
    def from_command(ctx, project, target):
        return Lint(target=target)

    def transform_filter(self, transform: Transform, config: Config) -> bool:
        return isinstance(transform, VerilatorLintTransform)

    def iter_config(self) -> Iterable[Config]:
        yield self.target


class Cat(Config):
    """
    This example shows an anonymous transform and the arg interface.
    """

    args: list[str] = field(default_factory=list)

    @Workflow("cat")
    @click.argument("args", nargs=-1, type=click.UNPROCESSED)
    @staticmethod
    def from_command(ctx, args):
        return Cat(args=list(args))

    def iter_transforms(self) -> Iterable[Transform]:
        yield (
            Transform()
            .bind_tools(PythonSite)
            .bind_inputs(args=ArgsInterface(self.args))
            .bind_execute(
                lambda c, t, i: [
                    Invocation(version=t.pythonsite, execute="cat", args=shlex.split(i.args))
                ]
            )
        )
