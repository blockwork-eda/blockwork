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

from typing import Iterable
from blockwork.build.transform import Transform
from blockwork.workflows import Workflow
from .transforms.lint import VerilatorLintTransform
from .config.config import Design, Site, Project


@Workflow.register()
class Build(Workflow):
    SITE_TYPE = Site
    PROJECT_TYPE = Project

    def transform_filter(self, transforms: Iterable[Transform]) -> Iterable[Transform]:
        yield from transforms

@Workflow.register()
class Lint(Workflow):
    SITE_TYPE = Site
    PROJECT_TYPE = Project
    TARGET_TYPE = Design

    def transform_filter(self, transforms: Iterable[Transform]) -> Iterable[Transform]:
        for transform in transforms:
            if isinstance(transform, VerilatorLintTransform):
                yield transform
