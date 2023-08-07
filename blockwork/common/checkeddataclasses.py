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

import dataclasses
import typeguard
import typing

class FieldError(TypeError):
    "Dataclass field validation error"
    def __init__(self, msg: str, field: str):
        self.msg = msg
        self.field = field

    def __str__(self):
        return self.msg


CTP = typing.ParamSpec('CTP')
CTR = typing.TypeVar('CTR')
def _copytypes(_frm: typing.Callable[CTP, CTR]):
    'Utility to copy the parameter types and return from one function to another'
    def wrap(to) -> typing.Callable[CTP, CTR]:
        return typing.cast(typing.Callable[CTP, CTR], to)
    return wrap

DCLS = typing.TypeVar("DCLS")
def _dataclass_inner(cls: DCLS) -> DCLS:
    "Subclasses a dataclass, adding checking after initialisation."

    # Replacement init function calls original, then runs checks
    def __init__(self, *args, **kwargs):
        cls.__init__(self, *args, **kwargs)

        # Check each field has the expected type
        for field in dataclasses.fields(cls):
            value = getattr(self, field.name)
            try:
                typeguard.check_type(value, field.type)
            except typeguard.TypeCheckError as ex:
                raise FieldError(str(ex), field.name) from None
            if isinstance(field, Field):
                field.run_checks(value)

    return type(cls.__name__, (cls,), {"__init__": __init__})

@_copytypes(dataclasses.dataclass)
def dataclass(__cls=None, /, **kwargs):
    "Checked version of the dataclass decorator which adds runtime type checking."
    if __cls is None:
        def wrap(cls):
            dc = dataclasses.dataclass(**kwargs)(cls)
            return _dataclass_inner(dc)
        return wrap
    else:
        dc = dataclasses.dataclass()(__cls)
        return _dataclass_inner(dc)
    

class Field(dataclasses.Field):
    "Checked version of Field. See field."
    checkers: list[typing.Callable[[typing.Self, typing.Any], None]]

    def check(self, checker: typing.Callable[[typing.Any], None]):
        """
        Register a checking function for this field. 
        Intended for use as a decorator. 
        Returns the checker function so it is chainable.
        """
        self.checkers = getattr(self, 'checkers', [])
        self.checkers.append(checker)
        return checker
    
    def run_checks(self, value):
        for checker in getattr(self, 'checkers', []):
            try:
                checker(self, value)
            except TypeError as ex:
                raise FieldError(str(ex), self.name) from None


def field(*, default=dataclasses.MISSING, default_factory=dataclasses.MISSING, init=True, repr=True,
          hash=None, compare=True, metadata=None, kw_only=dataclasses.MISSING):
    """
    Checked version of field which allows addictional checking functions to be registered to a field.
    Checking functions should raise type errors if the field value is not valid. For example::
    
        @dataclass
        class Location:
            path: str = field()
            column: int
            line: int

            @path.check
            def absPath(value):
                if not value.startswith('/'):
                    raise TypeError("Expected absolute path")

    """
    if default is not dataclasses.MISSING and default_factory is not dataclasses.MISSING:
        raise ValueError('cannot specify both default and default_factory')
    return Field(default, default_factory, init, repr, hash, compare,
                 metadata, kw_only)