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

from blockwork.build.interface import DictInterface, Interface, TemplateInterface
from blockwork.build.transform import Transform
from blockwork.common.checkeddataclasses import field
from blockwork.config import base
from ..transforms.lint import DesignInterface, VerilatorLintTransform
from ..transforms.templating import BashTransform, MakoTransform

class Site(base.Site):
    pass


class Project(base.Project):
    pass

class Mako(base.Config):
    template: str
    output: str

    def iter_transforms(self):
        yield MakoTransform(
            template=self.api.file_interface(self.template),
            output=self.api.file_interface(self.output)
        )


class Design(base.Config):
    top: str
    sources: list[str]
    transforms: list[Mako] = field(default_factory=list)

    def iter_config(self):
        yield from self.transforms

    def iter_transforms(self) -> Iterable[Transform]:
        idesign = DesignInterface(sources=map(self.api.file_interface, self.sources),
                                  headers=[])
        yield VerilatorLintTransform(idesign)


class Testbench(base.Config):
    design: Design
    bench_python: str
    bench_make: str

    def iter_config(self):
        yield self.design

class FileContent(base.Config):
    path: str
    def to_str_interface(self):
        return self.api.file_interface(self.path).to_content_interface()

class ConfigMetaType(type):
    typ: type
    method: str
    def __instancecheck__(self, instance):
        if isinstance(instance, self.typ):
            return True
        return hasattr(instance, self.method)


class ConfigType(metaclass=ConfigMetaType):
    def __new__(cls, value) -> Interface:
        if isinstance(value, cls.typ):
            return Interface(value)
        else:
            return getattr(value, cls.method)()


class ConfigStr(ConfigType):
    typ = str
    method = 'to_str_interface'


class Template(base.Config):
    text: ConfigStr
    path_fields: dict[str, str]
    text_fields: dict[str, str]

    def to_str_interface(self):
        fields = {k:Interface(v) for k,v in self.text_fields.items()}
        fields.update({k:self.api.file_interface(v) for k,v in self.path_fields.items()})
        text = ConfigStr(self.text)
        return TemplateInterface(text=text, fields=DictInterface(fields))


class Tool(base.Config):
    script: ConfigStr

    def iter_transforms(self) -> Iterable[Transform]:
        script = ConfigStr(self.script)
        yield BashTransform(script=script, workdir=self.api.file_interface('./tool'))

