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

from .container import Container

class Foundation(Container):
    """ Standard baseline container for Blockwork """

    def __init__(self, **kwargs) -> None:
        super().__init__(image="docker.io/library/rockylinux:9.1",
                         workdir=Path("/bw/scratch"),
                         **kwargs)
        cwd = Path.cwd()
        self.bind_readonly(cwd / "bw" / "input")
        self.bind_readonly(cwd / "bw" / "tools")
        self.bind(cwd / "bw" / "output")
        self.bind(cwd / "bw" / "scratch")
