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

from abc import ABC
from pathlib import Path
from typing import Iterable, TYPE_CHECKING, Optional

import yaml
if TYPE_CHECKING:
    from ..context import Context
    from . import parsers # noqa: F401
from ..build.interface import FileInterface
from ..build.transform import Transform

from ..common.checkeddataclasses import dataclass
from dataclasses import dataclass as unchecked_dataclass
from ..common.yaml import ConverterRegistry, DataclassConverter


class Config(ABC):
    'Base class for all config'
    _registry: ConverterRegistry
    _converter: type[DataclassConverter] = DataclassConverter
    _YAML_TAG: Optional[str] = None

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        dataclass(kw_only=True)(cls)
        if Config in cls.__bases__:
            cls._registry = ConverterRegistry()
        cls._registry.register(cls._converter, tag=cls._YAML_TAG)(cls)


class Site(Config):
    'Base class for site configuration'
    projects: dict[str, str]


class Project(Config):
    'Base class for project configuration'
    units: dict[str, str]


@unchecked_dataclass(kw_only=True)
class ElementContext:
    'Context object bound on to each element to keep track of where it came from'
    unit: str
    config: Path
    unit_project_path: Path
    unit_scratch_path: Path


class ElementFileInterface(FileInterface):
    """
    File interface for config elements
    """
    def __init__(self, element: "Element", path: str) -> None:
        self.element = element
        self.path = Path(path)

    def keys(self):
        yield (self.element._context.unit, self.path)
    
    def resolve_output(self, ctx: "Context"):
        return (self.element._context.unit_scratch_path / self.transform.id() / self.path)
    
    def resolve_input(self, ctx: "Context"):
        return (self.element._context.unit_project_path / self.path)


class ElementConverter(DataclassConverter["Element", "parsers.Element"]):
    def construct_scalar(self, loader: yaml.Loader, node: yaml.ScalarNode) -> "Element":
        # Allow elements to be indirected with a path e.g. `!<element> [<unit>.<path>]`
        target = loader.construct_scalar(node)
        if not isinstance(target, str):
            raise RuntimeError
        return self.parser.parse_target(target, self.typ)
    
    def construct_mapping(self, loader: yaml.Loader, node: yaml.MappingNode) -> "Element":
        unit = self.parser.unit
        unit_project_path = self.parser.ctx.host_root / self.parser.project.units[unit]
        unit_scratch_path = self.parser.ctx.host_scratch / self.parser.project.units[unit]
        def dict_callback(node_dict):
            node_dict['_context'] = ElementContext(
                unit=unit,
                config=Path(node.start_mark.name),
                unit_project_path=unit_project_path,
                unit_scratch_path=unit_scratch_path
            )
        element = super().construct_mapping(loader, node, dict_callback=dict_callback)
        return element


class Element(Config):
    "Base class for element configuration"
    _converter = ElementConverter
    _context: ElementContext

    def iter_sub_elements(self) -> Iterable["Element"]:
        """
        Yields any sub-elements which are used as part of this one.

        Implementation notes:
            - This function must be implemented when sub-elements are used.
        """
        yield from []

    def iter_transforms(self) -> Iterable[Transform]:
        """
        Yields any transforms from this element.
        """
        yield from []

    def file_interface(self, path):
        """
        Utility method to to create a fileinterface for this element.
        """
        return ElementFileInterface(self, path)
