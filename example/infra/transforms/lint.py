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
from typing import Sequence

from blockwork.build import Transform
from blockwork.build.interface import Interface
from infra.tools.simulators import Verilator

class VerilatorLintTransform(Transform):
    tools = [Verilator]

    def __init__(self, inputs: Sequence[Interface[Path, Path]]):
        super().__init__()
        self.bind_inputs(inputs=inputs)

    def exec(self, ctx, tools, iface):
        yield tools.verilator.get_action("run")(
            ctx,
            "--lint-only",
            "-Wall",
            *iface.inputs
        )
