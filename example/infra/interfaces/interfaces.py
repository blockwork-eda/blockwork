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

from blockwork.transforms import IFace
from blockwork.common.complexnamespaces import ReadonlyNamespace


class DesignInterface(IFace):
    def __init__(self, sources: Iterable[Path], headers: Iterable[Path]) -> None:
        self.sources = sources
        self.headers = headers

    def resolve(self):
        return {
            "sources": list(self.sources),
            "headers": list(self.headers),
        }
