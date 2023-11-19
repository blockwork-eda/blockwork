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

from blockwork.build.interface import DictInterface, Interface, MetaInterface, TemplateInterface
from blockwork.build.transform import Transform
from blockwork.common.checkeddataclasses import field
from blockwork.common.into import Into
from blockwork.config import base
from blockwork.config.base import Config
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

ConfigStr = Into[Interface[str]]

@ConfigStr.converter(FileContent)
def converter(fc: FileContent) -> Interface[str]:
    return fc.api.file_interface(fc.path).to_content_interface()

@ConfigStr.converter(str)
def converter(text: str) -> Interface[str]:
    return Interface(text)

class Template(base.Config):
    template: ConfigStr
    text_in: dict[str, str] = field(default_factory=dict)
    files_in: dict[str, str] = field(default_factory=dict)
    dirs_in: dict[str, str] = field(default_factory=dict)
    files_out: dict[str, str] = field(default_factory=dict)
    dirs_out: dict[str, str] = field(default_factory=dict)

@ConfigStr.converter(Template)
def converter(cfg: Template) -> Interface[str]:
    in_fields = {}
    out_fields = {}
    in_fields.update({k:Interface(v) for k,v in cfg.text_in.items()})
    in_fields.update({k:cfg.api.file_interface(v) for k,v in cfg.files_in.items()})
    in_fields.update({k:cfg.api.file_interface(v, is_dir=True) for k,v in cfg.dirs_in.items()})
    out_fields.update({k:cfg.api.file_interface(v) for k,v in cfg.files_out.items()})
    out_fields.update({k:cfg.api.file_interface(v, is_dir=True) for k,v in cfg.dirs_out.items()})
    return TemplateInterface(template=ConfigStr(cfg.template), 
                             in_fields=DictInterface(in_fields),
                             out_fields=DictInterface(out_fields))




class Command(base.Config):
    command: ConfigStr
    workdir: str = './workdir'
    tools: list[str] = field(default_factory=list)
    def iter_transforms(self) -> Iterable[Transform]:
        command = ConfigStr(self.command)
        yield BashTransform(command=command,
                            workdir=self.api.file_interface(self.workdir, is_dir=True),
                            tools=self.tools)


class Tool(base.Config):
    # script: ConfigStr
    # workdir: str | None = './tool'
    commands: list[Command] = field(default_factory=list)

    def iter_config(self) -> Iterable[Config]:
        yield from self.commands
        # return super().iter_config()
    # outputs: dict[str, str] = field(default_factory=dict)
    # def iter_transforms(self) -> Iterable[Transform]:
    #     script = ConfigStr(self.script)
    #     workdir = self.api.file_interface(self.workdir)
    #     # op = DictInterface({k:self.api.file_interface(v) for k,v in self.outputs.items()})
    #     yield BashTransform(script=script, workdir=workdir)

