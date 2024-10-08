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

import functools
import inspect
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from contextlib import contextmanager
from enum import StrEnum, auto
from pathlib import Path
from typing import Any, ClassVar, NoReturn, TextIO, TypeVar, Union

from ..common.registry import RegisteredClass
from ..context import Context

_TDefault = TypeVar("_TDefault")


class ToolMode(StrEnum):
    READONLY = auto()
    READWRITE = auto()


class ToolError(Exception):
    pass


class ToolActionError(ToolError):
    "Tool doesn't have requested action"


class Require:
    """Forms a requirement on another tool and version"""

    def __init__(self, tool: type["Tool"], version: str | None = None) -> None:
        self.tool_cls = tool
        self.version = version
        if not inspect.isclass(tool) or not issubclass(tool, Tool):
            raise ToolError("Requirement tool must be of type Tool")
        if (self.version is not None) and not isinstance(self.version, str):
            raise ToolError("Requirement version must be None or a string")

    @property
    @functools.lru_cache  # noqa B019
    def tool(self) -> "Tool":
        return self.tool_cls(self.version)


class Version:
    """Defines a version of a tool"""

    def __init__(
        self,
        version: str,
        location: Path,
        env: dict[str, str] | None = None,
        paths: dict[str, list[str]] | None = None,
        requires: list[Require] | None = None,
        default: bool = False,
    ) -> None:
        self.version = version
        self.location = location
        self.env = env or {}
        self.paths = paths or {}
        self.requires = requires
        self.default = default
        self.tool_cls: type["Tool"] | None = None
        # Sanitise arguments
        self.requires = self.requires or []
        self.paths = self.paths or {}
        self.env = self.env or {}
        if not isinstance(self.location, Path):
            raise ToolError(f"Bad location given for version {self.version}: {self.location}")
        if not isinstance(self.version, str) or len(self.version.strip()) == 0:
            raise ToolError("A version must be specified")
        if not isinstance(self.paths, dict):
            raise ToolError("Paths must be specified as a dictionary")
        if not all(isinstance(k, str) and isinstance(v, list) for k, v in self.paths.items()):
            raise ToolError("Path keys must be strings and values must be lists")
        if not all(isinstance(y, str | Path) for x in self.paths.values() for y in x):
            raise ToolError("Path entries must be of type str or pathlib.Path")
        if not isinstance(self.default, bool):
            raise ToolError("Default must be either True or False")
        if not isinstance(self.requires, list):
            raise ToolError("Requirements must be a list")
        if not all(isinstance(x, Require) for x in self.requires):
            raise ToolError("Requirements must be a list of Require objects")

    @property
    @functools.lru_cache  # noqa: B019
    def id_tuple(self) -> str:
        return (*self.tool_cls.base_id_tuple, self.version)

    @property
    @functools.lru_cache  # noqa: B019
    def tool(self) -> "Tool":
        return self.tool_cls(self.version)

    @property
    @functools.lru_cache  # noqa: B019
    def id(self) -> str:
        vend, name, vers = self.id_tuple
        if vend.casefold() == Tool.NO_VENDOR.casefold():
            return "_".join((name, vers))
        else:
            return "_".join((vend, name, vers))

    @functools.lru_cache  # noqa: B019
    def resolve_requirements(self) -> set["Version"]:
        return {x.tool.version for x in self.requires}

    @property
    def path_chunk(self) -> Path:
        if self.tool_cls.vendor is not Tool.NO_VENDOR:
            return Path(self.tool_cls.vendor.lower()) / self.tool_cls.name / self.version
        else:
            return Path(self.tool_cls.name) / self.version

    def get_action(self, name: str) -> Callable:
        return self.tool.get_action(name)

    def get_installer(self) -> Callable | None:
        return self.tool.get_installer()

    def __getattribute__(self, name: str) -> Any:
        try:
            return super().__getattribute__(name)
        except AttributeError as e:
            try:
                return self.get_action(name)
            except ToolActionError:
                raise e from None


class Tool(RegisteredClass):
    """Base class for tools"""

    # Tool root locator
    CNTR_ROOT: Path = Path("/__tool_cntr_root__")
    HOST_ROOT: Path = Path("/__tool_host_root__")

    # Default vendor
    NO_VENDOR = "N/A"

    # Touch file name
    TOUCH_FILE: str = "bw.touch"

    # Action registration
    ACTIONS: ClassVar[dict[str, Callable]] = defaultdict(dict)
    RESERVED = ("installer", "default")

    # Placeholders
    vendor: str | None = None
    versions: Sequence[Version] | None = None

    @classmethod
    @functools.lru_cache
    def _validate(cls) -> None:
        cls.vendor = cls.vendor.strip() if isinstance(cls.vendor, str) else Tool.NO_VENDOR
        cls.versions = cls.versions or []
        if not isinstance(cls.versions, list | tuple):
            raise ToolError(f"Versions of tool {cls.name} must be a list or a tuple")
        if not all(isinstance(x, Version) for x in cls.versions):
            raise ToolError(f"Versions of tool {cls.name} must be a list of Version objects")
        # If only one version is defined, make that the default
        if len(cls.versions) == 1:
            cls.versions[0].default = True
            cls.versions[0].tool_cls = cls
            cls.default = cls.versions[0]
        else:
            # Check for collisions between versions and multiple defaults
            default_version = None
            version_nums = []
            for version in cls.versions:
                version.tool_cls = cls
                # Check for multiple defaults
                if version.default:
                    if default_version is not None:
                        raise ToolError(
                            f"Multiple versions marked default for tool {cls.name} "
                            f"from vendor {cls.vendor}"
                        )
                    default_version = version
                # Check for repeated version numbers
                if version.version in version_nums:
                    raise ToolError(
                        f"Duplicate version {version.version} for tool "
                        f"{cls.name} from vendor {cls.vendor}"
                    )
                version_nums.append(version.version)
            # Check the default has been identified
            if default_version is None:
                raise ToolError(
                    f"No version of tool {cls.name} from vendor " f"{cls.vendor} marked as default"
                )
            cls.default = default_version

    def __init_subclass__(cls, *args, **kwargs):
        super().__init_subclass__(*args, **kwargs)
        # Validate cls properties on class creation
        cls._validate()
        return super().__init_subclass__()

    def __init__(self, version: str | None = None) -> None:
        self.version = self.get_version(version, self.default)

    def __iter__(self) -> Iterable[Version]:
        yield from self.versions

    @classmethod
    @property
    @functools.lru_cache
    def name(cls) -> str:
        return cls.__name__.lower()

    @classmethod
    @property
    @functools.lru_cache
    def base_id_tuple(cls) -> str:
        return (cls.vendor.lower(), cls.name)

    @classmethod
    @property
    @functools.lru_cache
    def base_id(cls) -> str:
        vend, name = cls.base_id_tuple
        if vend.casefold() == Tool.NO_VENDOR.casefold():
            return name
        else:
            return "_".join((vend, name))

    @property
    def vernum(self) -> str:
        return self.version.version

    @property
    def location(self) -> Path:
        return self.version.location

    @classmethod
    @functools.lru_cache
    def get_version(cls, version: str | None, default: _TDefault = NoReturn) -> Version | _TDefault:
        """
        Retrieve a specific version of a tool from the version name.

        :param version: Version name
        :returns:       Matching Version instance, or None if it doesn't exist
        """
        if version is None:
            return cls.default
        match = [x for x in cls.versions if x.version == version]
        if match:
            return match[0]
        if default is NoReturn:
            raise KeyError(f"Invalid version `{version}` for tool `{cls.name}`")
        return default

    @classmethod
    def action(cls, tool_name: str, name: str | None = None, default: bool = False) -> Callable:
        """
        Decorator to mark a Tool method as an action, which can be called either
        by other tools or from the command line.

        :param tool_name:   Name of the tool, which should match the class name
                            of the tool. This must be provided as an argument as
                            unbound methods do not have a relationship to their
                            parent.
        :param name:        Optional name of the action, if not provided then
                            the name of the function will be used
        :param default:     Whether to also associate this as the default action
                            for the tool
        """

        def _inner(method: Callable) -> Callable:
            nonlocal name
            name = name or method.__name__
            # Check that the name is not reserved
            if name.lower() in cls.RESERVED:
                raise ToolError(
                    f"Cannot register an action called '{name}' to "
                    f"tool '{tool_name}' as it is a reserved name"
                )
            # Register the action
            cls.__register_action(tool_name, name, default, method)
            # Return the unaltered method
            return method

        return _inner

    @classmethod
    def installer(cls, tool_name: str) -> Callable:
        """
        Special decorator to mark an action that installs the tool by downloading
        it from a central store.

        :param tool_name:   Name of the tool, which should match the class name
                            of the tool. This must be provided as an argument as
                            unbound methods do not have a relationship to their
                            parent.
        """

        def _inner(method: Callable) -> Callable:
            # Register method with a fixed name of 'installer' (reserved)
            cls.__register_action(tool_name, "installer", False, method)
            # Return the unaltered method
            return method

        return _inner

    @classmethod
    def __register_action(cls, tool_name: str, name: str, default: bool, method: Callable):
        """
        Register a provided method as a tool action with a given name, optionally
        marking it as the 'default'.

        :param tool_name:   Name of the tool, which should match the class name
                            of the tool
        :param name:        Name of the action
        :param default:     Whether to also associate this as the default action
                            for the tool
        :param method:      The method implementing the action
        """
        tool_name = tool_name.lower()
        name = name.lower()
        # Raise an error if the name clashes
        if name in cls.ACTIONS[tool_name]:
            raise ToolError(
                f"An action called '{name}' already been registered " f"to tool '{tool_name}'"
            )
        # Register the action as specified
        cls.ACTIONS[tool_name][name] = method
        # If marked as default, call recursively
        if default:
            cls.__register_action(tool_name, "default", False, method)

    def get_action(self, name: str) -> Callable:
        """
        Return an action registered for this tool if known.

        :param name:    Name of the action
        :returns:       The instance wrapped decorated method if known, else excepts
        """
        tool_cls = type(self)
        tool_name = tool_cls.__name__.lower()
        if (actions := tool_cls.ACTIONS.get(tool_name, None)) is None:
            raise ToolActionError
        if (raw_act := actions.get(name.lower(), None)) is None:
            raise ToolActionError

        # The method held in the actions dictionary is unbound, so this wrapper
        # provides the instance as the first argument
        def _wrap(context, *args, **kwargs):
            if not isinstance(context, Context):
                raise RuntimeError(
                    f"Expected Context object as first argument " f"to action but got {context}"
                )
            return raw_act(self, context, *args, **kwargs)

        return _wrap

    def get_installer(self):
        """
        Return the installer registered for this tool if it exists.

        :returns:       The instance wrapped decorated method if known, else excepts
        """
        return self.get_action("installer")

    def get_host_path(self, ctx: Context, absolute: bool = True) -> Path:
        """
        Expand the location to get the full path to the tool on the host system.
        Substitutes Tool.HOST_ROOT for the 'host_tools' path from Context.

        :param ctx:      Context object
        :param absolute: When enabled this will flatten symlinks in the hierarchy
        :returns:        Resolved path
        """
        if self.location.is_relative_to(Tool.HOST_ROOT):
            path = ctx.host_tools / self.location.relative_to(Tool.HOST_ROOT)
        else:
            path = self.location
        return path.absolute() if absolute else path

    def get_container_path(self, ctx: Context, path: Path | None = None) -> Path:
        """
        Expand the location to get the full path to the tool within the contained
        environment, substituting Tool.CNTR_ROOT for the 'container_tools' path
        from Context.

        :param ctx:  Context object
        :param path: When provided, this path is resolved relative to the tool's
                     root (if defined using Tool.CNTR_ROOT)
        :returns:    Resolved path
        """
        base = ctx.container_tools / self.version.path_chunk
        if path:
            if path.is_relative_to(Tool.CNTR_ROOT):
                return base / path.relative_to(Tool.CNTR_ROOT)
            else:
                return path
        else:
            return base

    def as_interface(self, ctx: Context):
        from ..transforms import EnvPolicy, IEnv, IPath

        def normalise(value):
            if isinstance(value, Path):
                if value.is_relative_to(Tool.CNTR_ROOT) or value.is_relative_to(Tool.HOST_ROOT):
                    value = value.relative_to(Tool.CNTR_ROOT)
                    value = IPath(
                        self.get_host_path(ctx) / value, self.get_container_path(ctx) / value
                    )
            return value

        env = []
        for key, value in self.version.env.items():
            env.append(IEnv(key, normalise(value), policy=EnvPolicy.CONFLICT))
        for key, values in self.version.paths.items():
            env.append(IEnv(key, list(map(normalise, values)), policy=EnvPolicy.PREPEND))

        return {"env": env, "root": IPath(self.get_host_path(ctx), self.get_container_path(ctx))}

    # ==========================================================================
    # Registry Handling
    # ==========================================================================

    @classmethod
    def wrap(cls, tool: "Tool") -> "Tool":
        if tool in RegisteredClass.LOOKUP_BY_OBJ[cls]:
            return tool
        else:
            RegisteredClass.LOOKUP_BY_NAME[cls][tool().base_id_tuple] = tool
            RegisteredClass.LOOKUP_BY_OBJ[cls][tool] = tool
            return tool

    @classmethod
    def get(
        cls,
        vend_or_name: str,
        name: str | None = None,
        version: str | None = None,
    ) -> Union["Tool", None]:
        """
        Retrieve a tool registered for a given vendor, name, and version. If only a
        name is given, then NO_VENDOR is assumed for the vendor field. If no version
        is given, then the default version is returned. If no tool is known for the
        specification, then None is returned.

        :param vend_or_name:    Vendor or tool name is no associated vendor
        :param name:            Name if a vendor is specified
        :param version:         Version of the tool (optional)
        """
        vendor = vend_or_name.lower() if name else Tool.NO_VENDOR.lower()
        name = (name if name else vend_or_name).lower()
        tool_def: type[Tool] = cls.get_by_name((vendor, name))
        if not tool_def:
            return None
        version = tool_def.get_version(version, None)
        if version is None:
            return None
        return tool_def(version)

    @classmethod
    @contextmanager
    def temp_registry(cls):
        "Context managed temporary registry for use in tests"
        with super().temp_registry():
            actions = Tool.ACTIONS
            Tool.ACTIONS = defaultdict(dict)
            try:
                yield None
            finally:
                Tool.ACTIONS = actions


class Invocation:
    """
    Encapsulates the invocation of a tool within the container environment, this
    is returned by an method marked with @Tool.action(). The action may specify
    the tool version to use, the binary to launch, arguments to provide, whether
    or not X11 display forwarding is required, whether or not an interactive
    terminal is required, and any files/folders to bind in to the container.

    :param version:     Tool version to execute
    :param execute:     Binary to execute
    :param args:        Arguments to call the tool with
    :param workdir:     Working directory within the container
    :param display:     Whether to forward X11 display (forces interactive mode)
    :param interactive: Whether to attach an interactive shell
    :param host:        Whether to detect and bind host paths
    :param binds:       Paths to bind into the container from the host. Can be
                        provided as a single path in which case the container
                        path will be inferred, or as a tuple of a host path and
                        a container path.
    :param env:         Environment variables to add to the container
    :param path:        Path variables to extend within the container
    """

    def __init__(
        self,
        tool: Tool,
        execute: Path | str,
        args: Sequence[str | Path] | None = None,
        workdir: Path | None = None,
        display: bool = False,
        interactive: bool = False,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
        host: bool = False,
        binds: Sequence[Path | tuple[Path, Path]] | None = None,
        env: dict[str, str] | None = None,
        path: dict[str, list[Path]] | None = None,
    ) -> None:
        self.tool = tool
        self.execute = execute
        self.args = args or []
        self.workdir = workdir
        self.display = display
        self.interactive = interactive or display
        self.stdout = stdout
        self.stderr = stderr
        self.host = host
        self.binds = binds or []
        self.env = env or {}
        self.path = path or {}

    def where(self, **kwargs):
        "Utility method to configure invocation after the fact"
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                raise AttributeError(
                    f"Invocation object has no option `{k}` (tried to set to `{v}`)"
                )
        return self
