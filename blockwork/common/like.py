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

from typing import Any, Callable, Generic, TypeVar

_LikeType = TypeVar("_LikeType")
_FrmType = TypeVar("_FrmType")
_ToType = TypeVar("_ToType")
class LikeMetaType(type):
    _converters: dict[tuple[Any, Any], Callable[[Any], Any]] = {}

    def __instancecheck__(cls, inst):
        """
        We use this to allow isinstance checks to pass when a suitable 
        converter exists.
        """
        try:
            if isinstance(inst, cls.typ):
                return True
        except TypeError:
            pass
        key = (inst.__class__, cls.typ)
        return key in cls._converters

    def __getitem__(self, typ: _LikeType) -> "Like[_LikeType]":
        """
        We use this to make Like behave like a generic, while getting the
        type information as a value. If we don't do this we can't retrieve 
        the type information when we get to __instancecheck__.
        """
        # if not isinstance(typ, type):
            # raise RuntimeError(f"Like can only be used for types, but got {typ}")
        return type("LikeType", (Like,), {"typ": typ})

    def converter(self, frm: _FrmType, to:_ToType | None = None)\
            -> Callable[[Callable[[_FrmType], _ToType]], Callable[[_FrmType], _ToType]]:
        """
        Register a converter from one type to another. Allows casting using
        `Like[to_type](from_type)`.
        """
        if to is None:
            if self.typ is None:
                raise RuntimeError(
                    "Can't infer conversion type, either call using "
                    "`@Like[<to_type>]converter(<from_type>)` or using "
                    "`@Like.converter(<from_type>, <to_type>)`"
                )
            to = self.typ
        def inner(fn: Callable[[_FrmType], _ToType]) -> Callable[[_FrmType], _ToType]:
            self._converters[(frm, to)] = fn
            return fn
        return inner

class Like(Generic[_LikeType], metaclass=LikeMetaType):
    """
    Use to create flexible type checked interfaces where values can
    be coerced so long as a converter has been registered. See example::

        @Like[str].converter(int)
        def int_to_str(num):
            return str(num)
        
        assert Like[str](4) == str(4)
        assert isinstance(4, Like[str])
        assert isinstance('hi', Like[str])
    """
    typ: _LikeType = None

    def __new__(cls, inst) -> _LikeType: 
        """
        Cast the argument to the type it's like.
        """
        try:
            if isinstance(inst, cls.typ):
                return inst
        except TypeError:
            pass
        key = (inst.__class__, cls.typ)
        return cls._converters[key](inst)
