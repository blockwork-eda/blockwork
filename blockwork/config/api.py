from abc import ABC
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Generic, Optional, TypeVar, cast

import yaml

from ..common.scopes import Scope

if TYPE_CHECKING:
    from ..context import Context
    from ..transforms import Transform
    from .base import Config, Project, Site


class ApiAccessError(Exception):
    def __init__(self, api: str):
        super().__init__(
            f"Tried to access unavailable api `{api}` try creating a fork using `with_{api}(...)`"
        )


class ConfigApi(Scope):
    """
    Api for configuration objects to access wider information.

    Intended to be created using just ctx and extended with the with_* methods.
    """

    def __init__(
        self,
        ctx: "Context",
        site: Optional["SiteApi"] = None,
        project: Optional["ProjectApi"] = None,
        target: Optional["TargetApi"] = None,
        node: Optional["NodeApi"] = None,
        transform: Optional["TransformApi"] = None,
    ) -> None:
        self.ctx = ctx
        self._site = site
        self._project = project
        self._target = target
        self._node = node
        self._transform = transform

    def __call__(self, fn):
        "Allow to be used as a decorator"

        def decorated(*args, **kwargs):
            with self:
                return fn(*args, **kwargs)

        return decorated

    def node_id(self) -> int | None:
        "The unique id for the node"
        if self._node:
            return hash(self.node.pos)
        return None

    class FORK_UNSET:  # noqa: N801
        ...

    def fork(
        self,
        site: "type[FORK_UNSET] | SiteApi | None" = FORK_UNSET,
        project: "type[FORK_UNSET] | ProjectApi | None" = FORK_UNSET,
        target: "type[FORK_UNSET] | TargetApi | None" = FORK_UNSET,
        node: "type[FORK_UNSET] | NodeApi | None" = FORK_UNSET,
        transform: "type[FORK_UNSET] | TransformApi | None" = FORK_UNSET,
    ):
        "Create a new api object from this one"
        forked_site = self._site if site is self.FORK_UNSET else site
        forked_project = self._project if project is self.FORK_UNSET else project
        forked_target = self._target if target is self.FORK_UNSET else target
        forked_node = self._node if node is self.FORK_UNSET else node
        forked_transform = self._transform if transform is self.FORK_UNSET else transform
        return ConfigApi(
            ctx=self.ctx,
            site=cast(SiteApi, forked_site),
            project=cast(ProjectApi, forked_project),
            target=cast(TargetApi, forked_target),
            node=cast(NodeApi, forked_node),
            transform=cast(TransformApi, forked_transform),
        )

    def with_site(self, path, typ):
        "Extend with a site api"
        return SiteApi(self, path, typ).api

    def with_project(self, spec, typ):
        "Extend with a project api"
        return ProjectApi(self, spec, typ).api

    def with_node(self, node: yaml.Node):
        "Extend with a node api"
        return NodeApi(self, node).api

    def with_target(self, spec: str, typ: "type[Config]"):
        "Extend with a target api"
        return TargetApi(self, spec, typ).api

    def with_transform(self, transform: "Transform"):
        "Extend with a transform api"
        return TransformApi(self, transform).api

    @property
    def site(self):
        if self._site is None:
            raise ApiAccessError("site")
        return self._site

    @property
    def project(self):
        if self._project is None:
            raise ApiAccessError("project")
        return self._project

    @property
    def target(self):
        if self._target is None:
            raise ApiAccessError("target")
        return self._target

    @property
    def node(self):
        if self._node is None:
            raise ApiAccessError("node")
        return self._node

    @property
    def transform(self):
        if self._transform is None:
            raise ApiAccessError("transform")
        return self._transform

    def path(self, path: str | Path) -> Path:
        if self._transform:
            return self._transform.path(path)
        if self._target:
            return self._target.path(path)
        return Path(path).absolute()


ConfigType = TypeVar("ConfigType")


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
        self.config_path = path
        with self.api:
            self._config = typ.parser.parse(self.config_path)


class ProjectApi(ConfigApiBase["Project"]):
    def __init__(self, api: ConfigApi, spec: str, typ: "type[Project]") -> None:
        self.api = api.fork(project=self, target=None)
        self.name = spec
        self.config_path = self.find_config(self.name)
        with self.api:
            self._config = typ.parser.parse(self.config_path)

    def find_config(self, name):
        return self.api.ctx.host_root / self.api.site.config.projects[name]


class TargetApi(ConfigApiBase["Config"]):
    def __init__(self, api: ConfigApi, spec: str, typ: "type[Config]") -> None:
        self._context_unit = None if api._target is None else api._target.unit
        self.api = api.fork(target=self)
        self.unit, self.target = self.split_spec(spec)
        self.config_path = self.find_config(self.unit, self.target, typ)
        with self.api:
            self._config = typ.parser.parse(self.config_path)

        self.project_path = self.api.ctx.host_root / self.api.project.config.units[self.unit]
        self.scratch_path = (
            self.api.ctx.host_scratch
            / self.api.project.config.units[self.unit]
            / self.api.ctx.timestamp
        )

    def split_spec(self, spec: str):
        """
        Parse a target config file based on the target unit, path within that
        unit and expected type

        :param spec: The target specified as `<unit>:<path>` or `<path>`
                     where path is the path within the unit to the yaml,
                     not including the extension. The <unit> component
                     is inferred where possible.
        """
        target_parts = spec.split(":")
        if len(target_parts) == 2:
            # Path and unit specified as `<unit>:<path>`, `:<path>`, or `:`
            unit, target = target_parts
            if not target:
                raise RuntimeError(
                    f"Invalid target specification `{spec}` (trailing `:` after unit)"
                )
        elif len(target_parts) == 1:
            # Unit specified as `<unit>` or ``
            unit, target = target_parts[0], ""
        else:
            raise RuntimeError(f"Invalid target specification `{spec}` (too many `:`)")

        # If given empty unit, infer here.
        if unit == "":
            if self._context_unit is not None:
                unit = self._context_unit
            else:
                raise RuntimeError(f"Require implicit unit for `{spec}`, but not in unit context!")
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
        implicit_file_name = typ.FILE_NAME or typ.YAML_TAG or typ.__name__.lower()

        # Get the path to the config file
        unit_path = self.api.ctx.host_root / self.api.project.config.units[unit]
        directory_path = unit_path / target / f"{implicit_file_name}.yaml"
        file_path = unit_path / f"{target or implicit_file_name}.yaml"
        if directory_path.exists():
            config_path = directory_path
        elif file_path.exists():
            config_path = file_path
        else:
            raise RuntimeError(
                f"Config not found for {unit}:{target} at either "
                f"`{directory_path}` or `{file_path}`"
            )
        return config_path

    def path(self, path: str | Path):
        project_path = self.project_path / path
        scratch_path = self.scratch_path / path
        return project_path if project_path.exists() else scratch_path


class NodeApi:
    def __init__(self, api: ConfigApi, node: yaml.Node) -> None:
        self.api = api.fork(node=self)
        self.node = node
        self.pos = ":".join(
            map(
                str,
                (
                    Path(node.start_mark.name).absolute(),
                    node.start_mark.line,
                    node.start_mark.column,
                ),
            )
        )


class TransformApi:
    def __init__(self, api: ConfigApi, transform: "Transform") -> None:
        self.api = api.fork(transform=self)
        self.transform = transform
        now = datetime.now().strftime("D%Y%m%dT%H%M%S")
        self.id = f"{type(transform).__name__}-{now}-{id(transform)}"

    def path(self, path: str | Path) -> Path:
        if target := self.api._target:
            return target.scratch_path / self.id / path
        # Attempt to include the project and target in the path
        try:
            return (
                self.api.ctx.host_scratch
                / self.api.project.config.units[self.api.target.unit]
                / self.id
                / path
            )
        # Fall back to using the transform's ID
        except ApiAccessError:
            return self.api.ctx.host_scratch / self.id / path
