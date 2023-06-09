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

import yaml
try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader


class ConfigBase(yaml.YAMLObject):
    yaml_tag    = "!unset"
    yaml_loader = Loader
    yaml_dumper = Dumper

    @classmethod
    def from_yaml(cls, loader : Loader, node : yaml.Node) -> "ConfigBase":
        if isinstance(node, yaml.nodes.MappingNode):
            return cls(**loader.construct_mapping(node, deep=True))
        else:
            return cls(*loader.construct_sequence(node))

    def check(self) -> None:
        pass


class ConfigError(Exception):
    """ Custom exception type for syntax errors in configurations """

    def __init__(self, obj : ConfigBase, field : str, msg : str) -> None:
        super().__init__(msg)
        self.obj = obj
        self.field = field


class Config:
    """ Methods to parse and dump YAML configuration objects """

    @staticmethod
    def parse(path : Path) -> ConfigBase:
        """
        Parse a YAML file from disk and return any config object it contains.

        :param path: Path to the YAML file to parse
        :returns:    Parsed config object
        """
        with path.open("r", encoding="utf-8") as fh:
            parsed : ConfigBase = yaml.load(fh, Loader=Loader)
        if isinstance(parsed, ConfigBase):
            parsed.check()
        return parsed

    @staticmethod
    def parse_str(data : str) -> ConfigBase:
        """
        Parse a YAML string and return any config object it contains.

        :param data: YAML string
        :returns:    Parsed config object
        """
        parsed : ConfigBase = yaml.load(data, Loader=Loader)
        if isinstance(parsed, ConfigBase):
            parsed.check()
        return parsed

    @staticmethod
    def dump(object : ConfigBase) -> str:
        """
        Dump a config object into a YAML string

        :param object: Config object to dump
        :returns:      YAML string representation
        """
        return yaml.dump(object, Dumper=Dumper)
