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
from pathlib import Path

from blockwork.transforms import EnvPolicy, IEnv, IFace


class DesignInterface(IFace):
    sources: Iterable[Path] = IFace.FIELD(default_factory=list)
    headers: Iterable[Path] = IFace.FIELD(default_factory=list)

    def resolve(self):
        return {
            "sources": list(self.sources),
            "headers": list(self.headers),
        }


class PythonInterface(IFace):
    modules: Iterable[Path] = IFace.FIELD(default_factory=list)

    def resolve(self):
        return [[IEnv("PYTHONPATH", list(self.modules), policy=EnvPolicy.APPEND)]]
