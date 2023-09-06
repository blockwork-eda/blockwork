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

from typing import Iterable
from blockwork.build.transform import Transform
from blockwork.common.checkeddataclasses import field
from blockwork.config import base
from ..transforms.lint import DesignInterface, VerilatorLintTransform
from ..transforms.templating import MakoTransform


class Site(base.Site):
    pass


class Project(base.Project):
    pass

class Mako(base.Element):
    template: str
    output: str

    def iter_transforms(self):
        yield MakoTransform(
            template=self.file_interface(self.template),
            output=self.file_interface(self.output)
        )


class Design(base.Element):
    top: str
    sources: list[str]
    transforms: list[Mako] = field(default_factory=list)

    def iter_elements(self):
        yield from self.transforms

    def iter_transforms(self) -> Iterable[Transform]:
        idesign = DesignInterface(sources=map(self.file_interface, self.sources),
                                  headers=[])
        yield VerilatorLintTransform(idesign)


class Testbench(base.Element):
    design: Design
    bench_python: str
    bench_make: str

    def iter_elements(self):
        yield self.design
