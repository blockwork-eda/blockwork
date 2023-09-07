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

from typing import Any, Callable, Dict, Hashable, Optional, Type, Tuple, Union, cast

# NOTE: Credit to Andriy Ivaneyko for the singleton pattern used below
#       https://stackoverflow.com/questions/51896862/how-to-create-singleton-class-with-arguments-in-python

class Singleton(type):
    INSTANCES : Dict[Type, Any] = {}

    def __call__(cls, *args, **kwds) -> Any:
        if cls not in Singleton.INSTANCES:
            Singleton.INSTANCES[cls] = super(Singleton, cls).__call__(*args, **kwds)
        return Singleton.INSTANCES[cls]

class ParameterisedSingleton(type):
    INSTANCES : Dict[Tuple[Type, Union[str, int]], Any] = {}

    def __call__(cls, *args, **kwds) -> Any:
        uniq_key = (cls, *args, *(f"{k}={v}" for k, v in kwds.items()))
        if uniq_key not in ParameterisedSingleton.INSTANCES:
            ParameterisedSingleton.INSTANCES[uniq_key] = super(ParameterisedSingleton, cls).__call__(*args, **kwds)
        return ParameterisedSingleton.INSTANCES[uniq_key]


def keyed_singleton(arg_key: Optional[Callable[..., Hashable]]=None, 
                    inst_key: Optional[Callable[[Any], Hashable]]=None):
    "Factory for singletons which use a key function to uniquify/share"
    
    if (arg_key is None) == (inst_key is None):
        raise RuntimeError("Must specify arg_key or inst_key (but not both)")

    class FactoriedSingleton(type):
        INSTANCES = {}
        def __call__(cls, *args, **kwds):
            if inst_key:
                inst = super().__call__(*args, **kwds)
                k = inst_key(inst)
            else:
                inst = None
                k = cast(Callable, arg_key)(*args, **kwds)
            if k not in cls.INSTANCES:
                cls.INSTANCES[k] = inst or cls(*args, **kwds)
            return cls.INSTANCES[k]
    return FactoriedSingleton
