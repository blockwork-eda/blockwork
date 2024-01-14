# Copyright 2024, Blockwork, github.com/intuity/blockwork
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
"""
A utility module to help creating api objects which can be used to access
contextual data and utilities while under particular scopes.
"""
from typing import Any
from .scopes import Scope

class ApiAccessError(Exception):
    def __init__(self, api: str):
        super().__init__(f"Tried to access unavailable api `{api}` try creating a fork first. ")

class ScopedApi(Scope):
    '''
    Use as a base for a new api, for example::

        class NodeApi(ScopedApi):
            parent: str

        def some_func():
            api = NodeApi.current
            print(api.parent)

        with NodeApi(parent='me'):
            sume_func()
    '''
    def __init__(self, **apis: dict[str, Any]) -> None:
        self._apis = {k:api for k, api in apis.items() if api is not None}

    def __call__(self, fn):
        'Allow to be used as a decorator'
        def decorated(*args, **kwargs):
            with self:
                return fn(*args, **kwargs)
        return decorated
    
    def fork(self, **apis: dict[str, Any]):
        'Create a new api object from this one'
        new_apis = {**self._apis}
        for k, api in apis.items():
            if api is None:
                if k in new_apis:
                    del new_apis[k]
            else:
                new_apis[k] = api
        return type(self)(**new_apis)

    def __getattr__(self, key: str):
        if key in self:
            return self._apis[key]
        raise ApiAccessError(key)
    
    def __contains__(self, key: str):
        return key in self._apis
    
    def get(self, key: str, default: Any = None):
        return self._apis.get(key, default)
