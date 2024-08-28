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
'''
This module contains the fundamentals required for the implementation of
caching mechanisms. See the example project's cache for a simple working
example.

The cache scheme stores files using the hash of its content as a key, and
additionally stores a many-to-one map of a hashkey which is computable
before anything is run to that content hash.

Stages:
  Initial:
    - Hash the content of static input interfaces
    - Use these to compute transform hashkeys for nodes with no dependencies
    - Use input interface names along with the hashkeys of transforms that
        output them to get the transform hashkeys for nodes with dependencies

  Pre-run:
    - Go through the transforms in reverse order
    - Try and pull all output interfaces from caches - if successful mark that
        transform as fetched.
    - If all dependents of a transform are fetched, mark a transform as skipped

  During-run:
    - Go through transforms in dependency order as usual
    - Skip transforms marked as fetched or skipped
    - Push output interfaces to all caches that allow it

Future improvements:
  - Pass through information such as tags, file-size, and time-to-create
    through to caches so they can make intelligent decisions on what to cache.

'''

from abc import ABC, abstractmethod
import hashlib
import os
from pathlib import Path
import sys
from types import ModuleType
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from ..transforms import Transform
from ..context import Context

# Switch to never pull or push from the cache, but to instead compare the
# hash with existing cache entries.
# This will become a command option later...
CACHE_CONSISTENCY_MODE = False

_module_hash_map = {}

class Cache(ABC):

    @staticmethod
    def enabled(ctx: Context):
        '''
        True if any cache is configured
        '''
        return len(ctx.caches) > 0

    @staticmethod
    def hash_content(path: Path) -> str:
        '''
        Hash the content of a file or directory. This needs to be consistent
        across caching schemes so consistency checks can be performed.
        '''
        if not path.exists():
            assert path.is_symlink(), f"Tried to hash a path that does not exist `{path}`"
            # Symlinks might point to a path that doesn't exist and that's ok
            content_hash = hashlib.md5(f'<symlink to {path.resolve()}>'.encode('utf8'))
        elif path.is_dir():
            content_hash = hashlib.md5('<dir>'.encode('utf8'))
            for item in sorted(os.listdir(path)):
                content_hash.update((item + Cache.hash_content(path / item)).encode('utf8'))
        else:
            with path.open('rb') as f:
                content_hash = hashlib.file_digest(f, 'md5')
        return content_hash.hexdigest()

    @staticmethod
    def hash_module(module: str) -> str:
        '''
        Hash a python module **that has already been imported**. This is
        currently implemented as a hash of module paths and modify times.

        In the future this could be improved by calculating the import tree
        for the module, resulting in fewer unnecessary rebuilds.
        '''
        if (hsh := _module_hash_map.get(module, None)) is not None:
            return hsh

        import_str = ""
        for m in sys.modules.copy().values():
            if not isinstance(m, ModuleType):
                continue
            if m.__spec__ is None:
                continue
            if m.__spec__.origin in ["built-in", "frozen"]:
                continue
            if m.__file__ is None:
                continue

            import_str += m.__file__ + str(os.path.getmtime(m.__file__))

        hsh = hashlib.md5(import_str.encode("utf8")).hexdigest()
        _module_hash_map[module] = hsh
        return hsh

    @staticmethod
    def store_to_any(ctx: Context, key_hash: str, frm: Path) -> bool:
        'Store to every cache that will accept the content'
        stored_somewhere = False
        for cache in ctx.caches:
            if cache.store(key_hash, frm):
                stored_somewhere = True
        return stored_somewhere

    @staticmethod
    def fetch_from_any(ctx: Context, key_hash: str, to: Path) -> bool:
        'Pull from the first cache that has the item'
        for cache in ctx.caches:
            if cache.fetch(key_hash, to):
                return True
            to.unlink(missing_ok=True)
        return False

    @staticmethod
    def fetch_transform(ctx: Context, transform: "Transform") -> bool:
        'Fetch all the output interfaces for a transform'
        if CACHE_CONSISTENCY_MODE:
            return False

        for name, (direction, serial) in transform._serial_interfaces.items():
            if direction.is_input:
                continue
            for medial in serial.medials:
                hashkey = f"{name}-{medial._input_hash()}"
                if not Cache.fetch_from_any(ctx, hashkey, Path(medial.val)):
                    return False
        return True

    @staticmethod
    def store_transform(ctx: Context, transform: "Transform") -> bool:
        'Store all the output interfaces for a transform'
        if CACHE_CONSISTENCY_MODE:
            for name, (direction, serial) in transform._serial_interfaces.items():
                if direction.is_input:
                    continue
                for medial in serial.medials:
                    hashkey = f"{name}-{medial._input_hash()}"
                    content_hash = Cache.hash_content(Path(medial.val))
                    for cache in ctx.caches:
                        assert content_hash == cache.fetch_hash(hashkey)
            return False

        for name, (direction, serial) in transform._serial_interfaces.items():
            if direction.is_input:
                continue
            for medial in serial.medials:
                hashkey = f"{name}-{medial._input_hash()}"
                if not Cache.store_to_any(ctx, hashkey, Path(medial.val)):
                    return False
        return True

    def store(self, key_hash: str, frm: Path) -> bool:
        'Store a single file/directory'
        content_hash = Cache.hash_content(frm)
        if self.store_item(content_hash, frm):
            if self.store_hash(key_hash, content_hash):
                return True
            self.drop_item(content_hash)
        return False

    def fetch(self, key_hash: str, to: Path) -> bool:
        'Fetch a single file/directory'
        if (content_hash:=self.fetch_hash(key_hash)) is not None:
            if self.fetch_item(content_hash, to):
                return True
        to.unlink(missing_ok=True)
        return False

    @abstractmethod
    def store_hash(self, key_hash: str, content_hash: str) -> bool: ...
    '''
    Try and store a hash in the key cache. Should return True if the item
    is successfully placed in the cache, or is already present.
    '''

    @abstractmethod
    def drop_hash(self, key_hash: str) -> bool: ...
    '''
    Remove a hash from the key cache. Must be able to handle missing keys.
    '''

    @abstractmethod
    def fetch_hash(self, key_hash: str) -> Optional[str]: ...
    '''
    Fetch the content hash from the key cache. Return None if not present.
    '''

    @abstractmethod
    def store_item(self, content_hash: str, frm: Path) -> bool: ...
    '''
    Try and store an item in the content cache. Should return True if the item
    is successfully placed in the cache or was already present (this will
    happen if two different key_hashes result in the same content hash).
    '''

    @abstractmethod
    def drop_item(self, content_hash: str): ...
    '''
    Remove an item from the content cache. Must be able to handle missing values,
    and directories.
    '''

    @abstractmethod
    def fetch_item(self, content_hash: str, to: Path) -> bool: ...
    '''
    Try and fetch an item from the content cache. Should return True if the
    item is successfully retreived from the cache.
    '''
