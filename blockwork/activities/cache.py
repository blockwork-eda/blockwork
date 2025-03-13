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


from pathlib import Path
from pprint import pprint

import click

from ..build.caching import Cache
from ..context import Context


@click.group()
def cache() -> None:
    """
    Cache utilities
    """
    pass


@cache.command(name="read-key")
@click.argument("key", type=click.STRING)
@click.pass_obj
def read_key(ctx: Context, key: str):
    """
    Read transform key data
    """
    data = Cache.fetch_transform_key_data_from_any(ctx, key)
    if data:
        pprint(data)
        exit(0)
    exit(1)


@cache.command(name="fetch-medial")
@click.argument("key", type=click.STRING)
@click.option("--output", "-o", type=click.Path(writable=True, path_type=Path), required=True)
@click.pass_obj
def fetch_medial(ctx: Context, key: str, output: Path):
    """
    Fetch a single medial
    """
    if not key.startswith(Cache.medial_prefix):
        key = Cache.medial_prefix + key
    for cache in ctx.caches:
        if cache.fetch_item(key, output):
            exit(0)
    exit(1)
