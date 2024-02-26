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
from typing import Any, ClassVar

from infra.tools.misc import PythonSite

from blockwork.common.complexnamespaces import ReadonlyNamespace
from blockwork.context import Context
from blockwork.tools import Tool, Version
from blockwork.transforms import Transform


class CapturedTransform(Transform):
    "Transform with stdout captured to a file interface"

    tools: tuple[Tool, ...] = (PythonSite,)
    output: Path = Transform.OUT(init=True, default=...)

    def execute(
        self,
        ctx: Context,
        tools: ReadonlyNamespace[Version],
        iface: ReadonlyNamespace[Any],
    ):
        output = ctx.map_to_host(iface.output)
        with output.open(mode="w", encoding="utf-8") as stdout:
            inv = tools.pythonsite.get_action("run")(ctx, "-c", "print('hello interface')")
            inv.stdout = stdout
            yield inv
