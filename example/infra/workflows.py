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

from typing import Iterable, Optional, Self
import click
from blockwork.build.transform import Transform
from blockwork.config.base import Config, Element
from blockwork.workflows import Workflow
from .transforms.lint import VerilatorLintTransform



class Build(Workflow):
    target: Config
    match: Optional[str]

    @classmethod
    @Workflow.Options.target()
    @click.option('--match', type=str, default=None)
    def from_command(cls, project, target, match):
        inst = cls(target=target, match=match)
        return inst

    def transform_filter(self, transform: Transform, element: Element) -> bool:
        return self.match is None or self.match.lower() in transform.__class__.__name__.lower()

class Test(Workflow):
    tests: list[Workflow]

    @classmethod
    @Workflow.Options.target()
    def from_command(cls, project, target):
        tests = [
            Build(target=target, match='mako')
        ]
        return cls(tests=tests)

    def iter_config(self) -> Iterable[Config]:
        yield from self.tests
    
    def transform_filter(self, transform: Transform, config: Config) -> bool:
        return False

class Lint(Workflow):
    target: Config

    @classmethod
    @Workflow.Options.target()
    def from_command(cls, project, target):
        inst = cls(target=target)
        return inst

    def transform_filter(self, transform: Transform, element: Element) -> bool:
        return isinstance(transform, VerilatorLintTransform)
