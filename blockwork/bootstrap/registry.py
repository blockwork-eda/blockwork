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
import importlib
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from ..context import Context

@dataclasses.dataclass
class BootstrapStep:
    full_path   : str
    method      : Callable
    check_point : Optional[Path]

    @property
    def id(self) -> str:
        return self.full_path.replace(".", "__")


class Bootstrap:
    """ Collects bootstrapping routines together """
    REGISTERED : Dict[str, BootstrapStep] = {}

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
            importlib.import_module(path)

    @classmethod
    def register(cls, check_point : Optional[Union[str, Path]] = None) -> None:
        """
        Register a method as a bootstrapping step, with an optional touch point
        which will be used to determine if the step is out-of-date and needs to
        be re-run. The bootstrap method must accept two arguments - the first
        called 'context' which will carry an instance of Context, and the second
        called 'last_run' which will be an instance of datetime carrying the last
        date the step was run. The bootstrap method should return a boolean value
        to indicate whether it was already up-to-date - True indicates no actions
        needed to be run, False indicates it was out-of-date and some actions
        were performed.

        :param check_point: Optional file path to use when determining if the
                            step is out-of-date
        :returns:           The inner decorating method
        """
        def _inner(method : Callable) -> None:
            step = BootstrapStep(method.__module__ + "." + method.__qualname__,
                                 method,
                                 Path(check_point) if check_point else None)
            # Avoid registering a bootstrapping method twice, Python dictionaries
            # maintain order so this will run steps in the order of declaration.
            if step.id not in cls.REGISTERED:
                cls.REGISTERED[step.id] = step
            return method
        return _inner

    @classmethod
    def invoke(cls, context : Context) -> None:
        """
        Evaluate all of the registered bootstrap methods, checking to see whether
        they are out-of-date based on their 'check_point' before executing them.

        :param context: The context object of the current session
        """
        tracking = context.state.bootstrap
        for step in cls.REGISTERED.values():
            raw      = tracking.get(step.id, 0)
            last_run = datetime.fromisoformat(raw) if raw else datetime.min
            if step.check_point:
                chk_point = context.host_root / step.check_point
                if (chk_point.exists() and
                    datetime.fromtimestamp(chk_point.stat().st_mtime) <= last_run):
                    logging.info(f"Bootstrap step '{step.full_path}' is already up to date (based on checkpoint)")
                    continue
            if step.method(context=context, last_run=last_run) is True:
                logging.info(f"Bootstrap step '{step.full_path}' is already up to date (based on method)")
            else:
                logging.info(f"Ran bootstrap step '{step.full_path}'")
                tracking.set(step.id, datetime.now().isoformat())
