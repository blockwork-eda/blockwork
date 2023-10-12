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
from typing import Iterable, TYPE_CHECKING, Optional

import yaml

from ..common.singleton import keyed_singleton
if TYPE_CHECKING:
    from ..context import Context
    from . import parsers # noqa: F401
from ..build.interface import FileInterface
from ..build.transform import Transform

from ..common.checkeddataclasses import dataclass
from dataclasses import dataclass as unchecked_dataclass
from ..common.yaml import ConverterRegistry, DataclassConverter


class Config(metaclass=keyed_singleton(inst_key=lambda i:hash(i))):
    '''
    Base class for all config.
    All-caps keys are reserved.
    '''
    _REGISTRY: ConverterRegistry = ConverterRegistry()
    "Defines which YAML registry the config belongs to i.e. site/project/element"
    _CONVERTER: type[DataclassConverter] = DataclassConverter
    "Defines how to convert the YAML tag into a Python object"
    YAML_TAG: Optional[str] = None
    "The !<Tag> to represent this document in YAML"
    FILE_NAME: Optional[str] = None
    "The source for this element, for example the file/line origin"
    SRC: Optional[str] = None
    """The implicit file name to use when one isn't provided, 
       defaults to YAML_TAG if provided, else class name"""
    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        dataclass(kw_only=True, frozen=True, eq=False, repr=False)(cls)
        cls._REGISTRY.register(cls._CONVERTER, tag=cls.YAML_TAG)(cls)

    def __init__(self, *args, **kwargs): ...

    def __hash__(self):
        if self.SRC:
            # If we know what the source is - i.e. a file on disc, 
            # the resultant dataclass should always be the same
            return hash(self.SRC)
        else:
            return id(self)
    
    def __eq__(self, other):
        return hash(self) == hash(other)

    def iter_config(self) -> Iterable["Config"]:
        """
        Yields any sub-config which is used as part of this one.

        Implementation notes:
            - This function must be implemented when sub-elements are used.
        """
        yield from []

    def iter_transforms(self) -> Iterable[Transform]:
        """
        Yields any transforms from this element.
        """
        yield from []

    def config_filter(self, config: "Config"):
        """
        Filter configs underneath this which are "interesting".

        For uninteresting configs, we use our own transform filter
        for transforms underneath them, for interesting configs we
        use theirs.
        """
        return False

    def transform_filter(self, transform: Transform, config: "Config"):
        """
        Filter transforms underneath this which are "interesting".

        Interesting transforms will be the run targets, uninteresting
        transforms which are dependencies will also get run.
        """
        return True

class Site(Config):
    'Base class for site configuration'
    projects: dict[str, str]


class Project(Config):
    'Base class for project configuration'
    units: dict[str, str]


@unchecked_dataclass(kw_only=True, frozen=True)
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

    def key(self):
        return (self.element.CTX.unit, self.path)
    
    def resolve_output(self, ctx: "Context"):
        return (self.element.CTX.unit_scratch_path / self.input_transform.id() / self.path)
    
    def resolve_input(self, ctx: "Context"):
        return (self.element.CTX.unit_project_path / self.path)


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
            node_dict['SRC'] = f"{node.start_mark.name}:{node.start_mark.line}:{node.start_mark.column}"
            node_dict['CTX'] = ElementContext(
                unit=unit,
                config=Path(node.start_mark.name),
                unit_project_path=unit_project_path,
                unit_scratch_path=unit_scratch_path
            )
        element = super().construct_mapping(loader, node, dict_callback=dict_callback)
        return element


class Element(Config):
    "Base class for element configuration"
    _CONVERTER = ElementConverter
    CTX: ElementContext
    SRC: str

    def file_interface(self, path):
        """
        Utility method to to create a fileinterface for this element.
        """
        return ElementFileInterface(self, path)
