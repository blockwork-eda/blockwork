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

from ..common.checkeddataclasses import dataclass, field
from ..common.yaml import ConverterRegistry, DataclassConverter, Parser

_registry = ConverterRegistry()


@_registry.register(DataclassConverter, tag="!Cache")
@dataclass
class CacheConfig:
    name: str
    path: str
    max_size: str | None = None
    fetch_condition: bool | str = False
    store_condition: bool | str = False
    check_determinism: bool = True


@_registry.register(DataclassConverter, tag="!Caching")
@dataclass
class CachingConfig:
    enabled: bool = True
    targets: bool = False
    expect: bool = False
    trace: bool = False
    caches: list[CacheConfig] = field(default_factory=list)


CachingParser = Parser(_registry)(CachingConfig)
