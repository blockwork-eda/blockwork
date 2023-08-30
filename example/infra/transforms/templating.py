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
from blockwork.build import Interface, Transform
from infra.tools.misc import PythonSite


class MakoTransform(Transform):
    tools = [PythonSite]

    def __init__(self, template: Interface[Path, Path], output: Interface[Path, Path]):
        super().__init__()
        self.bind_inputs(template=template)
        self.bind_outputs(output=output)

    def exec(self, ctx, tools, iface):
        cmd  = "from mako.template import Template;"
        cmd += f"fh = open('{iface.output}', 'w');"
        cmd += f"fh.write(Template(filename='{iface.template}').render());"
        cmd += "fh.flush();"
        cmd += "fh.close()"
        yield tools.pythonsite.get_action("run")(ctx, "-c", cmd)
