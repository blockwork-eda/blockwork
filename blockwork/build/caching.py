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
import functools
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType
from typing import DefaultDict, Iterable, Optional, TYPE_CHECKING, TypedDict
if TYPE_CHECKING:
    from ..transforms import Transform
from ..context import Context
from ordered_set import OrderedSet as OSet
from datetime import datetime, timezone
import distutils.sysconfig
import ast
import site

class MedialStoreData(TypedDict):
    '''
    Medial data stored as JSON in caches
    '''
    src: str
    key: str

class TransformStoreData(TypedDict):
    '''
    Transform data stored as JSON in caches
    '''
    run_time: float
    byte_size: int
    medials: dict[str, MedialStoreData]

class MedialFetchData(TypedDict):
    '''
    Medial data used to fetch items from caches
    '''
    dst: str

class TransformFetchData(TypedDict):
    '''
    Transfrom data used to fetch transforms from caches
    '''
    medials: dict[str, MedialFetchData]

class PyHasher:

    def __init__(self):
        self.module_stack: list[ModuleType] = []
        self.dependency_map: DefaultDict[str, OSet[str]] = DefaultDict(OSet)
        self.hash_map: dict[str, str] = {}
        self.visitor = ast.NodeVisitor()
        self.visitor.visit_Import = self.visit_Import
        self.visitor.visit_ImportFrom = self.visit_ImportFrom

        # Get a basic hash of the site
        site_str =''
        for sitepackages in site.getsitepackages():
            site_str += ''.join(sorted(os.listdir(sitepackages)))
        self.site_hash = hashlib.md5(site_str.encode('utf8')).hexdigest()

    @property
    def current_package(self):
        return self.module_stack[-1].__name__

    @property
    def current_module(self):
        return self.module_stack[-1]

    def is_package(self, module: ModuleType):
        return hasattr(module, "__path__")

    def visit_Import(self, node):
        for name in node.names:
            # import a,b,c
            self.map_package(name.name)

    def visit_ImportFrom(self, node):
        if node.module is not None and node.level == 0:
            # Non-relative import from a module
            # `from a import b`
            self.map_package(node.module)
            return

        # Get context based on level (number of '.')
        level = (node.level - 1) if self.is_package(self.current_module) else node.level
        context, *_rest = self.current_package.rsplit('.', level)

        if node.module is not None:
            # `from .a import b`
            self.map_package(f"{context}.{node.module}")
            return

        for name in node.names:
            # from . import a,b,c
            self.map_package(f"{context}.{name.name}")
            return

    def map_package(self, package: str):
        if package in self.dependency_map:
            # Don't re-process
            return
        if (module:=sys.modules.get(package, None)) is None:
            # Package may not be in sys modules if it's imported conditionally
            # or within a function etc...
            return
        self.map_module(module)

    def map_module(self, module: ModuleType):
        # Skip built-ins
        if (module.__spec__ is None or
            module.__spec__.origin in ["built-in", "frozen"]
        ):
            return

        # Skip standard library, pip modules, and compiled
        if (module.__file__ is None or
            module.__file__.startswith(distutils.sysconfig.BASE_PREFIX) or
            module.__file__.startswith(distutils.sysconfig.PREFIX) or
            not module.__file__.endswith('.py')
        ):
            return

        # Add as a dependency of calling package
        if len(self.module_stack):
            self.dependency_map[self.current_package].add(module.__name__)

        # Push the import context
        self.module_stack.append(module)

        # Read the file, parse it, examine imports, and record the hash
        with open(module.__file__, 'r') as f:
            module_ast = ast.parse(f.read())
            self.visitor.visit(module_ast)
            content_hash = hashlib.md5(ast.dump(module_ast).encode('utf8'))

        # Pop the import context
        self.module_stack.pop()

        # Roll in the site hash
        content_hash.update(self.site_hash.encode('utf8'))

        # Roll in the dependency hashes
        for dependency in self.dependency_map[module.__name__]:
            content_hash.update(self.hash_map[dependency].encode('utf8'))

        # Record hash
        self.hash_map[module.__name__] = content_hash.hexdigest()


    def get_package_hash(self, package: str):
        'Get the hash for a package'
        if package not in self.hash_map:
            self.map_package(package)
        return self.hash_map[package]


def get_byte_size(path: str | Path) -> int:
    'Get the size of a file or directory in bytes'
    if not os.path.exists(path):
        return 0
    if not os.path.isdir(path):
        return os.path.getsize(path)
    size = os.path.getsize(path)
    for dirpath, dirnames, filenames in os.walk(path):
        for name in (dirnames + filenames):
            filepath = os.path.join(dirpath, name)
            if not os.path.islink(filepath):
                size += os.path.getsize(filepath)
    return size

class Cache(ABC):
    pyhasher = PyHasher()
    medial_prefix = "md:"
    transform_prefix = "tx:"

    @staticmethod
    def enabled(ctx: Context):
        '''
        True if any cache is configured
        '''
        return len(ctx.caches) > 0

    @staticmethod
    def prune_all(ctx: Context):
        '''
        Prune all configured caches
        '''
        for cache in ctx.caches:
            cache.prune()

    @functools.cache
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
    def hash_imported_package(package: str) -> str:
        '''
        Hash a python package **that has already been imported**. This is
        currently implemented as a hash of module paths and modify times.

        In the future this could be improved by calculating the import tree
        for the module, resulting in fewer unnecessary rebuilds.
        '''
        return Cache.pyhasher.get_package_hash(package)

    @staticmethod
    def fetch_transform_from_any(ctx: Context, transform: "Transform") -> bool:
        'Fetch all the output interfaces for a transform'
        medials: dict[str, MedialFetchData] = {}
        for name, serial in transform._serial_interfaces.items():
            if serial.direction.is_input:
                continue
            for medial in serial.medials:
                medials[name] = MedialFetchData(dst=medial.val)
        data = TransformFetchData(medials=medials)

        # Pull from the first cache that has the item
        for cache in ctx.caches:
            if cache.fetch_transform(f"{Cache.transform_prefix}{transform._input_hash()}", data):
                return True
        return False

    @staticmethod
    def store_transform_to_any(ctx: Context, transform: "Transform", run_time: float) -> bool:
        'Store all the output interfaces for a transform'
        medials: dict[str, MedialStoreData] = {}
        byte_size = 0
        for name, serial in transform._serial_interfaces.items():
            if serial.direction.is_input:
                continue
            for medial in serial.medials:
                byte_size += get_byte_size(medial.val)
                medials[name] = MedialStoreData(src=medial.val, key=f"{Cache.medial_prefix}{Cache.hash_content(Path(medial.val))}")
        data = TransformStoreData(run_time=run_time, byte_size=byte_size, medials=medials)

        # Store to any caches that will take it
        stored_somewhere = False
        for cache in ctx.caches:
            if cache.store_transform(f"{Cache.transform_prefix}{transform._input_hash()}", data):
                stored_somewhere = True
        return stored_somewhere

    def prune(self):
        '''
        Prune the cache down to the limit set by the target_size property.
        '''
        now = datetime.now(timezone.utc).timestamp()

        target_size = self.target_size

        total_size = 0
        present_medials = set()
        transform_sizes = DefaultDict(int)
        transform_scores = DefaultDict(float)
        transform_medials = dict()

        # Collect cache item data
        for key in self.iter_keys():
            if key.startswith(Cache.medial_prefix):
                # Medial exists (but transform info might not!)
                present_medials.add(key)
            elif key.startswith(Cache.transform_prefix):
                # Read the transforms data
                if (sdata:=self.fetch_value(key, peek=True)) is None:
                    return False
                store_data: TransformStoreData = json.loads(sdata)
                # Calculate a usefulness score for the transform, where a
                # lower score means less useful and a better candidate for
                # eviction.
                # The ideal cache entry:
                #  - Took a long time to run originally
                #  - Produces small output files
                #  - Was accessed very recently
                run_time = store_data['run_time']
                byte_size = store_data['byte_size'] + len(sdata.encode('utf-8'))
                fetch_delta = now - self.get_last_fetch_utc(key)
                transform_scores[key] = run_time / byte_size / fetch_delta
                transform_sizes[key] = byte_size
                total_size += byte_size

                # Record the expected medials as some might be missing
                transform_medials[key] = set()
                for medial_data in store_data['medials'].values():
                    transform_medials[key].add(medial_data['key'])
            else:
                # Unexpected data - delete it.
                self.drop_item(key)

        # If any medial missing for a transform, set transform score to zero
        # as it is not useful to have it cached.
        for transform, medials in transform_medials.items():
            if medials - present_medials:
                transform_scores[transform] = 0

        # Remove transforms starting with those with the worst score until we
        # reach the target size, always removing any with a score of zero.
        for transform, score in sorted(transform_scores.items(), key=lambda i: i[1]):
            if score > 0 and total_size < target_size:
                break
            if self.drop_item(transform):
                del transform_medials[transform]
                total_size -= transform_sizes[transform]

        # Find medials that are referenced by remaining transforms
        referenced_medials = set()
        for medials in transform_medials.values():
            referenced_medials |= medials

        # Remove any medials with no transform referencing them
        unreferenced_medials = present_medials - referenced_medials
        for medial in unreferenced_medials:
            self.drop_item(medial)

    def store_transform(self, key: str, data: TransformStoreData) -> bool:
        'Store a transform to the cache'
        stored = True
        for medial_data in data["medials"].values():
            if self.store_item(medial_data['key'], Path(medial_data['src'])):
                continue
            stored = False

        if not stored or not self.store_value(key, json.dumps(data)):
            for medial_data in data["medials"].values():
                self.drop_item(medial_data['key'])
            return False
        return True

    def fetch_transform(self, key: str, data: TransformFetchData) -> bool:
        'Fetch a transform from the cache'
        if (sdata:=self.fetch_value(key)) is None:
            return False
        store_data: TransformStoreData = json.loads(sdata)

        for medial_key, medial_data in store_data['medials'].items():
            if not self.fetch_item(medial_data['key'], Path(data['medials'][medial_key]['dst'])):
                return False
        return True

    def store_value(self, key: str, value: str) -> bool:
        '''
        Try and store a string value by key. Should return True if the value
        is successfully stored or is already present.

        :param key:  The unique item key.
        :param frm:  The string value to be written.
        :return:     True if the item is successfully stored.
        '''
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write(value)
        result = self.store_item(key, Path(f.name))
        os.unlink(f.name)
        return result

    def drop_value(self, key: str) -> bool:
        '''
        Remove a string value from the store by key. Return True if item removed
        successfully.

        :param key:  The unique item key.
        :return:     True if the item is successfully removed
        '''
        return self.drop_item(key)


    def fetch_value(self, key: str, peek: bool=False) -> Optional[str]:
        '''
        Fetch a string value from the store by key. Return None if not present.

        :param key:  The unique item key.
        :param peek: Whether to skip the fetch time update (used internally by
                     meta-operations that shouldn't affect cache state).
        :return:     The fetched string or None if the fetch failed.
        '''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data'
            result = self.fetch_item(key, path, peek=peek)
            return path.read_text() if result else None

    @property
    @abstractmethod
    def target_size(self) -> int:
        '''
        Get the target cache size in bytes. Note this is the level that the
        cache will be pruned to, not a hard-limit.

        :return: The target cache size in bytes
        '''

    @abstractmethod
    def store_item(self, key: str, frm: Path) -> bool:
        '''
        Try and store a file or directory by key. Should return True if the
        item is successfully stored or is already present.

        :param key:  The unique item key.
        :param frm:  The location of the item to be copied in.
        :return:     True if the item is successfully stored.
        '''
        ...

    @abstractmethod
    def drop_item(self, key: str) -> bool:
        '''
        Remove a file or directory from the store. Must be able to handle missing
        files and directories.

        :param key:  The unique item key.
        :return:     True if the item is successfully removed
        '''
        ...

    @abstractmethod
    def fetch_item(self, key: str, to: Path, peek: bool=False) -> bool:
        '''
        Retrieve a file or directory from the store, copying it to the path
        provided by `to`. Should return True if the item is successfully
        retreived from the cache.

        :param key:  The unique item key.
        :param to:   The path where the item should be copied to.
        :param peek: Whether to skip the fetch time update (used internally by
                     meta-operations that shouldn't affect cache state).
        :return:     Whether the item was successfully fetched.
        '''
        ...

    @abstractmethod
    def get_last_fetch_utc(self, key: str) -> int | float:
        '''
        Get the last fetch time as a UTC timestamp.

        :param key:  The unique item key.
        :return:     The last time an item was fetched as a UTC timestamp.
        '''
        ...

    @abstractmethod
    def iter_keys(self) -> Iterable[str]:
        '''
        Iterate over keys stored in the key cache

        :return: Iterable of keys in the cache
        '''
        ...
