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
from pathlib import Path
from blockwork.common.registry import RegisteredClass
from blockwork.common.singleton import Singleton
from blockwork.config import base, Config


class Workflow(RegisteredClass, metaclass=Singleton):
    """ Base class for workflows """

    # Tool root locator
    ROOT : Path = Path("/__tool_root__")

    # Config types this workflow uses
    SITE_TYPE = base.Site
    PROJECT_TYPE = base.Project
    TARGET_TYPE = base.Element

    def __init__(self, config: Config) -> None:
        self.config = config
        # Resolve input and output paths
        self.config.resolve()

    def exec(self):
        'Run the workflow'
        raise NotImplementedError

    @classmethod
    @property
    @functools.lru_cache()
    def name(cls) -> str:
        return cls.__name__.lower()

    # ==========================================================================
    # Registry Handling
    # ==========================================================================

    @classmethod
    def wrap(cls, workflow : "Workflow") -> "Workflow":
        if workflow in RegisteredClass.LOOKUP_BY_OBJ[cls]:
            return workflow
        else:
            RegisteredClass.LOOKUP_BY_NAME[cls][workflow.name] = workflow
            RegisteredClass.LOOKUP_BY_OBJ[cls][workflow] = workflow
            return workflow
