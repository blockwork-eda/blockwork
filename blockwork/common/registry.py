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
from pathlib import Path
from typing import Any, Callable, Dict, List, Type

class RegistryError(Exception):
    pass


class Registry:
    LOOKUP_BY_NAME : Dict[Type, Dict[str, "RegisteredMethod"]] = defaultdict(lambda: {})
    LOOKUP_BY_OBJ  : Dict[Type, Dict[Callable, "RegisteredMethod"]] = defaultdict(lambda: {})

    @classmethod
    def setup(cls, root : Path, paths : List[str]) -> None:
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
    def wrap(cls, obj : Any) -> Any:
        del obj
        raise NotImplementedError("The 'wrap' method must be implemented by an "
                                  "inheriting registry type")

    @classmethod
    def register(cls, *_args, **_kwds) -> Any:
        def _inner(obj : Any) -> Any:
            cls.wrap(obj)
            return obj
        return _inner

    @classmethod
    def get_all(cls) -> Dict[str, "RegisteredMethod"]:
        return RegisteredMethod.LOOKUP_BY_NAME[cls]

    @classmethod
    def get_by_name(cls, name : str) -> "RegisteredMethod":
        base = RegisteredMethod.LOOKUP_BY_NAME[cls]
        if name not in base:
            raise RegistryError(f"Unknown {cls.__name__.lower()} for '{name}'")
        return base[name]

    @classmethod
    def clear_registry(cls) -> None:
        """ Clear all existing registrations for this registry """
        RegisteredMethod.LOOKUP_BY_NAME[cls] = {}
        RegisteredMethod.LOOKUP_BY_OBJ[cls] = {}


class RegisteredMethod(Registry):
    """
    Provides registry behaviours for an object type. A decorator is provided
    `@RegisteredMethod.register()` to associate an object with the registry.
    """

    @classmethod
    def wrap(cls, obj : Callable) -> Callable:
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
    def wrap(cls, obj : Type) -> Type:
        if obj in RegisteredClass.LOOKUP_BY_OBJ[cls]:
            return obj
        else:
            RegisteredClass.LOOKUP_BY_NAME[cls][obj.__name__] = obj
            RegisteredClass.LOOKUP_BY_OBJ[cls][obj] = obj
            return obj
