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

import atexit
import json
from pathlib import Path


class StateFile:

    def __init__(self, path : Path) -> None:
        self.__path = path
        self.__data = {}
        self.load()

    def load(self) -> None:
        if self.__path.exists():
            with self.__path.open("r", encoding="utf-8") as fh:
                self.__data = json.load(fh)

    def store(self) -> None:
        with self.__path.open("w", encoding="utf-8") as fh:
            json.dump(fh, self.__data)

class State:
    """
    Manages the state tracking folder for the project

    :param location:    Absolute path to the state folder
    """

    def __init__(self, location : Path) -> None:
        self.location = location
