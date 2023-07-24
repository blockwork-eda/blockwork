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
import logging
from types import SimpleNamespace
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple, Union

from ..common.registry import RegisteredMethod
from ..context import Context
from .entity import Entity
from .file import FileType
from ..tools import Tool, Invocation

class TransformError(Exception):
    pass

class TransformImpossible(Exception):
    pass

class Transform(RegisteredMethod):

    # Transform output root locator
    ROOT : Path = Path("/__transform_root__")

    def __init__(self, method : Callable) -> None:
        self.name = method.__name__
        self.method = method
        self.inputs : List[FileType] = []
        self.outputs : List[FileType] = []
        self.tools : List[Tool] = []

    def __repr__(self) -> str:
        return f"<Transform name='{self.name}'>"

    def add_input(self, ftype : FileType) -> None:
        self.inputs.append(ftype)

    def add_output(self, ftype : FileType) -> None:
        self.outputs.append(ftype)

    def add_tool(self, tool : Tool) -> None:
        self.tools.append(tool)

    def __call__(self,
                 ctx : Context,
                 entity : Entity,
                 inputs : Dict[FileType, Path]) -> Union[Invocation, Path]:
        # Determine working directory for this transform
        host_dirx = ctx.host_scratch / entity.name / self.name
        cntr_dirx = ctx.container_scratch / entity.name / self.name
        # Create namespace for tools
        tool_map = {}
        for tool_def in self.tools:
            tool = tool_def()
            tool_map[tool.name] = tool.default
        n_tools = SimpleNamespace(**tool_map)
        # Create namespace for inputs
        n_inputs = SimpleNamespace(**{ x.strip(".").replace(".", "_"): y for x, y in inputs.items() })
        # Invoke the transform
        yield from self.method(n_tools, n_inputs, host_dirx, cntr_dirx)

    @classmethod
    def tool(cls, tool : Tool) -> Callable:
        def _inner(func : Callable) -> Callable:
            tran = cls.wrap(func)
            tran.add_tool(tool)
            return func
        return _inner

    @classmethod
    def input(cls, ftype : Union[str, FileType]) -> Callable:
        ftype = ftype if isinstance(ftype, FileType) else FileType(ftype)
        def _inner(func : Callable) -> Callable:
            tran = cls.wrap(func)
            tran.add_input(ftype)
            return func
        return _inner

    @classmethod
    def output(cls, ftype : Union[str, FileType]) -> Callable:
        ftype = ftype if isinstance(ftype, FileType) else FileType(ftype)
        def _inner(func : Callable) -> Callable:
            tran = cls.wrap(func)
            tran.add_output(ftype)
            return func
        return _inner

    @classmethod
    @functools.lru_cache()
    def identify_chain(cls, from_type : FileType, to_type : FileType) -> List[Tuple[FileType, FileType, "Transform"]]:
        """
        Identify chain of transforms that can convert from any one type to any
        other type.

        :param from_type:   The existing type of the file
        :param to_type:     The desired type of the file
        :returns:           The chain of transformations required, each element
                            is a tuple of the matched input type, the matched
                            output type, and the transformation
        """
        logging.debug(f"Searching for transform chain from '{from_type.extension}' "
                      f"to '{to_type.extension}'")
        def _inner(from_type : FileType, to_type : FileType) -> Iterable[Tuple[FileType, FileType, Transform]]:
            # Identify transforms that support the input type
            for tran in filter(lambda x: from_type in x.inputs,
                            Transform.get_all().values()):
                # If this transform reaches the desired output, yield immediately
                if to_type in tran.outputs:
                    logging.debug(f"Transform '{tran.name}' matches on input type "
                                  f"'{from_type.extension}' and output type "
                                  f"'{to_type.extension}'")
                    yield from_type, to_type, tran
                    break
                # Otherwise, recurse to see if another step can help?
                for out_ftype in tran.outputs:
                    try:
                        yield from Transform.identify_chain(out_ftype, to_type)
                        break
                    except TransformImpossible:
                        continue
                else:
                    logging.debug(f"Transform '{tran.name}' matches input type "
                                  f"'{from_type.extension}' but cannot achieve "
                                  f"output type '{to_type.extension}'")
            # If we search without success, raise error
            else:
                raise TransformError(f"Cannot identify transform chain between "
                                     f"'{from_type.extension}' and '{to_type.extension}'")
        return list(_inner(from_type, to_type))
