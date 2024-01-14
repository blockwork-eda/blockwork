from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar
import yaml


from ..common.scopedapi import ScopedApi

if TYPE_CHECKING:
    from .base import Project, Config, Site
    from ..context import Context

from ..build.interface import FileInterface, SplitFileInterface

class ApiAccessError(Exception):
    def __init__(self, api: str):
        super().__init__(f"Tried to access unavailable api `{api}` try creating a fork using `with_{api}(...)`")

class ConfigApi(ScopedApi):
    '''
    Api for configuration objects to access wider information.
    
    Intended to be created using just ctx and extended with the with_* methods.
    '''
    ctx: "Context"
    site: "SiteApi"
    project: "ProjectApi"
    target: "TargetApi"
    node: "NodeApi"

    def node_id(self) -> int | None:
        'The unique id for the node'
        if (node := self.get('node', None)):
            return hash(node.pos)
        return None
            
    def with_site(self, path, typ):
        'Extend with a site api'
        return SiteApi(self, path, typ).api

    def with_project(self, spec, typ):
        'Extend with a project api'
        return ProjectApi(self, spec, typ).api
    
    def with_node(self, node: yaml.Node):
        'Extend with a node api'
        return NodeApi(self, node).api

    def with_target(self, spec: str, typ: "type[Config]"):
        'Extend with a target api'
        return TargetApi(self, spec, typ).api

    def file_interface(self, path: str|Path):
        if 'target' in self:
            return self.target.file_interface(path)
        return FileInterface(path)

ConfigType = TypeVar('ConfigType')
class ConfigApiBase(Generic[ConfigType], ABC):
    _config: "ConfigType"
    @property
    def config(self) -> ConfigType:
        if self._config is None:
            raise RuntimeError("Tried to access config before it is initialised!")
        return self._config

class SiteApi(ConfigApiBase["Site"]):
    def __init__(self, api: ConfigApi, path: Path, typ: "type[Site]") -> None:
        self.api = api.fork(site=self, project=None, target=None)
        self.path = path
        with self.api:
            self._config = typ.parser.parse(self.path)

class ProjectApi(ConfigApiBase["Project"]):
    def __init__(self, api: ConfigApi, spec: str, typ: "type[Project]") -> None:
        self.api = api.fork(project=self, target=None)
        self.name = spec
        self.path = self.find_config(self.name)
        with self.api:
            self._config = typ.parser.parse(self.path)

    def find_config(self, name):
        return self.api.ctx.host_root / self.api.site.config.projects[name]

class TargetApi(ConfigApiBase["Config"]):
    def __init__(self, api: ConfigApi, spec: str, typ: "type[Config]") -> None:
        self._context_unit = api.target.unit if 'target' in api else None
        self.api = api.fork(target=self)
        self.unit, self.target = self.split_spec(spec)
        self.path = self.find_config(self.unit, self.target, typ)
        with self.api:
            self._config = typ.parser.parse(self.path)

        self.project_path = self.api.ctx.host_root / self.api.project.config.units[self.unit]
        self.scratch_path = (self.api.ctx.host_scratch / 
                             self.api.ctx.timestamp / 
                             self.api.project.config.units[self.unit])

    def split_spec(self, spec: str):
        """
        Parse a target config file based on the target unit, path within that 
        unit and expected type

        :param spec: The target specified as `<unit>:<path>` or `<path>` 
                     where path is the path within the unit to the yaml,
                     not including the extension. The <unit> component
                     is inferred where possible.
        """
        target_parts = spec.split(':')
        if len(target_parts) == 2:
            # Path and unit specified as `<unit>:<path>`, `:<path>`, or `:`
            unit, target = target_parts
            if not target:
                 raise RuntimeError(f'Invalid target specification `{spec}` (trailing `:` after unit)')
        elif len(target_parts) == 1:
            # Unit specified as `<unit>` or ``
            unit, target = target_parts[0], ''
        else:
            raise RuntimeError(f'Invalid target specification `{spec}` (too many `:`)')

        # If given empty unit, infer here.
        if unit == '':
            if self._context_unit is not None:
                unit = self._context_unit
            else:
                raise RuntimeError(f'Require implicit unit for `{spec}`, but not in unit context!')
        return unit, target

    def find_config(self, unit, target, typ):
        """
        Parse a target config file based on the target unit, path within that 
        unit and expected type
        :param unit: The unit within which the target exists
        :param target: The target path within the unit
        :param typ: Expected element type
        """
        # The target should be either referring to a directory (in which case the
        # filename will be implicit based on the target type), or a file.
        implicit_file_name = (typ.FILE_NAME or
                              typ.YAML_TAG or
                              typ.__name__.lower())

        # Get the path to the config file
        unit_path = self.api.ctx.host_root / self.api.project.config.units[unit]
        directory_path = unit_path / target / f"{implicit_file_name}.yaml"
        file_path = unit_path / f"{target or implicit_file_name}.yaml"
        if directory_path.exists():
            config_path = directory_path
        elif file_path.exists():
            config_path = file_path
        else:
            raise RuntimeError(f'Config not found for {unit}:{target} at either `{directory_path}` or `{file_path}`')
        return config_path

    def file_interface(self, path: str | Path):
        return SplitFileInterface(input_path=self.project_path / path,
                                  output_path=self.scratch_path / path,
                                  key=(self.unit, path))

class NodeApi:
    def __init__(self, api: ConfigApi, node: yaml.Node) -> None:
        self.api = api.fork(node=self)
        self.node = node
        self.pos = f"{Path(node.start_mark.name).absolute()}:{node.start_mark.line}:{node.start_mark.column}"
