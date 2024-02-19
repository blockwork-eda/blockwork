from collections.abc import Iterable
from pathlib import Path

import pytest

from blockwork.config.api import ConfigApi
from blockwork.context import Context


@pytest.fixture(name="api")
def api(tmp_path: Path) -> Iterable["ConfigApi"]:
    "Fixture to create a basic api object from dummy bw config"
    bw_yaml = tmp_path / ".bw.yaml"
    with bw_yaml.open("w", encoding="utf-8") as fh:
        fh.write("!Blockwork\n" "project: test\n")
    with ConfigApi(Context(tmp_path)) as api:
        yield api
