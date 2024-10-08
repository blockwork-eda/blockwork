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

import logging
import pprint
import shutil
from pathlib import Path
from typing import ClassVar
from zipfile import ZipFile

import boto3
import botocore

from blockwork.common.singleton import Singleton
from blockwork.context import Context
from blockwork.tools import Invocation, Tool, Version


@Tool.register()
class ObjStore(Tool, metaclass=Singleton):
    versions: ClassVar[list[Version]] = [
        Version(
            location=Tool.HOST_ROOT / "objstore",
            version="latest",
            default=True,
        ),
    ]

    def __init__(self, *args, **kwds) -> None:
        super().__init__(*args, **kwds)
        self._is_setup = False

    def setup(self, ctx: Context) -> "ObjStore":
        if self._is_setup:
            return self
        self._is_setup = True
        # Check if the object store has been configured
        if None in (
            ctx.state.objstore.endpoint,
            ctx.state.objstore.access_key,
            ctx.state.objstore.secret_key,
            ctx.state.objstore.bucket,
        ):
            logging.warning("Object store details need to be configured")
            ctx.state.objstore.endpoint = input("Endpoint URL: ")
            ctx.state.objstore.access_key = input("Access Key  : ")
            ctx.state.objstore.secret_key = input("Secret Key  : ")
            ctx.state.objstore.bucket = input("Bucket      : ")
            logging.info("Object store configured")
        # Create a client
        self.store = boto3.client(
            service_name="s3",
            endpoint_url=ctx.state.objstore.endpoint,
            aws_access_key_id=ctx.state.objstore.access_key,
            aws_secret_access_key=ctx.state.objstore.secret_key,
        )
        # Locally cache the bucket
        self.bucket = ctx.state.objstore.bucket
        # Return self to allow chaining
        return self

    def get_info(self, path: str) -> dict[str, str] | None:
        try:
            return self.store.head_object(Bucket=self.bucket, Key=path)
        except botocore.exceptions.ClientError:
            return None

    def download(self, path: str, target: Path) -> None:
        if not self.get_info(path):
            raise Exception(f"Unknown object: {path}")
        with target.open("wb") as fh:
            self.store.download_fileobj(self.bucket, path, fh)

    @Tool.action("ObjStore")
    def authenticate(self, ctx: Context, *args: list[str]) -> Invocation:
        if len(args) == 4:
            ctx.state.objstore.endpoint = args[0]
            ctx.state.objstore.access_key = args[1]
            ctx.state.objstore.secret_key = args[2]
            ctx.state.objstore.bucket = args[3]
        elif len(args) > 0:
            raise Exception(
                "SYNTAX: bw tool objstore.authenticate <ENDPOINT_URL> <ACCESS_KEY> "
                "<SECRET_KEY> <BUCKET>"
            )
        ObjStore().setup(ctx)
        return None

    @Tool.action("ObjStore")
    def lookup(self, ctx: Context, path: str) -> Invocation:
        ObjStore().setup(ctx)
        if lkp := ObjStore().get_info(path):
            logging.info(
                pprint.pformat(
                    lkp, indent=4, compact=True, width=shutil.get_terminal_size().columns - 20
                )
            )
        else:
            raise Exception(f"No object known for: {path}")


def from_objstore(func):
    def _mock(tool: Tool, ctx: Context, version: Version, *args: list[str]) -> Invocation:
        objname = f"{tool.name.lower()}_{version.version.replace('.', '_')}.zip"
        store = ObjStore().setup(ctx)
        # If the object store doesn't offer this tool, defer to the next installer
        if not store.get_info(objname):
            logging.warning(f"Object store doesn't offer {tool.name} @ {version.version}")
            return func(tool, ctx, version, *args)
        # Download the object
        logging.debug(f"Downloading tool {tool.name} from object store")
        store.download(objname, target := ctx.host_tools / objname)
        # Unpack archive
        logging.debug(f"Unpacking tool {tool.name} into {ctx.host_tools}")
        with ZipFile(target, "r") as zh:
            zh.extractall(ctx.host_tools)
        # Clean-up
        logging.debug("Removing zip archive")
        target.unlink()

    return _mock
