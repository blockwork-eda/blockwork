Caching allows build outputs to be re-used across workflow runs. In Blockwork
caching is used to:

 - Save compute: Builds don't need to be repeated
 - Save disk-space: Identical objects can be de-duplicated
 - Save developer-time: Re-building only changed items
 - Ensure build determinism: Checking the same inputs always produce the same
    output

See [Caching](../config/caching.md) for details on how to configure caches, or
read on for details on how to implement your own Blockwork caches, or how the
caching scheme works.

## Implementing a Cache

A custom cache can be implemented by inheriting from the base Cache class and
implementing a minimal set of methods. A minimal implementation which stores
into a local directory is:

```python
from collections.abc import Iterable
from filelock import FileLock
from pathlib import Path
from shutil import copy, copytree

from blockwork.build.caching import Cache
from blockwork.config import CacheConfig
from blockwork.context import Context


class BasicFileCache(Cache):
    def __init__(self, ctx: Context, cfg: CacheConfig) -> None:
        super().__init__(ctx, cfg) # Super must be called!
        self.cache_root: Path = ctx.host_scratch / "my-cache"
        self.cache_root.mkdir(exist_ok=True)
        self.lock = FileLock(self.cache_root.with_suffix(".lock"))

    def store_item(self, key: str, frm: Path) -> bool:
        with self.lock:
            to = self.cache_root / key
            if to.exists():
                # Two different key hashes resulted in the same content hash,
                # item has already been stored
                return True
            to.parent.mkdir(exist_ok=True, parents=True)
            if frm.is_dir():
                copytree(frm, to)
            else:
                copy(frm, to)
        return True

    def fetch_item(self, key: str, to: Path) -> bool:
        to.parent.mkdir(exist_ok=True, parents=True)
        frm = self.cache_root / key
        if not frm.exists():
            return False
        try:
            to.symlink_to(frm, target_is_directory=frm.is_dir())
        except FileNotFoundError:
            return False
        return True
```

This implementation will give you a local cache which is safe for running in
parallel (the lock could be removed if only running serially).

However, without implementing some of the optional methods this cache will grow
indefinitely. To allow the cache to self prune, some extra methods must be
implemented:

```python
    def drop_item(self, key: str) -> bool:
        with self.lock:
            path = self.cache_root / key
            if path.exists():
                if path.is_dir():
                    rmtree(path)
                else:
                    path.unlink()
        return True

    def iter_keys(self) -> Iterable[str]:
        if not self.cache_root.exists():
            yield from []
        yield from self.cache_root.iterdir()
```

This allows the cache to prune itself down to the maximum size as expressed in
the cache configuration. It will prune itself at the end of each workflow
by calculating a score for each item based on `time-to-create / size` and
removing items from lowest to highest score until the max-size is reached.

A final enhancement enables intelligent pruning based on how recently an item
was used by including a `time-since-last-use` term. This can be enabled by
implementing a final pair of methods as follows:

```python
    def get_last_fetch_utc(self, key: str) -> float:
        frm = self.cache_root / key
        try:
            return frm.stat().st_mtime
        except OSError:
            return 0

    def set_last_fetch_utc(self, key: str):
        frm = self.cache_root / key
        if frm.exists():
            frm.touch(exist_ok=True)
```

## Caching Scheme

Blockwork's cache scheme calculates two types of hash:

 - Transform hashes: Calculated by hashing a transform's definition with the
    definition of its dependencies recursively. This can be calculated before
    any transforms have been run.
 - File hashes: Calculated by hashing a transform file-output, which can only
    be done after the transform has run.

After a transform is run, the output-files are stored in the cache according
to their hash, and a key-file containing each output hash is stored according
to the transform hash.

This two level scheme allows many transforms to refer to the same cached file,
preventing unnecessary copies being stored.

### Process

Stages:

  - Initial:
    - Hash the content of static input interfaces
    - Use these to compute transform hashkeys for nodes with no dependencies
    - Use input interface names along with the hashkeys of transforms that
        output them to get the transform hashkeys for nodes with dependencies

  - Pre-run:
    - Go through the transforms in reverse order
    - Try and pull all output interfaces from caches - if successful mark that
        transform as fetched.
    - If all dependents of a transform are fetched, mark a transform as skipped

  - During-run:
    - Go through transforms in dependency order as usual
    - Skip transforms marked as fetched or skipped
    - Push output interfaces to all caches that allow it
