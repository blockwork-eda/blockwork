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
"""
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

"""

from abc import ABC, abstractmethod
import functools
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import ModuleType
from typing import Any, ClassVar, DefaultDict, Iterable, NotRequired, Optional, TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from ..transforms import Transform
from ..context import Context
from ordered_set import OrderedSet as OSet
from datetime import datetime, timezone
import distutils.sysconfig
import ast
import site
from ..config import CacheConfig as CacheConfig
from humanfriendly import InvalidTimespan, parse_size, parse_timespan


TraceData = tuple[str, str, str, str, list["TraceData"]]

class TransformStableDetails(TypedDict):
    mod_name: str
    cls_name: str
    mname_to_okeys: dict[str, list[str]]

class TransformTransientDetails(TypedDict):
    run_time: float
    byte_size: int

class TransformKeyData(TypedDict):
    """
    Transfrom data used to fetch transforms from caches
    """
    stable: TransformStableDetails
    transient: TransformTransientDetails
    trace: NotRequired[list[TraceData] | None]


class TransformStoreData(TypedDict):
    key_data: TransformKeyData
    mkey_to_path: dict[str, Path]


class TransformFetchData(TypedDict):
    mname_to_paths: dict[str, list[Path]]


class CacheError(RuntimeError):
    pass

class CacheDeterminismError(CacheError):
    pass


KEY_FILE_SIZE = 250
"The size of key files, small variance but it doesn't matter."

class BWFrozenHash:
    def __init__(self, ident: str, byte_digest: bytes, trace: list[TraceData] | None = None):
        self.ident = ident
        self._byte_digest = byte_digest
        self.trace = trace

    def digest(self):
        return self._byte_digest

    def hex_digest(self):
        return self._byte_digest.hex()

    def __repr__(self) -> str:
        return self.hex_digest()

class BWHash:
    keep_trace: ClassVar[bool] = False

    def __init__(self, ident: str = "<missing_ident>"):
        self._ident = ident
        self._md5 = hashlib.md5()
        self._trace: list[TraceData] = []

    def with_str(self, value: str) -> "BWHash":
        self.update_str(value)
        return self

    def with_path(self, value: Path) -> "BWHash":
        self.update_path(value)
        return self

    def with_hash(self, value: "BWFrozenHash") -> "BWHash":
        self.update_hash(value)
        return self

    def update_str(self, value: str):
        self._md5.update(value.encode("utf-8"))
        if self.keep_trace:
            md5 = hashlib.md5(value.encode("utf-8"))
            self._trace.append(("str", repr(value[:80]), md5.hexdigest(), self._md5.hexdigest(), []))

    def update_path(self, value: Path):
        with value.open("rb") as f:
            self._md5.update((md5 := hashlib.file_digest(f, "md5")).digest())
        if self.keep_trace:
            self._trace.append(("path", value.as_posix(), md5.hexdigest(), self._md5.hexdigest(), []))

    def update_hash(self, value: "BWFrozenHash"):
        self._md5.update(value.digest())
        if self.keep_trace:
            self._trace.append(("hash", value.ident, value.hex_digest(), self._md5.hexdigest(), value.trace or []))

    def frozen(self) -> BWFrozenHash:
        return BWFrozenHash(self._ident, self._md5.digest(), self._trace)

class PyHasher:
    def __init__(self):
        self.module_stack: list[ModuleType] = []
        self.dependency_map: DefaultDict[str, OSet[str]] = DefaultDict(OSet)
        self.hash_map: dict[str, BWFrozenHash] = {}
        self.visitor = ast.NodeVisitor()
        self.visitor.visit_Import = self.visit_Import
        self.visitor.visit_ImportFrom = self.visit_ImportFrom

    @property
    def current_package(self):
        return self.module_stack[-1].__name__

    @property
    def current_module(self):
        return self.module_stack[-1]

    def is_package(self, module: ModuleType):
        return hasattr(module, "__path__")

    def visit_Import(self, node):
        if node.col_offset:
            # Don't process conditional imports as we can't
            # manage them in a reasonable way.
            return
        for name in node.names:
            # import a,b,c
            self.map_package(name.name)

    def visit_ImportFrom(self, node):
        if node.col_offset:
            # Don't process conditional imports as we can't
            # manage them in a reasonable way.
            return
        if node.module is not None and node.level == 0:
            # Non-relative import from a module
            # `from a import b`
            self.map_package(node.module)
            return

        # Get context based on level (number of '.')
        level = (node.level - 1) if self.is_package(self.current_module) else node.level
        context, *_rest = self.current_package.rsplit(".", level)

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
            # Don't re-process but add dependency
            if len(self.module_stack):
                self.dependency_map[self.current_package].add(package)
            return
        self.map_module(sys.modules[package])

    def map_module(self, module: ModuleType):
        # Skip built-ins
        if module.__spec__ is None or module.__spec__.origin in ["built-in", "frozen"]:
            return

        # Skip standard library, pip modules, and compiled
        if (
            module.__file__ is None
            or module.__file__.startswith(distutils.sysconfig.BASE_PREFIX)
            or module.__file__.startswith(distutils.sysconfig.PREFIX)
            or not module.__file__.endswith(".py")
        ):
            return

        # Add as a dependency of calling package
        if len(self.module_stack):
            self.dependency_map[self.current_package].add(module.__name__)

        # Push the import context
        self.module_stack.append(module)

        content_hash = BWHash(module.__file__)

        # Read the file, parse it, examine imports, and record the hash
        with open(module.__file__, "r") as f:
            module_ast = ast.parse(f.read())
            self.visitor.visit(module_ast)
        # Roll in the dependency hashes
        for dependency in self.dependency_map[module.__name__]:
            content_hash.update_hash(self.hash_map[dependency])

        # Roll in the content hash
        content_hash.update_str(ast.dump(module_ast))

        # Pop the import context
        self.module_stack.pop()

        # Record hash
        self.hash_map[module.__name__] = content_hash.frozen()

    def get_package_hash(self, package: str) -> BWFrozenHash:
        "Get the hash for a package"
        if package not in self.hash_map:
            self.map_package(package)
        return self.hash_map[package]


def get_byte_rate(byte_size: int, second_time: float):
    "Calculate bytes/second, avoiding infinity with a small delta"
    if second_time == 0:
        second_time = 1e-9
    return byte_size / second_time


class Cache(ABC):
    pyhasher = PyHasher()
    medial_prefix = "md-"
    transform_prefix = "tx-"

    def __init__(self, ctx: Context, cfg: CacheConfig):
        self.ctx = ctx
        self.cfg = cfg
        self.error_root = self.ctx.host_scratch / "cache_errors"

    @staticmethod
    def parse_threshold(condition: str | bool) -> float:
        """
        Parse a cache threshold condition into seconds/byte (s/B).

        Conditions can either be expressed as booleans:
            `True`: Always
            `False`: Never
        or as human friendly seconds/byte expressions:
            `1B/s`: > 1 second to create each byte.
            `1GB/h`: > 1 hour to create each Gigabyte.
            `5MB/4m` > 4 minutes to create each 5 Megabytes.
        """
        if condition is True:
            return math.inf
        if condition is False:
            return 0

        parts = condition.split("/")
        if len(parts) != 2:
            raise ValueError(
                "Cache condition must either be expressed as a boolean or as a fraction e.g. `3MB/s`"
            )
        dividend, divisor = parts
        byte_size = parse_size(dividend)
        try:
            seconds = parse_timespan(divisor)
        except InvalidTimespan:
            # Allow e.g. 5GB/1s or just 1GB/s
            seconds = parse_timespan("1" + divisor)
        return get_byte_rate(second_time=seconds, byte_size=byte_size)

    @functools.cached_property
    def fetch_threshold(self) -> float:
        """
        The threshold in terms of seconds-to-create per byte-size (s/B) at
        which items will be fetched from this cache.
        """
        return Cache.parse_threshold(self.cfg.fetch_condition)

    @functools.cached_property
    def store_threshold(self) -> float:
        """
        The threshold in terms of seconds-to-create per byte-size (s/B) at
        which items will be stored into this cache.
        """
        return Cache.parse_threshold(self.cfg.store_condition)

    @staticmethod
    def enabled(ctx: Context):
        """
        True if any cache is configured
        """
        return len(ctx.caches) > 0

    @staticmethod
    def prune_all(ctx: Context):
        """
        Prune all configured caches
        """
        for cache in ctx.caches:
            cache.prune()

    @functools.cache
    @staticmethod
    def hash_size_content(path: Path) -> tuple[BWFrozenHash, int]:
        """
        Hash the content of a file or directory and get the size in bytes.
        This needs to be consistent across caching schemes so consistency
        checks can be performed.
        """
        if not path.exists():
            assert path.is_symlink(), f"Tried to hash a path that does not exist `{path}`"
            # Symlinks might point to a path that doesn't exist and that's ok
            content_hash = BWHash().with_str(f"<symlink to {path.resolve()}>")
            byte_size = 0
        elif path.is_dir():
            content_hash = BWHash().with_str("<dir>")
            byte_size = 0
            for item in sorted(os.listdir(path)):
                sub_hash, sub_size = Cache.hash_size_content(path / item)
                content_hash.update_str(item)
                content_hash.update_hash(sub_hash)
                byte_size += sub_size
        else:
            content_hash = BWHash().with_path(path)
            byte_size = os.path.getsize(path)
        return content_hash.frozen(), byte_size

    @staticmethod
    def hash_imported_package(package: str) -> BWFrozenHash:
        """
        Hash a python package **that has already been imported**. This is
        currently implemented as a hash of module paths and modify times.

        In the future this could be improved by calculating the import tree
        for the module, resulting in fewer unnecessary rebuilds.
        """
        return Cache.pyhasher.get_package_hash(package)

    @staticmethod
    def _clear_cached_hashes():
        """
        Clear the cache for the hash functions, useful for testing.
        """
        Cache.hash_size_content.cache_clear()

    @staticmethod
    def get_transform_fetch_data(transform: "Transform") -> TransformFetchData:
        """
        Get the information we need from a transform in order to fetch it.
        """
        mname_to_paths: dict[str, list[Path]] = {}

        for name, serial in transform._serial_interfaces.items():
            if serial.direction.is_input:
                continue
            mname_to_paths[name] = []
            for medial in serial.medials:
                mname_to_paths[name].append(Path(medial.val))
        return TransformFetchData(mname_to_paths=mname_to_paths)

    @staticmethod
    def get_transform_store_data(ctx: Context, transform: "Transform", run_time: float) -> TransformStoreData:
        """
        Get the information we need from a transform in order to store it.
        """
        mname_to_okeys: dict[str, list[str]] = {}
        mkey_to_path: dict[str, Path] = {}

        byte_size = 0
        for name, serial in transform._serial_interfaces.items():
            if serial.direction.is_input:
                continue

            mname_to_okeys[name] = []
            for midx, medial in enumerate(serial.medials):
                if serial.deterministic:
                    # Compute hash based on file content
                    mhash = medial._content_hash()
                else:
                    # Compute hash based on definition
                    mhash = BWHash().with_hash(transform._input_hash()).with_str(name + str(midx)).frozen()
                byte_size += medial._byte_size()
                key = Cache.medial_prefix + mhash.hex_digest()
                mname_to_okeys[name].append(key)
                mkey_to_path[key] = Path(medial.val)

        return TransformStoreData(
            key_data=TransformKeyData(
                stable={
                    "mname_to_okeys": mname_to_okeys,
                    "cls_name":transform._cls_name,
                    "mod_name":transform._mod_name
                },
                transient={
                    "byte_size":byte_size,
                    "run_time": run_time,
                },
                trace=transform._input_hash().trace
            ),
            mkey_to_path=mkey_to_path,
        )

    @staticmethod
    def fetch_transform_key_data_from_any(ctx: Context, key: str) -> TransformKeyData | None:
        "Fetch transform key data from any available cache"

        for cache in ctx.caches:
            if cache.fetch_threshold > 0 and (key_data := cache.fetch_object(key)) is not None:
                return key_data

        return None

    @staticmethod
    def fetch_transform_from_any(ctx: Context, transform: "Transform") -> bool:
        "Fetch all the output interfaces for a transform from any available cache"
        key = Cache.transform_prefix + transform._input_hash().hex_digest()

        key_data = Cache.fetch_transform_key_data_from_any(ctx, key)
        if key_data is None:
            return False

        fetch_data = Cache.get_transform_fetch_data(transform)

        mname_to_paths = fetch_data["mname_to_paths"]
        mname_to_okeys = key_data["stable"]["mname_to_okeys"]
        mkey_to_path: dict[str, Path] = {}
        for mname, mpaths in mname_to_paths.items():
            mkeys = mname_to_okeys[mname]
            for mkey, mpath in zip(mkeys, mpaths):
                mkey_to_path[mkey] = mpath

        byte_rate = get_byte_rate(second_time=key_data["transient"]["run_time"], byte_size=key_data["transient"]["byte_size"])

        for cache in ctx.caches:
            if byte_rate > cache.fetch_threshold:
                continue
            if cache.fetch_transform(mkey_to_path):
                for other_cache in ctx.caches:
                    if other_cache is cache:
                        continue
                    if other_cache.cfg.check_determinism:
                        other_cache.check_determinism(key, key_data, mkey_to_path)
                    if byte_rate > other_cache.store_threshold:
                        continue
                    other_cache.store_object(key, key_data)
                    other_cache.store_transform(mkey_to_path)
                return True

        return False

    @staticmethod
    def store_transform_to_any(ctx: Context, transform: "Transform", run_time: float) -> bool:
        "Store all the output interfaces for a transform into all available cahche"
        key = Cache.transform_prefix + transform._input_hash().hex_digest()

        store_data = Cache.get_transform_store_data(ctx, transform, run_time)

        key_data = store_data["key_data"]
        mkey_to_path = store_data["mkey_to_path"]

        byte_rate = get_byte_rate(second_time=key_data["transient"]["run_time"], byte_size=key_data["transient"]["byte_size"])

        # Store to any caches that will take it
        stored_somewhere = False
        for cache in ctx.caches:
            if cache.cfg.check_determinism:
                cache.check_determinism(key, key_data, mkey_to_path)
            if byte_rate > cache.store_threshold:
                continue
            cache.store_object(key, key_data)
            if cache.store_transform(mkey_to_path):
                stored_somewhere = True

        return stored_somewhere

    def prune(self):
        """
        Prune the cache down to the limit set by the configuration.
        """
        now = datetime.now(timezone.utc).timestamp()

        if self.cfg.max_size is None:
            return

        target_size = parse_size(self.cfg.max_size)

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
                store_data: TransformKeyData | None = None
                if (store_data := self.fetch_object(key)) is None:
                    return False
                # Calculate a usefulness score for the transform, where a
                # lower score means less useful and a better candidate for
                # eviction.
                # The ideal cache entry:
                #  - Took a long time to run originally
                #  - Produces small output files
                #  - Was accessed very recently
                run_time = store_data["transient"]["run_time"]
                byte_size = store_data["transient"]["byte_size"] + KEY_FILE_SIZE
                fetch_delta = now - self.get_last_fetch_utc(key)
                transform_scores[key] = run_time / byte_size / fetch_delta
                transform_sizes[key] = byte_size
                total_size += byte_size

                # Record the expected medials as some might be missing
                transform_medials[key] = set()
                for medial_keys in store_data["stable"]["mname_to_okeys"].values():
                    for medial_key in medial_keys:
                        transform_medials[key].add(medial_key)
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

    def check_determinism(self, key: str, key_data: TransformKeyData, mkey_to_path: dict[str, Path]):
        "Check transform key data is deterministic"
        stored_key_data: TransformKeyData | None
        if (stored_key_data := self.fetch_object(key)) is None:
            return

        new = key_data["stable"]
        old = stored_key_data["stable"]
        if new == old:
            return

        # Write out the key data for debug
        (self.error_root / key).mkdir(parents=True, exist_ok=True)
        old_key_path = self.error_root / key / "old"
        new_key_path = self.error_root / key / "new"
        with old_key_path.open("w") as f:
            json.dump(stored_key_data, f)

        with new_key_path.open("w") as f:
            json.dump(key_data, f)

        key_text = (f"Old Key Data: '{old_key_path}'\n"
                    f"New Key Data: '{new_key_path}'")


        if (new["cls_name"], new["mod_name"]) != (old["cls_name"], old["mod_name"]):
            # Vanishingly unlikely hash collision
            raise CacheDeterminismError("Transform hash collision detected!\n"
                                        "Transform name mismatch.\n"
                                        f"{key_text}\n"
                                        f"Old Name: {new['mod_name']}.{new['cls_name']}\n"
                                        f"New Name: {old['mod_name']}.{old['cls_name']}")

        if (new["mname_to_okeys"] != old["mname_to_okeys"]):
            if (mnames := sorted(new["mname_to_okeys"].keys())) != (old_mnames := sorted(old["mname_to_okeys"].keys())):
                # Vanishingly unlikely hash collision
                raise CacheDeterminismError("Transform hash collision detected!\n"
                                            "Output key mismatch.\n"
                                            f"{key_text}\n"
                                            f"Old keys: {old_mnames}\n"
                                            f"New keys: {mnames}")

            for mname in mnames:
                if (new_mkeys := new["mname_to_okeys"][mname]) == (old_mkeys := old["mname_to_okeys"][mname]):
                    continue

                if len(new_mkeys) != len(old_mkeys):
                    # I can't see how this would happen...
                    raise CacheDeterminismError("Non-deterministic transform detected!\n"
                                                f"Interface `{mname}` has a differing"
                                                " number of files associated with it."
                                                f"{key_text}\n"
                                                f"Old Count: `{len(old_mkeys)}`\n"
                                                f"New Count: `{len(new_mkeys)}`")

                for new_mkey, old_mkey in zip(new_mkeys, old_mkeys):
                    if new_mkey == old_mkey:
                        continue

                    error_dir = self.error_root / (new["mod_name"] + "." + new["cls_name"]) / mname / key
                    shutil.rmtree(error_dir, ignore_errors=True)
                    error_dir.mkdir(exist_ok=True, parents=True)
                    old_error_path = error_dir / old_mkey
                    if not self.fetch_item(old_mkey, old_error_path):
                        # Nothing to debug, just drop it.
                        self.drop_object(mname)
                        continue
                    new_path = mkey_to_path[new_mkey]
                    new_error_path = error_dir / new_mkey
                    new_error_path.symlink_to(new_path,
                                                    target_is_directory=new_path.is_dir())
                    # Hash collision as a result of non-deterministic transform
                    raise CacheDeterminismError("Non-deterministic transform detected!\n"
                                                f"New output for key `{mname}` does not match existing"
                                                " output for same hash.\n"
                                                f"{key_text}\n"
                                                f"Old Output: '{old_error_path}'\n"
                                                f"New Output: '{new_error_path}'")

        raise CacheDeterminismError("Non-deterministic transform detected!\n"
                                    "Unexpected condition.\n"
                                    f"{key_text}")

    def store_transform(self, mkey_to_path: dict[str, Path]) -> bool:
        "Store a transform to the cache"
        for medial_key, medial_path in mkey_to_path.items():
            if self.store_item(medial_key, medial_path):
                continue
            return False
        return True

    def fetch_transform(self, mkey_to_path: dict[str, Path]):
        "Fetch a transform from the cache"
        for medial_key, medial_path in mkey_to_path.items():
            if not self.fetch_item(medial_key, medial_path):
                return False
        return True

    def store_value(self, key: str, value: str) -> bool:
        """
        Try and store a string value by key. Should return True if the value
        is successfully stored or is already present.

        :param key:  The unique item key.
        :param frm:  The string value to be written.
        :return:     True if the item is successfully stored.
        """
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(value)
        result = self.store_item(key, Path(f.name))
        os.unlink(f.name)
        return result

    def drop_value(self, key: str) -> bool:
        """
        Remove a string value from the store by key. Return True if item removed
        successfully.

        :param key:  The unique item key.
        :return:     True if the item is successfully removed
        """
        return self.drop_item(key)

    def fetch_value(self, key: str) -> Optional[str]:
        """
        Fetch a string value from the store by key. Return None if not present.

        :param key:  The unique item key.
        :return:     The fetched string or None if the fetch failed.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data"
            result = self.fetch_item(key, path)
            return path.read_text() if result else None

    def store_object(self, key: str, value: Any) -> bool:
        """
        Try and store a JSON-able object by key. Should return True if the
        object is successfully stored or is already present.

        :param key:  The unique item key.
        :param frm:  The string value to be written.
        :return:     True if the item is successfully stored.
        """
        return self.store_value(key, json.dumps(value))

    def drop_object(self, key: str) -> bool:
        """
        Remove an object from the store by key. Return True if item removed
        successfully.

        :param key:  The unique item key.
        :return:     True if the item is successfully removed
        """
        return self.drop_value(key)

    def fetch_object(self, key: str) -> Optional[Any]:
        """
        Fetch an object from the store by key. Return None if not present.

        :param key:  The unique item key.
        :return:     The fetched string or None if the fetch failed.
        """
        value = self.fetch_value(key)
        if value is None:
            return None
        return json.loads(value)

    @abstractmethod
    def store_item(self, key: str, frm: Path) -> bool:
        """
        Try and store a file or directory by key. Should return True if the
        item is successfully stored or is already present.

        :param key:  The unique item key.
        :param frm:  The location of the item to be copied in.
        :return:     True if the item is successfully stored.
        """
        ...

    def drop_item(self, key: str) -> bool:
        """
        Remove a file or directory from the store. Must be able to handle missing
        files and directories.

        :param key:  The unique item key.
        :return:     True if the item is successfully removed
        """
        return False

    @abstractmethod
    def fetch_item(self, key: str, to: Path) -> bool:
        """
        Retrieve a file or directory from the store, copying it to the path
        provided by `to`. Should return True if the item is successfully
        retreived from the cache.

        :param key:  The unique item key.
        :param to:   The path where the item should be copied to.
        :return:     Whether the item was successfully fetched.
        """
        ...

    def iter_keys(self) -> Iterable[str]:
        """
        Iterate over item keys stored in the cache

        :return: Iterable of item keys in the cache
        """
        yield from []

    def get_last_fetch_utc(self, key: str) -> int | float:
        """
        Get the last fetch time as a UTC timestamp.

        :param key:  The unique item key.
        :return:     The last time an item was fetched as a UTC timestamp.
        """
        return 0

    def set_last_fetch_utc(self, key: str):
        """
        Update the last fetch time as a UTC timestamp.

        :param key:  The unique item key.
        """
        return
