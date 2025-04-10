from pathlib import Path
from typing import ClassVar

from blockwork.build import Entity


@Entity.register()
class Top(Entity):
    files: ClassVar[list[Path]] = [
        Entity.ROOT / "adder.sv",
        Entity.ROOT / "counter.sv",
        Entity.ROOT / "top.sv.mako",
    ]
