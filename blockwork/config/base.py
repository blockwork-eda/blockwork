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
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from ..context import Context
from ..build.interface import FileInterface
from ..build.transform import Transform

from ..common.checkeddataclasses import dataclass
from dataclasses import dataclass as unchecked_dataclass


@dataclass(kw_only=True)
class Site:
    'Base class for site configuration'
    projects: dict[str, str]

@dataclass(kw_only=True)
class Project:
    'Base class for project configuration'
    units: dict[str, str]


@unchecked_dataclass(kw_only=True)
class ElementContext:
    'Context object bound on to each element to keep track of where it came from'
    unit: str
    config: Path
    unit_project_path: Path
    unit_scratch_path: Path


class ElementFileInterface(FileInterface):
    """
    File interface for config elements
    """
    def __init__(self, element: "Element", path: str) -> None:
        self.element = element
        self.path = Path(path)

    def keys(self):
        yield (self.element._context.unit, self.path)
    
    def resolve_output(self, ctx: "Context"):
        return (self.element._context.unit_scratch_path / self.transform.id() / self.path)
    
    def resolve_input(self, ctx: "Context"):
        return (self.element._context.unit_project_path / self.path)


@dataclass(kw_only=True)
class Element:
    "Base class for element configuration"
    _context: ElementContext

    def iter_sub_elements(self) -> Iterable["Element"]:
        """
        Yields any sub-elements which are used as part of this one.

        Implementation notes:
            - This function must be implemented when sub-elements are used.
        """
        yield from []

    def iter_transforms(self) -> Iterable[Transform]:
        """
        Yields any transforms from this element.
        """
        yield from []

    def file_interface(self, path):
        """
        Utility method to to create a fileinterface for this element.
        """
        return ElementFileInterface(self, path)
