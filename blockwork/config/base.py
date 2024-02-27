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

from collections.abc import Iterable
from typing import dataclass_transform

import yaml

from ..build.transform import Transform
from ..common.checkeddataclasses import dataclass, field
from ..common.singleton import keyed_singleton
from ..common.yaml import DataclassConverter
from ..common.yaml.parsers import Parser
from .api import ConfigApi


class ConfigConverter(DataclassConverter["Config", "Parser"]):
    def construct_scalar(self, loader: yaml.Loader, node: yaml.ScalarNode) -> "Config":
        # Allow elements to be indirected with a path e.g. `!<element> [<unit>.<path>]`
        target = loader.construct_scalar(node)
        if not isinstance(target, str):
            raise RuntimeError
        with ConfigApi.current.with_target(target, self.typ) as api:
            return api.target.config

    def construct_mapping(self, loader: yaml.Loader, node: yaml.MappingNode) -> "Config":
        with ConfigApi.current.with_node(node):
            return super().construct_mapping(loader, node)


@dataclass_transform(
    kw_only_default=True, frozen_default=True, eq_default=False, field_specifiers=(field,)
)
class Config(metaclass=keyed_singleton(inst_key=lambda i: hash(i))):
    """
    Base class for all config.
    All-caps keys are reserved.
    """

    "Defines which YAML registry the config belongs to i.e. site/project/element"
    # _CONVERTER: type[DataclassConverter] = DataclassConverter
    _CONVERTER = ConfigConverter
    "Defines how to convert the YAML tag into a Python object"
    YAML_TAG: str | None = None
    "The !<Tag> to represent this document in YAML"
    FILE_NAME: str | None = None
    "The api object for this config"
    api: ConfigApi
    "The parser for this config"
    parser: Parser = Parser()
    """The implicit file name to use when one isn't provided,
       defaults to YAML_TAG if provided, else class name"""

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        cls.api = field(default_factory=lambda: ConfigApi.current)
        # Ensure that even if no annotations existed before, that the class is
        # well behaved as this caused a bug under Python 3.11.7
        if not hasattr(cls, "__annotations__"):
            cls.__annotations__ = {}
        if "__annotations__" not in cls.__dict__:
            setattr(cls, "__annotations__", cls.__annotations__)  # noqa: B010
        # Force an annotation for 'api'
        cls.__annotations__["api"] = ConfigApi
        dataclass(kw_only=True, frozen=True, eq=False, repr=False)(cls)
        cls.parser.register(cls._CONVERTER, tag=cls.YAML_TAG)(cls)

    def __init__(self, *args, **kwargs):
        ...

    def __hash__(self):
        return self.api.node_id() or id(self)

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
    "Base class for site configuration"

    projects: dict[str, str]


class Project(Config):
    "Base class for project configuration"

    units: dict[str, str]
