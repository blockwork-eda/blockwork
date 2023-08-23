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

from blockwork.workflows import Workflow
from ..config.config import Site, Project, Design, Testbench


@Workflow.register()
class Lint(Workflow):
    SITE_TYPE = Site
    PROJECT_TYPE = Project
    TARGET_TYPE = Design

    def exec(self):
        # Dummy for now
        pass

@Workflow.register()
class Sim(Workflow):
    SITE_TYPE = Site
    PROJECT_TYPE = Project
    TARGET_TYPE = Testbench

    def exec(self):
        # Dummy for now
        pass

