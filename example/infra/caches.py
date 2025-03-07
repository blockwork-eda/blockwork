import os
from collections.abc import Iterable
from pathlib import Path
from shutil import copy, copytree, rmtree

from blockwork.build.caching import Cache
from blockwork.context import Context


class BasicFileCache(Cache):
    def __init__(self, ctx: Context) -> None:
        self.cache_root = ctx.host_scratch / "cache"
        self.content_store = self.cache_root / "store"
        self.cache_root.mkdir(exist_ok=True)
        self.content_store.mkdir(exist_ok=True)

    @property
    def target_size(self) -> int:
        return 1024**3

    def store_item(self, key: str, frm: Path) -> bool:
        to = self.content_store / key
        if to.exists():
            return True
        if frm.is_dir():
            copytree(frm, to)
        else:
            copy(frm, to)
        return True

    def drop_item(self, key: str) -> bool:
        path = self.content_store / key
        if path.exists():
            if path.is_dir():
                rmtree(path)
            else:
                path.unlink()
        return True

    def fetch_item(self, key: str, to: Path) -> bool:
        to.parent.mkdir(exist_ok=True, parents=True)
        frm = self.content_store / key
        if not frm.exists():
            return False
        try:
            to.symlink_to(frm, target_is_directory=frm.is_dir())
        except FileNotFoundError:
            return False
        return True

    def get_last_fetch_utc(self, key: str) -> float:
        frm = self.content_store / key
        try:
            return frm.stat().st_mtime
        except OSError:
            return 0

    def set_last_fetch_utc(self, key: str):
        frm = self.content_store / key
        if frm.exists():
            frm.touch(exist_ok=True)

    def iter_keys(self) -> Iterable[str]:
        if not self.content_store.exists():
            yield from []
        yield from os.listdir(self.content_store)
