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

from .context import Context
from .executors import Container

cntr_dir = Path(__file__).absolute().parent / "containerfiles"


class FoundationError(Exception):
    pass


class Foundation(Container):
    """Standard baseline container for Blockwork"""

    def __init__(self, context: Context, **kwargs) -> None:
        super().__init__(
            context,
            image=f"foundation_{context.host_architecture}_{context.host_root_hash}",
            definition=cntr_dir / "foundation" / f"Containerfile_{context.host_architecture}",
            workdir=context.container_root,
            **kwargs,
        )
        self.bind(self.context.host_scratch, self.context.container_scratch)
        # Ensure various standard $PATHs are present
        self.append_env_path("PATH", "/usr/local/sbin")
        self.append_env_path("PATH", "/usr/local/bin")
        self.append_env_path("PATH", "/usr/sbin")
        self.append_env_path("PATH", "/usr/bin")
        self.append_env_path("PATH", "/sbin")
        self.append_env_path("PATH", "/bin")
        # Provide standard paths as environment variables
        self.set_env("BW_ROOT", context.container_root.as_posix())
        self.set_env("BW_SCRATCH", context.container_scratch.as_posix())
        self.set_env("BW_TOOLS", context.container_tools.as_posix())
        self.set_env("BW_PROJECT", context.config.project)
