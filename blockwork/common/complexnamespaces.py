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

from typing import Generic, TypeVar

_NamespaceValue = TypeVar("_NamespaceValue")


class ComplexNamespace(Generic[_NamespaceValue]):
    """
    Typed version of types.SimpleNamespace with read and modify only options.
    """

    def __init__(
        self,
        *,
        _RO: bool = False,  # noqa: N803
        _MO: bool = False,  # noqa: N803
        **kwargs: _NamespaceValue,
    ):
        self.__dict__["RO"] = _RO
        self.__dict__["MO"] = _MO
        self.__dict__["ns"] = kwargs

    def __getattr__(self, name) -> _NamespaceValue:
        return self.ns[name]

    def __getitem__(self, name) -> _NamespaceValue:
        return self.ns[name]

    def __setattr__(self, name: str, value: _NamespaceValue) -> None:
        if self.RO:
            raise RuntimeError("Namespace is read only")
        if self.MO and name not in self.ns:
            raise RuntimeError(f"Namespace is modify only and {name} is not already present")
        self.ns[name] = value

    def __repr__(self):
        return f"namespace({', '.join(f'{k}={v}' for k,v in self.ns.items())})"

    def keys(self):
        yield from self.ns.keys()

    def values(self):
        yield from self.ns.values()

    def items(self):
        yield from self.ns.items()


class ReadonlyNamespace(ComplexNamespace[_NamespaceValue]):
    """
    Namespace where attributes cannot be added or modified post initialisation
    """

    def __init__(self, **kwargs: _NamespaceValue):
        self.__dict__["RO"] = True
        self.__dict__["MO"] = False
        self.__dict__["ns"] = kwargs
