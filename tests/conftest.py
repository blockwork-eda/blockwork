from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import pytest

from blockwork.config.api import ConfigApi
from blockwork.context import Context
from blockwork.bootstrap import build_foundation


@pytest.fixture(name="api")
def api(tmp_path: Path) -> Iterable["ConfigApi"]:
    "Fixture to create a basic api object from dummy bw config"
    bw_yaml = tmp_path / ".bw.yaml"
    with bw_yaml.open("w", encoding="utf-8") as fh:
        fh.write("!Blockwork\nproject: test\n")
    ctx = Context(tmp_path)
    build_foundation(ctx, datetime.min)
    with ConfigApi(Context(tmp_path)) as api:
        yield api
