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

import logging
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path

from ..common.registry import RegisteredMethod
from ..context import Context


class BwBootstrapMode(StrEnum):
    default = auto()
    "Default behaviour"
    force = auto()
    "Rerun steps even when they are in-date"


class Bootstrap(RegisteredMethod):
    """
    Defines a single bootstrapping step to perform when setting up the workspace
    """

    def __init__(self, method: Callable) -> None:
        self.method = method
        self.full_path = method.__module__ + "." + method.__qualname__
        self.checkpoints: list[Path] = []

    def add_checkpoint(self, path: Path) -> None:
        self.checkpoints.append(path)

    @property
    def id(self) -> str:
        return self.full_path.replace(".", "__")

    def __call__(self, context: Context, mode: BwBootstrapMode = BwBootstrapMode.default) -> None:
        """
        Wrap the call to the bootstrapping method with handling to track when
        the step was last run, and whether it needs to be re-run based on its
        checkpoint paths alone.

        :param context: The context object
        :param mode:    Modifier for when build steps should be considered invalid
        """
        # When 'forcing' bootstrap to re-run, set the datestamp to the earliest ever date
        if mode == BwBootstrapMode.force:
            last_run = datetime.min
        # Otherwise, attempt to read the date back from the context
        else:
            raw = context.state.bootstrap.get(self.id, 0)
            last_run = datetime.fromisoformat(raw) if raw else datetime.min
        # Evaluate checkpoints
        if self.checkpoints:
            expired = False
            for chk in self.checkpoints:
                chk_path = context.host_root / chk
                if (
                    chk_path.exists()
                    and datetime.fromtimestamp(chk_path.stat().st_mtime) <= last_run
                ):
                    logging.debug(
                        f"Bootstrap step '{self.full_path}' checkpoint "
                        f"'{chk_path}' is up-to-date"
                    )
                else:
                    logging.debug(
                        f"Bootstrap step '{self.full_path}' checkpoint "
                        f"'{chk_path}' has been updated"
                    )
                    expired = True
            if not expired:
                logging.info(
                    f"Bootstrap step '{self.full_path}' is already up "
                    f"to date (based on checkpoints)"
                )
                return
        # Run the bootstrapping function
        logging.debug(f"Evaluating bootstrap step '{self.full_path}'")
        if self.method(context=context, last_run=last_run) is True:
            logging.info(
                f"Bootstrap step '{self.full_path}' is already up " f"to date (based on method)"
            )
        else:
            logging.info(f"Ran bootstrap step '{self.full_path}'")
            context.state.bootstrap.set(self.id, datetime.now().isoformat())

    @classmethod
    def checkpoint(cls, path: Path) -> Callable:
        def _inner(func: Callable) -> Callable:
            boot = cls.wrap(func)
            boot.add_checkpoint(path)
            return func

        return _inner

    @classmethod
    def evaluate_all(
        cls, context: Context, mode: BwBootstrapMode = BwBootstrapMode.default
    ) -> None:
        """
        Evaluate all of the registered bootstrap methods, checking to see whether
        they are out-of-date based on their 'check_point' before executing them.

        :param context: The context object of the current session
        :param mode:    Modifier for when build steps should be considered invalid
        """
        for step in cls.get_all().values():
            step(context, mode)
