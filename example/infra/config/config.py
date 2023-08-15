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
@dataclass
class Site(base.Site):
    pass


@registry.project.register(DataclassConverter)
@dataclass
class Project(base.Project):
    pass


@registry.element.register(ElementConverter)
@dataclass
class Design(base.Element):
    top: str
    sources: list[str] = field(default_factory=list)


@registry.element.register(ElementConverter)
@dataclass
class Testbench(base.Element):
    design: Design
