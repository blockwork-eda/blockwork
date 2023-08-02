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

import functools
import inspect
from pathlib import Path
from typing import List, Optional

from ..common.registry import RegisteredClass
from ..common.singleton import Singleton

class Entity(RegisteredClass, metaclass=Singleton):
    """ Base class for project entities """

    # Entity root locator
    ROOT : Path = Path("/__entity_root__")

    # Placeholders
    files : Optional[List[Path]] = None

    def __init__(self) -> None:
        self.files = self.files or []

    @property
    def name(self) -> str:
        return type(self).__name__

    @property
    @functools.lru_cache()
    def root_path(self) -> Path:
        return Path(inspect.getfile(self.__class__)).parent

    def get_host_files(self) -> List[Path]:
        return [(self.root_path / x.relative_to(Entity.ROOT)) for x in self.files]
