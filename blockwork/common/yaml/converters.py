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

import sys
from typing import Any, Callable, Generic, Iterable, Optional, TypeVar, cast, TYPE_CHECKING
from pathlib import Path
from dataclasses import _MISSING_TYPE, fields
import abc
import yaml
if TYPE_CHECKING:
    from .parsers import Parser
try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader


class YamlConversionError(yaml.YAMLError):
    'Error parsing yaml'
    def __init__(self, location: Path|str, msg: str):
        self.location = location
        self.msg = msg

    def __str__(self):
        return f"{self.location}: {self.msg}"


class YamlFieldError(YamlConversionError):
    'Error parsing yaml field'
    def __init__(self, location: str, ex: Exception, field: Optional[str] = None):
        self.field = field
        self.orig_ex = ex
        field_str = "" if self.field is None else f" at field `{self.field}`"
        super().__init__(f"{location}{field_str}", str(ex))


class YamlMissingFieldsError(YamlConversionError):
    def __init__(self, location: str, fields: Iterable[str]):
        self.fields = fields
        super().__init__(location, f"Missing field(s) `{', '.join(self.fields)}`")


class YamlExtraFieldsError(YamlConversionError):
    def __init__(self, location: str, fields: Iterable[str]):
        self.fields = fields
        super().__init__(location, f"Got extra field(s) `{', '.join(self.fields)}`")



_Convertable = TypeVar('_Convertable')
_Parser = TypeVar('_Parser', bound="Parser",)
class Converter(abc.ABC, Generic[_Convertable, _Parser]):
    """
    Defines how to convert between a yaml tag and a python type, intended
    to be subclassed and used in parser registries. For example::

        class WrapConverter(Converter):
            def construct_scalar(self, loader, node):
                return self.typ(loader.construct_scalar(node))

        wrap_parser = Parser()

        @wrap_parser.register(WrapConverter, tag='!Wrap')
        class Wrapper:
            def __init__(self, content):
                self.content = content

        print(wrap_parser.parse_str("data: !Wrap yum"))
    """

    def __init__(self, *, tag: str, typ: type[_Convertable], parser: _Parser):
        self.tag = tag
        self.typ = typ
        self.parser = parser

    def construct(self, loader: Loader, node: yaml.Node):
        match node:
            case yaml.nodes.MappingNode():
                return self.construct_mapping(loader, node)
            case yaml.nodes.SequenceNode():
                return self.construct_sequence(loader, node)
            case yaml.nodes.ScalarNode():
                return self.construct_scalar(loader, node)
            case yaml.nodes.CollectionNode():
                return self.construct_collection(loader, node)
            case _:
                return self.construct_node(loader, node)
        
    def represent(self, dumper: Dumper, value: _Convertable):
        return self.represent_node(dumper, value)
    
    def construct_mapping(self, loader: Loader, node: yaml.MappingNode) -> _Convertable:
        return self.construct_node(loader, node)

    def construct_sequence(self, loader: Loader, node: yaml.SequenceNode) -> _Convertable:
        return self.construct_node(loader, node)

    def construct_scalar(self, loader: Loader, node: yaml.ScalarNode) -> _Convertable:
        return self.construct_node(loader, node)

    def construct_collection(self, loader: Loader, node: yaml.CollectionNode) -> _Convertable:
        return self.construct_node(loader, node)

    def construct_node(self, loader: Loader, node: yaml.Node) -> _Convertable:
        raise NotImplementedError

    def represent_node(self, dumper: Dumper, value: _Convertable) -> yaml.Node:
        raise NotImplementedError


class ConverterRegistry:
    """
    Creates an object with which to register converters which
    can be used to initialise a Parser object.
    """
    def __init__(self):
        self._registered_tags: set[str] = set()
        self._registered_typs: set[Any] = set()
        self._registry: list[tuple[str, Any, type[Converter]]] = []

    def __iter__(self):
        yield from self._registry

    def register(self, Converter: type[Converter], *, tag: Optional[str]=None)\
                 -> Callable[[type[_Convertable]], type[_Convertable]]:
        """
        Register a object for parsing with this parser object.

        :param tag: The yaml tag to register as (!ClassName otherwise)
        """
        def wrap(typ: type[_Convertable]) -> type[_Convertable]:
            inner_tag = f"!{typ.__name__}" if tag is None else tag

            if inner_tag in self._registered_tags:
                raise RuntimeError(f'Converter already exists for tag `{inner_tag}`')
            
            if typ in self._registered_typs:
                raise RuntimeError(f'Converter already exists for type `{typ}`')
            
            self._registry.append((inner_tag, typ, Converter))
            return typ
        return wrap


class DataclassConverter(Converter[_Convertable, _Parser]):
    def construct_mapping(self,
                          loader: Loader,
                          node: yaml.MappingNode,
                          dict_callback: Optional[Callable[[dict[str, Any]], None]]=None) -> _Convertable:
        loc = f"{Path(node.start_mark.name).absolute()}:{node.start_mark.line}:{node.start_mark.column}"
        node_dict = cast(dict[str, Any], loader.construct_mapping(node, deep=True))

        # Get some info from the fields
        required_keys = set()
        keys = set()
        for field in fields(self.typ):
            keys.add(field.name)
            if isinstance(field.default, _MISSING_TYPE) and isinstance(field.default_factory, _MISSING_TYPE):
                required_keys.add(field.name)

        # Gives the caller an opportunity to modify the read dict prior to checking
        # e.g. to add extra implicit data
        if dict_callback:
            dict_callback(node_dict)
                
        # Check there are no extra fields provided
        if (extra := set(node_dict.keys()) - set(keys)):
            raise YamlExtraFieldsError(loc, extra)

        # Check there are no missing fields
        missing = set(required_keys) - set(node_dict.keys())
        if missing:
            raise YamlMissingFieldsError(loc, missing)

        try:
            # Create the dataclass instance
            instance = self.typ(**node_dict)
        except TypeError as ex:
            # Note, might be nice to add some heuristics to get the location based on the field error
            sys.tracebacklimit = 0
            raise YamlFieldError(loc, ex, getattr(ex, 'field', None)) from None

        return instance
    
    def represent_node(self, dumper: Dumper, value: _Convertable) -> yaml.Node:
        return dumper.represent_mapping(self.tag, value.__dict__)
