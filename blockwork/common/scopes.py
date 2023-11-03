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

from typing import Callable, Generic, ParamSpec, Self, TypeVar


class ScopeError(RuntimeError):
    'Attempted to access scoped data outside of any scope'

_ScopedData = TypeVar('_ScopedData')
class _ScopeWrap(Generic[_ScopedData]):
    _stack: list[_ScopedData] = []
    def __init__(self, data: _ScopedData):
        self._data = data

    def __enter__(self):
        self._stack.append(self._data)
        return self._data

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stack.pop()

    @classmethod
    @property
    def current(cls) -> _ScopedData:
        try:
            return cls._stack[-1]
        except IndexError as e:
            raise ScopeError from e

class Scope:
    """
    Mixin class to provide scoping via a context manager 
    stack for data that may otherwise end up global. See example::

        @dataclass
        class Verbosity(Scope):
            VERBOSE: bool

        def do_something():
            if Verbosity.current().VERBOSE:
                ...
            else
                ...
            
        with Verbosity(VERBOSE=True):
            do_something()
    """
    _stack: list[Self] = []
    def __enter__(self):
        self._stack.append(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stack.pop()

    @classmethod
    @property
    def current(cls) -> Self:
        try:
            return cls._stack[-1]
        except IndexError as e:
            raise ScopeError from e


_Param = ParamSpec('_Param')
_Return = TypeVar('_Return')
def scope(wrapee: Callable[_Param, _Return]) -> Callable[_Param, _ScopeWrap[_Return]]:
    """
    Decorator intended to provide scoping via a context manager 
    stack for data that may otherwise end up global. See example::

        @scope
        @dataclass
        class Verbosity:
            VERBOSE: bool

        def do_something():
            if Verbosity.current().VERBOSE:
                ...
            else
                ...
            
        with Verbosity(VERBOSE=True):
            do_something()
    """
    class Scoped(_ScopeWrap[wrapee]):
        def __init__(self, *args: _Param.args, **kwargs: _Param.kwargs):
            self._data = wrapee(*args, **kwargs)
    return Scoped
