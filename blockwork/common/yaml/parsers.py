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
from typing import Any, Callable, Generic, Optional,  Self
from .converters import Converter, Registry, _Convertable, YamlConversionError
import yaml
try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader


class ObjectParser(Generic[_Convertable]):
    """Yaml parser for a specific type, created by ParserFactory"""
    def __init__(self, typ: type[_Convertable], loader: type[Loader], dumper: type[Dumper]):
        self.typ = typ
        self.loader = loader
        self.dumper = dumper

    def parse(self, path : Path) -> _Convertable:
        """
        Parse a YAML file from disk and return any dataclass object it contains.

        :param path: Path to the YAML file to parse
        :returns:    Parsed object
        """
        with path.open("r", encoding="utf-8") as fh:
            parsed: _Convertable = yaml.load(fh, Loader=self.loader)
        if not isinstance(parsed, self.typ):
            raise YamlConversionError(path, f"Expected {self.typ} object got {type(parsed).__name__}")
        return parsed

    def parse_str(self, data : str) -> _Convertable:
        """
        Parse a YAML string and return any dataclass object it contains.

        :param data: YAML string
        :returns:    Parsed object
        """
        parsed : _Convertable = yaml.load(data, Loader=self.loader)
        if not isinstance(parsed, self.typ):
            raise YamlConversionError("<unicode string>", f"Expected {self.typ} object got {type(parsed).__name__}")
        return parsed


class Parser:
    """
    Creates a parser from a registry of conversions from tag to object and back, for example::

        spacial_registry = Registry()
        
        @spacial_registry.register(DataclassConverter, tag="!coord")
        @dataclass
        class Coordinate:
            x: int
            y: int
        
        # Parse as specific type (validates the result is a coordinate)
        spacial_parser = Parser(spacial_registry)
        spacial_parser(Coordinate).parse_str(...)

        # Parse as any registered type
        spacial_parser.parse_str(...)

    """
    def __init__(self, registry: Optional[Registry]=None):
        class loader(Loader):
            ...
        class dumper(Dumper):
            ...

        self.loader = loader
        self.dumper = dumper

        if registry is not None:
            for tag, typ, Converter in registry:
                self.register(Converter, tag=tag)(typ)


    def register(self, Converter: type[Converter[_Convertable, Self]], *, tag: Optional[str]=None) -> Callable[[type[_Convertable]], type[_Convertable]]:
        """
        Register a object for parsing with this parser object.

        :param tag: The yaml tag to register as (!ClassName otherwise)
        """
        def wrap(typ: type[_Convertable]) -> type[_Convertable]:
            inner_tag = f"!{typ.__name__}" if tag is None else tag
            converter = Converter(tag=inner_tag, typ=typ, parser=self)
            self.loader.add_constructor(inner_tag, converter.construct)
            self.dumper.add_representer(typ, converter.represent)
            return typ
        return wrap

    def __call__(self, typ: type[_Convertable]) -> ObjectParser[_Convertable]:
        """
        Create a parser for a specific object

        :param dc:   object to parse as
        :returns:    object Parser
        """
        return ObjectParser(typ, loader=self.loader, dumper=self.dumper)
    
    def parse(self, path : Path) -> Any:
        """
        Parse a YAML file from disk and return any dataclass object it contains.

        :param path: Path to the YAML file to parse
        :returns:    Parsed dataclass object
        """
        return self(object).parse(path)

    def parse_str(self, data : str) -> Any:
        """
        Parse a YAML string and return any dataclass object it contains.

        :param data: YAML string
        :returns:    Parsed dataclass object
        """
        return self(object).parse_str(data)


def SimpleParser(typ: type[_Convertable], Converter: type[Converter[_Convertable, Parser]]) -> ObjectParser[_Convertable]:
    """
    Create a parser for a specific dataclass
    """
    parser = Parser()
    parser.register(Converter)(typ)
    return parser(typ)
