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

from typing import Any, Generic, Optional, TypeVar
from pathlib import Path
import sys
from dataclasses import _MISSING_TYPE, fields
import yaml
try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader


class YamlDataclassError(yaml.YAMLError):
    'Error parsing yaml field'
    def __init__(self, location: str, msg: str):
        self.location = location
        self.msg = msg

    def __str__(self):
        return f"{self.location}: {self.msg}"


class YamlFieldError(YamlDataclassError):
    'Error parsing yaml field'
    def __init__(self, location: str, ex: Exception, field: Optional[str] = None):
        self.field = field
        self.orig_ex = ex
        field_str = "" if self.field is None else f" at field `{self.field}`"
        super().__init__(f"{location}{field_str}", str(ex))


class YamlMissingFieldsError(YamlDataclassError):
    def __init__(self, location: str, fields: list[str]):
        self.fields = fields
        super().__init__(location, f"Missing field(s) `{', '.join(self.fields)}`")


class YamlExtraFieldsError(YamlDataclassError):
    def __init__(self, location: str, fields: list[str]):
        self.fields = fields
        super().__init__(location, f"Got extra field(s) `{', '.join(self.fields)}`")


def constructorFactory(dc: type):
    "Creates and returns a yaml constructor for a dataclass"
    def constructor(loader: Loader, node: yaml.Node):
        # path:line:column
        loc = f"{Path(node.start_mark.name).absolute()}:{node.start_mark.line}:{node.start_mark.column}"

        if isinstance(node, yaml.nodes.MappingNode):
            node_dict = loader.construct_mapping(node, deep=True)

            # Get some info from the fields
            required_keys = set()
            keys = set()
            for field in fields(dc):
                keys.add(field.name)
                if isinstance(field.default, _MISSING_TYPE) and isinstance(field.default_factory, _MISSING_TYPE):
                    required_keys.add(field.name)
                    
            # Check there are no extra fields provided
            extra = set(node_dict.keys()) - set(keys)
            if extra:
                raise YamlExtraFieldsError(loc, extra)

            # Check there are no missing fields
            missing = set(required_keys) - set(node_dict.keys())
            if missing:
                raise YamlMissingFieldsError(loc, missing)
            
            try:
                # Create the dataclass instance
                instance = dc(**node_dict)
            except TypeError as ex:
                # Note, might be nice to add some heuristics to get the location based on the field error
                sys.tracebacklimit = 0
                raise YamlFieldError(loc, ex, getattr(ex, 'field', None)) from None

            return instance
        else:
            # Dataclasses can't be used to represent lists
            raise YamlDataclassError(loc, f"For tag `{node.tag}`, expected type `{dict}` but got `{node}`")
    return constructor


def representerFactory(tag):
    "Creates and returns a yaml representer from a dataclass"
    def representer(dumper: Dumper, node):
        return dumper.represent_mapping(tag, node.__dict__)
    return representer

_Parser_DC = TypeVar("_Parser_DC")
class _Parser(Generic[_Parser_DC]):
    """Yaml parser for a specific dataclass, created by ConfigFactory"""
    def __init__(self, dc: _Parser_DC, loader: Loader, dumper: Dumper):
        self.dc = dc
        self.loader = loader
        self.dumper = dumper

    def parse(self, path : Path) -> _Parser_DC:
        """
        Parse a YAML file from disk and return any dataclass object it contains.

        :param path: Path to the YAML file to parse
        :returns:    Parsed dataclass object
        """
        with path.open("r", encoding="utf-8") as fh:
            parsed: _Parser_DC = yaml.load(fh, Loader=self.loader)
        if not isinstance(parsed, self.dc):
            raise YamlDataclassError(path, f"Expected {self.dc} object got {type(parsed).__name__}")
        return parsed

    def parse_str(self, data : str) -> _Parser_DC:
        """
        Parse a YAML string and return any dataclass object it contains.

        :param data: YAML string
        :returns:    Parsed dataclass object
        """
        parsed : _Parser_DC = yaml.load(data, Loader=self.loader)
        if not isinstance(parsed, self.dc):
            raise YamlDataclassError("<unicode string>", f"Expected {self.dc} object got {type(parsed).__name__}")
        return parsed


class ParserFactory:
    """
    Creates an object which can be used to register dataclasses as
    Yaml tags, for example::

        YamlParser = YamlDataclassParserFactory()
        
        @YamlParser.register("!coord")
        @dataclass
        class Coordinate:
            x: int
            y: int
        
        # Parse as specific type (validates the result is a coordinate)
        YamlParser(Coordinate).parse_str(...)

        # Parse as any registered type
        YamlParser.parse_str(...)

    """
    def __init__(self):
        class loader(Loader):
            ...
        class dumper(Dumper):
            ...
        self.loader = loader
        self.dumper = dumper

    def register(self, tag: Optional[str]=None):
        """
        Register a dataclass for parsing with this parser object.

        :param tag: The yaml tag to register as (!ClassName otherwise)
        """
        Wrap_DC = TypeVar("Wrap_DC")
        def wrap(dc: Wrap_DC) -> Wrap_DC:
            inner_tag = f"!{dc.__name__}" if tag is None else tag
            self.loader.add_constructor(inner_tag, constructorFactory(dc))
            self.dumper.add_representer(dc, representerFactory(inner_tag))
            return dc
        return wrap
    
    ParserFactory_DC = TypeVar("ParserFactory_DC")
    def __call__(self, dc: ParserFactory_DC) -> _Parser[ParserFactory_DC]:
        """
        Create a parser for a specific dataclass

        :param dc:   Dataclass to parse as
        :returns:    Dataclass Parser
        """
        return _Parser(dc, loader=self.loader, dumper=self.dumper)
    
    def parse(self, path : Path) -> Any:
        """
        Parse a YAML file from disk and return any dataclass object it contains.

        :param path: Path to the YAML file to parse
        :returns:    Parsed dataclass object
        """
        return self(type).parse(path)

    def parse_str(self, data : str) -> Any:
        """
        Parse a YAML string and return any dataclass object it contains.

        :param data: YAML string
        :returns:    Parsed dataclass object
        """
        return self(type).parse_str(data)


SimpleParser_DC = TypeVar("SimpleParser_DC")
def SimpleParser(dc: SimpleParser_DC) -> _Parser[SimpleParser_DC]:
    """
    Create a parser for a specific dataclass
    """
    Parser = ParserFactory()
    Parser.register()(dc)
    return Parser(dc)
