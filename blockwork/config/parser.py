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

import contextlib
from pathlib import Path

import yaml
from blockwork.common.yaml import Parser, DataclassConverter
from blockwork.context import Context

from . import base, registry


class Site(Parser):
    "Parser for site yaml files"
    def __init__(self, ctx: Context):
        super().__init__(registry.site)
        self.ctx = ctx

class Project(Parser):
    "Parser for project yaml files"
    def __init__(self, ctx: Context, site: base.Site):
        super().__init__(registry.project)
        self.ctx = ctx
        self.site = site

class Element(Parser):
    "Parser for 'element' yaml files where an 'element' is a unit of configuration within the target" 
    def __init__(self, ctx: Context, site: base.Site, project: base.Project):
        super().__init__(registry.element)
        self.ctx = ctx
        self.site = site
        self.project = project
        self._unit_stack: list[str] = []

    def parse_target(self, target_spec: str, target_type: type[base.Element]):
        """
        Parse a target config file based on the target unit, path within that 
        unit and expected type

        :param target_spec: The target specified as `<unit>.<path>` or `<path>` 
                            where path is the path within the unit to the yaml,
                            not including the extension. The <unit> component
                            is inferred where possible.
        :param target_type: Expected element type
        """
        target_parts = target_spec.split('.')
        if len(target_parts) == 2:
            # Path and unit specified as `<unit>.<path>`, `.<path>`, or `.`
            unit, target = target_parts
        elif len(target_parts) == 1:
            # Unit specified as `<unit>` or ``
            unit, target = target_parts[0], ''
        else:
            raise RuntimeError(f'Invalid target specification: `{target_spec}`')

        # If given empty unit, infer here.
        if unit == '':
            if (unit := self.unit) is None:
                raise RuntimeError(f'Require implicit unit for `{target_spec}`, but not in unit context!')
            
        # If given empty target, infer here.
        if target == '':
            target = target_type.__name__.lower()

        # Get the path to the config file
        unit_path = self.ctx.host_root / self.project.units[unit]
        config_path = unit_path / f"{target}.yaml"

        # We're evaluating config files recursively going down, keep track
        # of the current unit so we can use it for relative references.
        with self.unit_context(unit):
            return self(target_type).parse(config_path)

    @contextlib.contextmanager
    def unit_context(self, unit: str):
        "Context manager for parsing under a particular unit's context"
        self._unit_stack.append(unit)
        try:
            yield None
        finally:
            self._unit_stack.pop()

    @property
    def unit(self):
        "The parser's current unit context"
        try:
            return self._unit_stack[-1]
        except IndexError:
            return None

        
class ElementConverter(DataclassConverter[base.Element, Element]):
    def construct_scalar(self, loader: yaml.Loader, node: yaml.ScalarNode) -> base.Element:
        # Allow elements to be indirected with a path e.g. `!<element> [<unit>.<path>]`
        target = loader.construct_scalar(node)
        if not isinstance(target, str):
            raise RuntimeError
        return self.parser.parse_target(target, self.typ)
    
    def construct_mapping(self, loader: yaml.Loader, node: yaml.MappingNode) -> base.Element:
        element = super().construct_mapping(loader, node)
        element._context = base.ElementContext(unit=self.parser.unit, config=Path(node.start_mark.name))
        return element
