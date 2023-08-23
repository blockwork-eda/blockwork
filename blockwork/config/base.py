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
from typing import Any, Iterable, Optional, Protocol, overload
from blockwork.common.checkeddataclasses import dataclass

class _Resolver(Protocol):
    'Takes a path or list of paths and returns a path or list of paths (respectively)'
    @overload
    def __call__(self, paths: list[str]) -> list[str]: ...
    @overload
    def __call__(self, paths: str) -> str: ...
    def __call__(self, paths) -> Any: ...

@dataclass(kw_only=True)
class Site:
    'Base class for site configuration'
    projects: dict[str, str]

@dataclass(kw_only=True)
class Project:
    'Base class for project configuration'
    units: dict[str, str]


@dataclass(kw_only=True)
class ElementContext:
    'Context object bound on to each element to keep track of where it came from'
    unit: str
    config: Path

@dataclass(kw_only=True)
class Element:
    'Base class for element configuration'
    _context: Optional[ElementContext] = None

    def iter_sub_elements(self) -> Iterable["Element"]:
        '''
        Yields any sub-elements which are used as part of this one.

        Implementation notes:
            - This function must be implemented when sub-elements are used.
        '''
        yield from []

    def resolve_input_paths(self, resolver: _Resolver):
        '''
        Resolves relative 'input' paths specified in the config to absolute ones based 
        on the resolver argument. Where input paths are paths which reference either
        static paths from the repository, or paths which refer to files which are output 
        from transforms.
        
        The resolver is expected to take a relative path and return an absolute path.

        Implementation notes:
            - This function must be implemented when config specifies paths to static
              or generated files.
            - The element is expected to patch itself with the output of the resolver
              for each path, for example::
              
            self.a_path = resolver(self.a_path)

        '''
        pass

@dataclass(kw_only=True)
class Transform(Element):
    'Base class for transforms'

    def resolve_output_paths(self, resolver: _Resolver):
        '''
        Resolves relative 'output' paths specified in the config to absolute ones based 
        on the resolver argument. Where output paths are absolute paths which can be 
        generated based on the transform inputs.

        The resolver is expected to take a relative path and return an absolute path.

        Implementation notes:
            - This function must be implemented when config transforms are used to
              create files.
            - The element is expected to patch itself with the output of the resolver
              for each path, for example::
              
            self.a_path = resolver(self.a_path)

        '''
        pass
