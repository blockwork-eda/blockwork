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
import logging
import sys
from pathlib import Path
from typing import Callable, List

from .context import Context

class Bootstrap:
    """ Collects bootstrapping routines together """
    REGISTERED = []

    @classmethod
    def setup(cls, root : Path, paths : List[str]) -> None:
        """
        Import Python modules carrying bootstrapping methods from a list of
        module paths that are either system wide or relative to a given root
        path.

        :param root:    Root path under which Python modules are defined, this is
                        added to the PYTHONPATH prior to discovery
        :param paths:   Python module names to import from
        """
        if root.absolute().as_posix() not in sys.path:
            sys.path.append(root.absolute().as_posix())
        for path in paths:
            num_reg = len(cls.REGISTERED)
            importlib.import_module(path)
            if len(cls.REGISTERED) == num_reg:
                raise Exception(f"No bootstrap methods registered by '{path}'")

    @classmethod
    def register(cls, method : Callable) -> None:
        """
        Register a method as a bootstrapping stage. The method must accept only
        a single argument of the Context object for the project.

        :param method:  The method to register
        """
        # Avoid registering a bootstrapping method twice. Use this rather than
        # a set to still guarantee ordering.
        if method not in cls.REGISTERED:
            cls.REGISTERED.append(method)

    @classmethod
    def invoke(cls, context : Context) -> None:
        for method in cls.REGISTERED:
            logging.info(f"Running bootstrap step '{method.__module__}."
                         f"{method.__qualname__}'")
            method(context)
