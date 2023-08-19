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
from typing import TypeVar, cast

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
        self._block_stack: list[str] = []

    def parse_target(self, target_spec: str, target_type: type[base.Element]):
        """
        Parse a target config file based on the target block, path within that 
        block and expected type

        :param target_spec: The target specified as `<block>.<path>` or `<path>` 
                            where path is the path within the block to the yaml,
                            not including the extension. The <block> component
                            is inferred where possible.
        :param target_type: Expected element type
        """
        target_parts = target_spec.split('.')
        if len(target_parts) == 2:
            # Path and block specified as `<block>.<path>`, `.<path>`, or `.`
            block, target = target_parts
        elif len(target_parts) == 1:
            # Block specified as `<block>` or ``
            block, target = target_parts[0], ''
        else:
            raise RuntimeError(f'Invalid target specification: `{target_spec}`')

        # If given empty block, infer here.
        if block == '':
            if (block := self.block) is None:
                raise RuntimeError(f'Require implicit block for `{target_spec}`, but not in block context!')
            
        # If given empty target, infer here.
        if target == '':
            target = target_type.__name__.lower()

        # Get the path to the config file
        block_path = self.ctx.host_root / self.project.blocks[block]
        config_path = block_path / f"{target}.yaml"

        # We're evaluating config files recursively going down, keep track
        # of the current block so we can use it for relative references.
        with self.block_context(block):
            return self(target_type).parse(config_path)

    @contextlib.contextmanager
    def block_context(self, block: str):
        "Context manager for parsing under a particular blocks context"
        self._block_stack.append(block)
        try:
            yield None
        finally:
            self._block_stack.pop()

    @property
    def block(self):
        "The parser's current block context"
        try:
            return self._block_stack[-1]
        except IndexError:
            return None

        
class ElementConverter(DataclassConverter[base.Element, Element]):
    def construct_scalar(self, loader: yaml.Loader, node: yaml.ScalarNode) -> base.Element:
        # Allow elements to be indirected with a path e.g. `!<element> [<block>.<path>]`
        target = loader.construct_scalar(node)
        if not isinstance(target, str):
            raise RuntimeError
        return self.parser.parse_target(target, self.typ)
    
    def construct_mapping(self, loader: yaml.Loader, node: yaml.MappingNode) -> base.Element:
        element = super().construct_mapping(loader, node)
        element._context = base.ElementContext(block=self.parser.block, config=Path(node.start_mark.name))
        return element
