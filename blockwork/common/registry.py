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

import importlib
import sys
from collections import defaultdict
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ClassVar, TypeVar

_RegObj = TypeVar("_RegObj")


class RegistryError(Exception):
    pass


class Registry:
    LOOKUP_BY_NAME: ClassVar[dict[type, dict[str, "RegisteredMethod"]]] = defaultdict(lambda: {})
    LOOKUP_BY_OBJ: ClassVar[dict[type, dict[Callable, "RegisteredMethod"]]] = defaultdict(
        lambda: {}
    )

    @staticmethod
    def setup(root: Path, paths: list[str]) -> None:
        """
        Import Python modules that register objects of this type from a list of
        module paths that are either system wide or relative to a given root path.

        :param root:    Root path under which Python modules are defined, this is
                        added to the PYTHONPATH prior to discovery
        :param paths:   Python module names to import from
        """
        if root.absolute().as_posix() not in sys.path:
            sys.path.append(root.absolute().as_posix())
        for path in paths:
            importlib.import_module(path)

    @classmethod
    def wrap(cls, obj: Any) -> Any:
        del obj
        raise NotImplementedError(
            "The 'wrap' method must be implemented by an " "inheriting registry type"
        )

    @classmethod
    def register(cls, *_args, **_kwds) -> Callable[[_RegObj], _RegObj]:
        def _inner(obj: _RegObj) -> _RegObj:
            cls.wrap(obj)
            return obj

        return _inner

    @classmethod
    def get_all(cls) -> dict[str, "RegisteredMethod"]:
        return RegisteredMethod.LOOKUP_BY_NAME[cls]

    @classmethod
    def get_by_name(cls, name: str) -> "RegisteredMethod":
        base = RegisteredMethod.LOOKUP_BY_NAME[cls]
        if name not in base:
            raise RegistryError(f"Unknown {cls.__name__.lower()} for '{name}'")
        return base[name]

    @classmethod
    @contextmanager
    def temp_registry(cls):
        """Context managed temporary registry for use in tests"""
        lookup_by_name = RegisteredMethod.LOOKUP_BY_NAME[cls]
        lookup_by_obj = RegisteredMethod.LOOKUP_BY_OBJ[cls]
        RegisteredMethod.LOOKUP_BY_NAME[cls] = defaultdict(lambda: {})
        RegisteredMethod.LOOKUP_BY_OBJ[cls] = defaultdict(lambda: {})
        try:
            yield None
        finally:
            RegisteredMethod.LOOKUP_BY_NAME[cls] = lookup_by_name
            RegisteredMethod.LOOKUP_BY_OBJ[cls] = lookup_by_obj

    @classmethod
    def clear_registry(cls) -> None:
        """Clear all existing registrations for this registry"""
        RegisteredMethod.LOOKUP_BY_NAME[cls] = {}
        RegisteredMethod.LOOKUP_BY_OBJ[cls] = {}


class RegisteredMethod(Registry):
    """
    Provides registry behaviours for an object type. A decorator is provided
    `@RegisteredMethod.register()` to associate an object with the registry.
    """

    @classmethod
    def wrap(cls, obj: Callable) -> Callable:
        if obj in Registry.LOOKUP_BY_OBJ[cls]:
            return Registry.LOOKUP_BY_OBJ[cls][obj]
        else:
            wrp = cls(obj)
            Registry.LOOKUP_BY_NAME[cls][obj.__name__] = wrp
            Registry.LOOKUP_BY_OBJ[cls][obj] = wrp
            return wrp


class RegisteredClass(Registry):
    """
    Provides registry behaviours for an object type. A decorator is provided
    `@RegisteredClass.register()` to associate an object with the registry.
    """

    @classmethod
    def wrap(cls, obj: type) -> type:
        if obj in RegisteredClass.LOOKUP_BY_OBJ[cls]:
            return obj
        else:
            RegisteredClass.LOOKUP_BY_NAME[cls][obj.__name__] = obj
            RegisteredClass.LOOKUP_BY_OBJ[cls][obj] = obj
            return obj
