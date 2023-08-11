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

from pathlib import Path
from typing import TypeVar

import yaml
from blockwork.common.yaml import Parser, DataclassConverter

from . import base, registry

_Convertable = TypeVar('_Convertable')


class Site(Parser):
    "Parser for site yaml files"
    def __init__(self):
        super().__init__(registry.site)

class Project(Parser):
    "Parser for project yaml files"
    def __init__(self, site: base.Site):
        super().__init__(registry.project)
        self.site = site

class Element(Parser):
    "Parser for 'element' yaml files where an 'element' is a unit of configuration within the target" 
    def __init__(self, site: base.Site, project: base.Project):
        super().__init__(registry.element)
        self.site = site
        self.project = project

class ElementConverter(DataclassConverter[_Convertable, Element]):
    def construct_sequence(self, loader: yaml.Loader, node: yaml.SequenceNode) -> _Convertable:
        # Allow elements to be indirected with a path e.g. `!<element> [<path-to-element>]`
        sequence = loader.construct_sequence(node, deep=True)
        return self.parser.parse(Path(sequence[0]))
