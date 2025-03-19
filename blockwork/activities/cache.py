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


import json
from pathlib import Path
from pprint import pprint

import click

from ..build.caching import Cache, TraceData, TransformKeyData
from ..context import Context


@click.group()
def cache() -> None:
    """
    Cache utilities
    """
    pass


def get_key_data(ctx: Context, key: str, from_cache: str | None = None) -> TransformKeyData | None:
    if any(key.startswith(p) for p in ("./", "../", "/")):
        print(f"Assuming key '{key}' is a key_file")

        with Path(key).open("r") as f:
            return json.load(f)

    print(f"Assuming key '{key}' is a cache key (use ./ prefix if this is a file)")
    if not key.startswith(Cache.transform_prefix):
        key = Cache.transform_prefix + key

    for cache in ctx.caches:
        if from_cache is not None and cache.cfg.name != from_cache:
            continue
        data = cache.fetch_object(key)
        if data is not None:
            print(f"Key '{key}' found in cache: '{cache.cfg.name}'")
            return data
    print(f"Key '{key}' not found")
    return None


def format_trace(trace: list[TraceData], depth=0, max_depth=0) -> list[str]:
    lines = []

    for typ, ident, own_hash, rolling_hash, sub_trace in trace:
        lines.append(f"{depth} {rolling_hash}  {own_hash} {depth*'  '} {typ}[{ident}]")
        if max_depth < 0 or depth < max_depth:
            lines.extend(format_trace(sub_trace, depth=depth + 1, max_depth=max_depth))
    return lines


@cache.command(name="read-key")
@click.argument("key", type=click.STRING)
@click.option(
    "--output", "-o", type=click.Path(writable=True, path_type=Path), required=False, default=None
)
@click.option("--cache", "-c", type=click.STRING, required=False, default=None)
@click.pass_obj
def read_key(ctx: Context, key: str, output: Path | None, cache: str):
    """
    Read transform key data
    """
    data = get_key_data(ctx, key, cache)
    if data is None:
        exit(1)

    if output is None:
        pprint(data)
    else:
        with output.open("w") as f:
            json.dump(data, f)
        exit(0)


@cache.command(name="trace-key")
@click.argument("key", type=click.STRING)
@click.option("--depth", "-d", type=click.INT, required=False, default=-1)
@click.option(
    "--output", "-o", type=click.Path(writable=True, path_type=Path), required=False, default=None
)
@click.option("--cache", "-c", type=click.STRING, required=False, default=None)
@click.pass_obj
def trace_key(ctx: Context, key: str, depth: int, output: Path | None, cache: str | None):
    """
    Read transform key data
    """
    data = get_key_data(ctx, key, cache)
    if data is None:
        exit(1)

    if (trace := data.get("trace", None)) is None:
        print("No trace data! Did you run with '--cache-trace'?")
        exit(1)

    format_trace(trace, max_depth=depth)

    trace_lines = format_trace(trace, max_depth=depth)
    if output is None:
        for line in trace_lines:
            print(line)
    else:
        with output.open("w") as f:
            for line in trace_lines:
                f.write(line + "\n")
    exit(0)


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
            print(f"Item found in cache: '{cache.cfg.name}'")
            exit(0)
    exit(1)


@cache.command(name="drop-key")
@click.argument("key", type=click.STRING)
@click.option("--yes", "-y", default=False, is_flag=True)
@click.pass_obj
def drop_key(ctx: Context, key: str, yes: bool):
    """
    Drop transform key data
    """
    if not key.startswith(Cache.transform_prefix):
        key = Cache.transform_prefix + key
    exit_code = 0
    for cache in ctx.caches:
        if yes or click.confirm(f"Drop key from cache '{cache.cfg.name}'?", default=False):
            if cache.drop_item(key):
                print(f"Item dropped from cache: '{cache.cfg.name}'")
            else:
                print(f"Item could not be dropped from cache: '{cache.cfg.name}'")
                exit_code = 1
    exit(exit_code)


@cache.command(name="drop-medial")
@click.argument("key", type=click.STRING)
@click.option("--yes", "-y", default=False, is_flag=True)
@click.pass_obj
def drop_medial(ctx: Context, key: str, yes: bool):
    """
    Fetch a single medial
    """
    if not key.startswith(Cache.medial_prefix):
        key = Cache.medial_prefix + key
    exit_code = 0
    for cache in ctx.caches:
        if yes or click.confirm(f"Drop key from cache '{cache.cfg.name}'?", default=False):
            if cache.drop_item(key):
                print(f"Item dropped from cache: '{cache.cfg.name}'")
            else:
                print(f"Item could not be dropped from cache: '{cache.cfg.name}'")
                exit_code = 1
    exit(exit_code)
