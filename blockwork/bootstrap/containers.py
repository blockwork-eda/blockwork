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
from datetime import datetime
from docker.errors import ImageNotFound
from pathlib import Path

from rich.console import Console

import blockwork
from ..containers.runtime import Runtime
from ..context import Context
from .registry import Bootstrap

root_dir = Path(blockwork.__path__[0]).absolute()
cntr_dir = root_dir / "containerfiles"

# === Foundation Container ===

foundation = cntr_dir / "foundation" / "Containerfile"

@Bootstrap.register()
def build_foundation(context : Context, last_run : datetime) -> bool:
    with Runtime.get_client() as client:
        # Check if the image exists (in case it was removed manually)
        try:
            client.images.get('foundation')
        except ImageNotFound:
            last_run = datetime.min
        # Check that the container file can be found
        if not foundation.exists():
            raise FileExistsError(f"Foundation ContainerFile does not exist at '{foundation}'!")
        # Check if the container file is newer than the last run
        if datetime.fromtimestamp(foundation.stat().st_mtime) <= last_run:
            return True
        # Build the container
        logging.info(f"Building the foundation container from {foundation} - "
                     f"this may take a while...")
        with Console().status("Building container...", spinner="arc"):
            client.images.build(path=foundation.parent.as_posix(),
                                dockerfile="Containerfile",
                                tag="foundation",
                                rm=True)
        logging.info("Foundation container built")
        return False
