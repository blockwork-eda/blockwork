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

from typing import Iterable, Optional
from blockwork.workflows.workflow import Workflow
import click
from blockwork.build.transform import Transform
from blockwork.config.base import Config, Element
from .transforms.lint import VerilatorLintTransform



class Build(Config):
    target: Config
    match: Optional[str]

    @Workflow("build").with_target()
    @click.option('--match', type=str, default=None)
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
        tests = [
            Build(target=target, match='mako')
        ]
        return Test(tests=tests)

    def iter_config(self) -> Iterable[Config]:
        yield from self.tests
    
    def config_filter(self, config: Config):
        return config in self.tests

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
