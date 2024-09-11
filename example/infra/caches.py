from pathlib import Path
from shutil import copy, copytree, rmtree

from blockwork.build.caching import Cache
from blockwork.context import Context


class BasicFileCache(Cache):
    def __init__(self, ctx: Context) -> None:
        self.cache_root = ctx.host_scratch / "cache"
        self.key_store = self.cache_root / "key_store"
        self.content_store = self.cache_root / "content_store"
        self.cache_root.mkdir(exist_ok=True)
        self.key_store.mkdir(exist_ok=True)
        self.content_store.mkdir(exist_ok=True)

    def store_hash(self, key_hash: str, content_hash: str) -> bool:
        (self.key_store / key_hash).write_text(content_hash)
        return True

    def drop_hash(self, key_hash: str) -> bool:
        (self.key_store / key_hash).unlink(missing_ok=True)
        return True

    def fetch_hash(self, key_hash: str) -> str | None:
        try:
            return (self.key_store / key_hash).read_text()
        except FileNotFoundError:
            return None

    def store_item(self, content_hash: str, frm: Path) -> bool:
        to = self.content_store / content_hash
        if to.exists():
            return True
        if frm.is_dir():
            copytree(frm, to)
        else:
            copy(frm, to)
        return True

    def drop_item(self, content_hash: str) -> bool:
        path = self.content_store / content_hash
        if path.exists():
            if path.is_dir():
                rmtree(path)
            else:
                path.unlink()
        return True

    def fetch_item(self, content_hash: str, to: Path) -> bool:
        to.parent.mkdir(exist_ok=True, parents=True)
        frm = self.content_store / content_hash
        try:
            if frm.is_dir():
                copytree(frm, to)
            else:
                copy(frm, to)
        except FileNotFoundError:
            return False
        return True
