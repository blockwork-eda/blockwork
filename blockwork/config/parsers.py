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

from ..common.yaml import Parser
from ..context import Context

from . import base


class Site(Parser):
    "Parser for site yaml files"
    def __init__(self, ctx: Context):
        super().__init__(base.Site._REGISTRY)
        self.ctx = ctx

class Project(Parser):
    "Parser for project yaml files"
    def __init__(self, ctx: Context, site: base.Site):
        super().__init__(base.Project._REGISTRY)
        self.ctx = ctx
        self.site = site

class Element(Parser):
    "Parser for 'element' yaml files where an 'element' is a unit of configuration within the target" 
    def __init__(self, ctx: Context, site: base.Site, project: base.Project):
        super().__init__(base.Element._REGISTRY)
        self.ctx = ctx
        self.site = site
        self.project = project
        self._unit_stack: list[str] = []

    def parse_target(self, target_spec: str, target_type: type[base.Element]):
        """
        Parse a target config file based on the target unit, path within that 
        unit and expected type

        :param target_spec: The target specified as `<unit>:<path>` or `<path>` 
                            where path is the path within the unit to the yaml,
                            not including the extension. The <unit> component
                            is inferred where possible.
        :param target_type: Expected element type
        """
        target_parts = target_spec.split(':')
        if len(target_parts) == 2:
            # Path and unit specified as `<unit>:<path>`, `:<path>`, or `:`
            unit, target = target_parts
            if not target:
                 raise RuntimeError(f'Invalid target specification `{target_spec}` (trailing `:` after unit)')
        elif len(target_parts) == 1:
            # Unit specified as `<unit>` or ``
            unit, target = target_parts[0], ''
        else:
            raise RuntimeError(f'Invalid target specification `{target_spec}` (too many `:`)')

        # If given empty unit, infer here.
        if unit == '':
            if (unit := self.unit) is None:
                raise RuntimeError(f'Require implicit unit for `{target_spec}`, but not in unit context!')
        # Get the path to the config file
        unit_path = self.ctx.host_root / self.project.units[unit]

        # The target should be either referring to a directory (in which case the
        # filename will be implicit based on the target type), or a file.
        implicit_file_name = (target_type.FILE_NAME or
                              target_type.YAML_TAG or
                              target_type.__name__.lower())
        directory_path = unit_path / target / f"{implicit_file_name}.yaml"
        file_path = unit_path / f"{target or implicit_file_name}.yaml"
        if directory_path.exists():
            config_path = directory_path
        elif file_path.exists():
            config_path = file_path
        else:
            raise RuntimeError(f'Config not found for {target_spec} at either `{directory_path}` or `{file_path}`')

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