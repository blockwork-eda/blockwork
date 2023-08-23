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

from blockwork.common.checkeddataclasses import dataclass, field
from blockwork.config import base
from blockwork.config import registry
from blockwork.common.yaml import DataclassConverter
from blockwork.config.parser import ElementConverter


@registry.site.register(DataclassConverter)
@dataclass(kw_only=True)
class Site(base.Site):
    pass


@registry.project.register(DataclassConverter)
@dataclass(kw_only=True)
class Project(base.Project):
    pass


@registry.element.register(ElementConverter)
@dataclass(kw_only=True)
class Design(base.Element):
    top: str
    sources: list[str]
    transforms: list[base.Transform] = field(default_factory=list)

    def iter_sub_elements(self):
        yield from self.transforms

    def resolve_input_paths(self, resolved):
        self.sources = resolved(self.sources)


@registry.element.register(ElementConverter)
@dataclass(kw_only=True)
class Testbench(base.Element):
    design: Design
    bench_python: str
    bench_make: str

    def iter_sub_elements(self):
        yield self.design

    def resolve_input_paths(self, resolver):
        self.bench_python = resolver(self.bench_python)
        self.bench_make = resolver(self.bench_make)
