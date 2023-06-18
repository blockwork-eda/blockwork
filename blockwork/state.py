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
import logging
from pathlib import Path
from typing import Any, Dict, Union

class StateError(Exception):
    pass


class StateNamespace:
    """
    A wrapper around a state tracking file, which is simply a JSON dictionary
    written to disk. The wrapper allows arbitrary keys to be set and retrieved,
    with values serialised to disk when the tool exits.

    :param name:    Name of the state object
    :param path:    Path to the JSON file where data is serialised
    """

    def __init__(self, name : str, path : Path) -> None:
        self.__name    = name
        self.__path    = path
        self.__data    = {}
        self.__altered = False
        self.load()

    def load(self) -> None:
        """ Load state from disk if the file exists """
        if self.__path.exists():
            with self.__path.open("r", encoding="utf-8") as fh:
                self.__data = json.load(fh)

    def store(self) -> None:
        """ Write out state to disk if any values have been changed """
        # Check the alterations flag, return immediately if nothing has changed
        if not self.__altered:
            return
        # Write out the updated data
        logging.debug(f"Saving updated state for {self.__name} to {self.__path}")
        with self.__path.open("w", encoding="utf-8") as fh:
            json.dump(self.__data, fh, indent=4)
        # Clear the alterations flag
        self.__altered = False

    def __getattr__(self, name: str) -> Any:
        try:
            return super().__getattr__(name)
        except Exception:
            return self.get(name)

    def __setattr__(self, name: str, value: Union[str, int, float, bool]) -> None:
        if name in ("get", "set") or name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self.set(name, value)

    def get(self, name: str, default: Any = None) -> Union[str, int, float, bool, None]:
        """
        Retrieve a value from the stored data, returning a default value if the
        key has not been set.

        :param name:    Name of the attribute to retrieve
        :param default: Default value to return if no previous value set
        :returns:       Value or the default value if not defined
        """
        return self.__data.get(name, default)

    def set(self, name: str, value: Union[str, int, float, bool]) -> None:
        """
        Set a value into the stored data, this must be of a primitive type such
        as string, integer, float, or boolean (so that it can be serialised)

        :param name:    Name of the attribute to set
        :param value:   Value to set
        """
        if not isinstance(value, (str, int, float, bool)):
            raise StateError(f"Value of type {type(value).__name__} is not supported")
        if not self.__altered:
            self.__altered = (value != self.__data.get(name, None))
        self.__data[name] = value


class State:
    """
    Manages the state tracking folder for the project

    :param location:    Absolute path to the state folder
    """

    def __init__(self, location : Path) -> None:
        self.__location = location
        self.__files : Dict[str, StateNamespace] = {}
        # When the program exits, ensure all modifications are saved to disk
        atexit.register(self.save_all)

    def save_all(self) -> None:
        """ Iterate through all open state objects and store any modifications """
        self.__location.mkdir(parents=True, exist_ok=True)
        for file in self.__files.values():
            file.store()

    def __getattr__(self, name: str) -> Any:
        try:
            return super().__getattr__(name)
        except Exception:
            return self.get(name)

    def get(self, name: str) -> StateNamespace:
        """
        Retrieve a state file wrapper for a given name, generating a new wrapper
        on the fly if one has never been retrieved before.

        :param name:    Name of the state file
        :returns:       Instance of StateNamespace
        """
        if name not in self.__files:
            self.__files[name] = StateNamespace(name, self.__location / f"{name}.json")
        return self.__files[name]
