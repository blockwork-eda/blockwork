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
from typing import Generic, Literal, TypeVar, Callable, cast, Self, Any, dataclass_transform
import warnings

import typeguard


class FieldError(TypeError):
    "Dataclass field validation error"

    def __init__(self, msg: str, field: str):
        self.msg = msg
        self.field = field

    def __str__(self):
        return self.msg


F = TypeVar('F', bound=Callable[..., Any])
class copy_signature(Generic[F]):
    def __init__(self, target: F) -> None: ...
    def __call__(self, wrapped: Callable[..., Any]) -> F:
        return cast(F, wrapped)


DCLS = TypeVar("DCLS")

def _dataclass_inner(cls: DCLS) -> DCLS:
    "Subclasses a dataclass, adding checking after initialisation."
    orig_init = cls.__init__

    # Replacement init function calls original, then runs checks
    def _dc_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)

        # Check each field has the expected type
        for field in dataclasses.fields(cls):
            value = getattr(self, field.name)
            with warnings.catch_warnings():
                # Catches a warning when typegaurd can't resolve a string type
                # definition to an actual type meaning it can't check the type.
                # This isn't ideal, but as far as @ed.kotarski can tell there
                # is no way round this limitation in user code meaning the
                # warning is just noise.
                warnings.simplefilter("ignore", category=typeguard.TypeHintWarning)
                try:
                    typeguard.check_type(value, field.type)
                except typeguard.TypeCheckError as ex:
                    raise FieldError(str(ex), field.name) from None
            if isinstance(field, Field):
                field.run_checks(value)

    cls.__init__ = _dc_init
    return cls



class Field(dataclasses.Field):
    "Checked version of Field. See field."

    checkers: list[Callable[[Self, Any], None]]

    def check(self, checker: Callable[[Any], None]):
        """
        Register a checking function for this field.
        Intended for use as a decorator.
        Returns the checker function so it is chainable.
        """
        self.checkers = getattr(self, "checkers", [])
        self.checkers.append(checker)
        return checker

    def run_checks(self, value):
        for checker in getattr(self, "checkers", []):
            try:
                checker(self, value)
            except TypeError as ex:
                raise FieldError(str(ex), self.name) from None

T_Field = TypeVar('T_Field')
def field(
    *,
    default: T_Field | Literal[dataclasses.MISSING] = dataclasses.MISSING,
    default_factory: Callable[[], T_Field] | Literal[dataclasses.MISSING]=dataclasses.MISSING,
    init=True,
    repr=True,  # noqa: A002
    hash=None,  # noqa: A002
    compare=True,
    metadata=None,
    kw_only=dataclasses.MISSING,
) -> T_Field:
    """
    Checked version of field which allows addictional checking functions to be
    registered to a field. Checking functions should raise type errors if the
    field value is not valid. For example:

        @dataclass
        class Location:
            path: str = field()
            column: int
            line: int

            @path.check
            def absPath(value):
                if not value.startswith("/"):
                    raise TypeError("Expected absolute path")

    """
    if default is not dataclasses.MISSING and default_factory is not dataclasses.MISSING:
        raise ValueError("cannot specify both default and default_factory")
    return cast(T_Field, Field(default, default_factory, init, repr, hash, compare, metadata, kw_only))


@copy_signature(dataclasses.dataclass)
@dataclass_transform(kw_only_default=True, frozen_default=True, eq_default=False, field_specifiers=(field,))
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
