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
from typing import Any, Generic, Iterable, Optional, TypeVar, cast
from pathlib import Path
from dataclasses import _MISSING_TYPE, fields
import abc
import yaml
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
class Converter(abc.ABC, Generic[_Convertable]):

    def __init__(self, tag: str, typ: type[_Convertable]):
        self.tag = tag
        self.typ = typ

    def construct(self, loader: Loader, node: yaml.Node):
        if isinstance(node, yaml.nodes.MappingNode):
            return self.construct_mapping(loader, node)
        elif isinstance(node, yaml.nodes.SequenceNode):
            return self.construct_sequence(loader, node)
        elif isinstance(node, yaml.nodes.ScalarNode):
            return self.construct_scalar(loader, node)
        elif isinstance(node, yaml.nodes.CollectionNode):
            return self.construct_collection(loader, node)
        else:
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


class DataclassConverter(Converter[_Convertable]):
    def construct_mapping(self, loader: Loader, node: yaml.MappingNode) -> _Convertable:
        loc = f"{Path(node.start_mark.name).absolute()}:{node.start_mark.line}:{node.start_mark.column}"
        node_dict = cast(dict[str, Any], loader.construct_mapping(node, deep=True))

        # Get some info from the fields
        required_keys = set()
        keys = set()
        for field in fields(self.typ):
            keys.add(field.name)
            if isinstance(field.default, _MISSING_TYPE) and isinstance(field.default_factory, _MISSING_TYPE):
                required_keys.add(field.name)
                
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
