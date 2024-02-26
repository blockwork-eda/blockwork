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
from typing import Any

from blockwork.transforms import Transform
from blockwork.common.complexnamespaces import ReadonlyNamespace
from blockwork.context import Context
from blockwork.tools.tool import Tool, Version

from ..tools.misc import PythonSite


class MakoTransform(Transform):
    tools: tuple[Tool, ...] = (PythonSite,)
    template: Path = Transform.IN()
    output: Path = Transform.OUT(init=True, default=...)

    def execute(
        self,
        ctx: Context,
        tools: ReadonlyNamespace[Version],
        iface: ReadonlyNamespace[Any],
    ):
        cmd = "from mako.template import Template;"
        cmd += f"fh = open('{iface.output}', 'w');"
        cmd += f"fh.write(Template(filename='{iface.template}').render());"
        cmd += "fh.flush();"
        cmd += "fh.close()"
        yield tools.pythonsite.get_action("run")(ctx, "-c", cmd)
