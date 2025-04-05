from collections.abc import Iterable
from dataclasses import field
from pathlib import Path

from blockwork.config.base import Config, ConfigProtocol
from blockwork.transforms import Transform

from ..transforms.bash import BashTF


class Run(Config):
    binary: str | Path
    needs: list[Config] = field(default_factory=list)

    def iter_config(self) -> Iterable[ConfigProtocol]:
        yield from self.needs

    def iter_transforms(self) -> Iterable[Transform]:
        binary = self.api.path(self.binary)
        yield BashTF(binary=binary)
