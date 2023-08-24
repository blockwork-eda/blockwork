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
import logging
from collections import defaultdict
from enum import StrEnum, auto
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

from ..common.registry import RegisteredClass
from ..common.singleton import Singleton
from ..context import Context, ContextHostPathError


class ToolMode(StrEnum):
    READONLY  = auto()
    READWRITE = auto()


class ToolError(Exception):
    pass


class Require:
    """ Forms a requirement on another tool and version """

    def __init__(self,
                 tool    : "Tool",
                 version : Optional[str] = None) -> None:
        self.tool = tool
        self.version = version
        if not inspect.isclass(tool) or not issubclass(tool, Tool):
            raise ToolError("Requirement tool must be of type Tool")
        if (self.version is not None) and not isinstance(self.version, str):
            raise ToolError("Requirement version must be None or a string")

    def resolve(self) -> "Version":
        if self.version:
            return self.tool().get_version(self.version)
        else:
            return self.tool().default


class Version:
    """ Defines a version of a tool """

    def __init__(self,
                 version  : str,
                 location : Path,
                 env      : Optional[Dict[str, str]]       = None,
                 paths    : Optional[Dict[str, List[str]]] = None,
                 requires : Optional[List[Require]]        = None,
                 default  : bool                           = False) -> None:
        self.version = version
        self.location = location
        self.env = env or {}
        self.paths = paths or {}
        self.requires = requires
        self.default = default
        self.tool : Optional["Tool"] = None
        # Sanitise arguments
        self.requires = self.requires or []
        self.paths    = self.paths or {}
        self.env      = self.env or {}
        if not isinstance(self.location, Path):
            raise ToolError(f"Bad location given for version {self.version}: {self.location}")
        if not isinstance(self.version, str) or len(self.version.strip()) == 0:
            raise ToolError("A version must be specified")
        if not isinstance(self.paths, dict):
            raise ToolError("Paths must be specified as a dictionary")
        if not all(isinstance(k, str) and isinstance(v, list) for k, v in self.paths.items()):
            raise ToolError("Path keys must be strings and values must be lists")
        if not all(isinstance(y, Path) for x in self.paths.values() for y in x):
            raise ToolError("Path entries must be of type pathlib.Path")
        if not isinstance(self.default, bool):
            raise ToolError("Default must be either True or False")
        if not isinstance(self.requires, list):
            raise ToolError("Requirements must be a list")
        if not all(isinstance(x, Require) for x in self.requires):
            raise ToolError("Requirements must be a list of Require objects")

    @property
    @functools.lru_cache()
    def id_tuple(self) -> str:
        return (*self.tool.base_id_tuple, self.version)

    @property
    @functools.lru_cache()
    def id(self) -> str:
        vend, name, vers = self.id_tuple
        if vend.casefold() == Tool.NO_VENDOR.casefold():
            return "_".join((name, vers))
        else:
            return "_".join((vend, name, vers))

    @functools.lru_cache()
    def resolve_requirements(self) -> Set["Version"]:
        return {x.resolve() for x in self.requires}

    @property
    def path_chunk(self) -> Path:
        if self.tool.vendor is not Tool.NO_VENDOR:
            return Path(self.tool.vendor.lower()) / self.tool.name / self.version
        else:
            return Path(self.tool.name) / self.version

    def get_action(self, name : str) -> Union[Callable, None]:
        if (action := self.tool.get_action(name)) is None:
            return None
        # Return a wrapper that inserts the active version
        def _wrap(context, *args, **kwargs):
            return action(context, self, *args, **kwargs)
        return _wrap

    def get_installer(self) -> Union[Callable, None]:
        if (action := self.tool.get_installer()) is None:
            return None
        # Return a wrapper that inserts the active version
        def _wrap(context, *args, **kwargs):
            return action(context, self, *args, **kwargs)
        return _wrap

    def __getattribute__(self, name: str) -> Any:
        try:
            return super().__getattribute__(name)
        except AttributeError as e:
            if (act := self.get_action(name)) is not None:
                return act
            raise e

    def get_host_path(self, ctx : Context) -> Path:
        """
        Expand the location to get the full path to the tool on the host system.
        Substitutes Tool.HOST_ROOT for the 'host_tools' path from Context.

        :param ctx: Context object
        :returns:   Resolved path
        """
        if self.location.is_relative_to(Tool.HOST_ROOT):
            return ctx.host_tools / self.location.relative_to(Tool.HOST_ROOT)
        else:
            return self.location

    def get_container_path(self, ctx : Context, path : Optional[Path] = None) -> Path:
        """
        Expand the location to get the full path to the tool within the contained
        environment, substituting Tool.CNTR_ROOT for the 'container_tools' path
        from Context.

        :param ctx:  Context object
        :param path: When provided, this path is resolved relative to the tool's
                     root (if defined using Tool.CNTR_ROOT)
        :returns:    Resolved path
        """
        base = ctx.container_tools / self.path_chunk
        if path:
            if path.is_relative_to(Tool.CNTR_ROOT):
                return base / path.relative_to(Tool.CNTR_ROOT)
            else:
                return path
        else:
            return base


class Tool(RegisteredClass, metaclass=Singleton):
    """ Base class for tools """

    # Tool root locator
    CNTR_ROOT : Path = Path("/__tool_cntr_root__")
    HOST_ROOT : Path = Path("/__tool_host_root__")

    # Default vendor
    NO_VENDOR = "N/A"

    # Action registration
    ACTIONS  = defaultdict(dict)
    RESERVED = ("installer", "default")

    # Placeholders
    vendor   : Optional[str]           = None
    versions : Optional[List[Version]] = None

    def __init__(self) -> None:
        self.vendor = self.vendor.strip() if isinstance(self.vendor, str) else Tool.NO_VENDOR
        self.versions = self.versions or []
        if not isinstance(self.versions, list):
            raise ToolError(f"Versions of tool {self.name} must be a list")
        if not all(isinstance(x, Version) for x in self.versions):
            raise ToolError(f"Versions of tool {self.name} must be a list of Version objects")
        # If only one version is defined, make that the default
        if len(self.versions) == 1:
            self.versions[0].default = True
            self.versions[0].tool = self
            self.default = self.versions[0]
        else:
            # Check for collisions between versions and multiple defaults
            self.default = None
            version_nums = []
            for version in self.versions:
                version.tool = self
                # Check for multiple defaults
                if version.default:
                    if self.default is not None:
                        raise ToolError(f"Multiple versions marked default for tool {self.name} "
                                        f"from vendor {self.vendor}")
                    self.default = version
                # Check for repeated version numbers
                if version.version in version_nums:
                    raise ToolError(f"Duplicate version {version.version} for tool "
                                    f"{self.name} from vendor {self.vendor}")
                version_nums.append(version.version)
            # Check the default has been identified
            if self.default is None:
                raise ToolError(f"No version of tool {self.name} from vendor "
                                f"{self.vendor} marked as default")

    def __iter__(self) -> Iterable[Version]:
        yield from self.versions

    @property
    @functools.lru_cache()
    def name(self) -> str:
        return type(self).__name__.lower()

    @property
    @functools.lru_cache()
    def base_id_tuple(self) -> str:
        return (self.vendor.lower(), self.name)

    @property
    @functools.lru_cache()
    def base_id(self) -> str:
        vend, name = self.base_id_tuple
        if vend.casefold() == Tool.NO_VENDOR.casefold():
            return name
        else:
            return "_".join((vend, name))

    @functools.lru_cache()
    def get_version(self, version : str) -> Version:
        """
        Retrieve a specific version of a tool from the version name.

        :param version: Version name
        :returns:       Matching Version instance, or None if it doesn't exist
        """
        match = [x for x in self.versions if x.version == version]
        return match[0] if match else None

    @classmethod
    def action(cls,
               tool_name : str,
               name      : Optional[str] = None,
               default   : bool          = False) -> Callable:
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
        def _inner(method : Callable) -> Callable:
            nonlocal name
            name = name or method.__name__
            # Check that the name is not reserved
            if name.lower() in cls.RESERVED:
                raise ToolError(f"Cannot register an action called '{name}' to "
                                f"tool '{tool_name}' as it is a reserved name")
            # Register the action
            cls.__register_action(tool_name, name, default, method)
            # Return the unaltered method
            return method
        return _inner

    @classmethod
    def installer(cls, tool_name : str) -> Callable:
        """
        Special decorator to mark an action that installs the tool by downloading
        it from a central store.

        :param tool_name:   Name of the tool, which should match the class name
                            of the tool. This must be provided as an argument as
                            unbound methods do not have a relationship to their
                            parent.
        """
        def _inner(method : Callable) -> Callable:
            # Register method with a fixed name of 'installer' (reserved)
            cls.__register_action(tool_name, "installer", False, method)
            # Return the unaltered method
            return method
        return _inner

    @classmethod
    def __register_action(cls,
                          tool_name : str,
                          name : str,
                          default : bool,
                          method : Callable):
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
            raise ToolError(f"An action called '{name}' already been registered "
                            f"to tool '{tool_name}'")
        # Register the action as specified
        cls.ACTIONS[tool_name][name] = method
        # If marked as default, call recursively
        if default:
            cls.__register_action(tool_name, "default", False, method)

    def get_action(self, name : str) -> Union[Callable, None]:
        """
        Return an action registered for this tool if known.

        :param name:    Name of the action
        :returns:       The instance wrapped decorated method if known, else None
        """
        tool_cls = type(self)
        tool_name = tool_cls.__name__.lower()
        if (actions := tool_cls.ACTIONS.get(tool_name, None)) is None:
            return None
        if (raw_act := actions.get(name.lower(), None)) is None:
            return None
        # The method held in the actions dictionary is unbound, so this wrapper
        # provides the instance as the first argument
        def _wrap(context, *args, **kwargs):
            if not isinstance(context, Context):
                raise RuntimeError(f"Expected Context object as first argument "
                                   f"to action but got {context}")
            return raw_act(self, context, *args, **kwargs)
        return _wrap

    # ==========================================================================
    # Registry Handling
    # ==========================================================================

    @classmethod
    def wrap(cls, tool : "Tool") -> "Tool":
        if tool in RegisteredClass.LOOKUP_BY_OBJ[cls]:
            return tool
        else:
            RegisteredClass.LOOKUP_BY_NAME[cls][tool().base_id_tuple] = tool
            RegisteredClass.LOOKUP_BY_OBJ[cls][tool] = tool
            return tool

    @classmethod
    def get(cls,
            vend_or_name : str,
            name         : Optional[str] = None,
            version      : Optional[str] = None) -> Union["Tool", None]:
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
        tool_def : Tool = cls.get_by_name((vendor, name))
        if not tool_def:
            return None
        tool = tool_def()
        if version:
            return tool.get_version(version)
        else:
            return tool.default

    @classmethod
    def select_version(cls,
                       vend_or_name : str,
                       name         : Optional[str] = None,
                       version      : Optional[str] = None) -> None:
        """
        Select a specific version of a tool as the default, overriding whatever
        default version the tool itself has nominated.

        :param vend_or_name:    Vendor or tool name is no associated vendor
        :param name:            Name if a vendor is specified
        :param version:         Version of the tool (required)
        """
        if version is None:
            raise ToolError("A version must be provided")
        vendor = vend_or_name.lower() if name else Tool.NO_VENDOR.lower()
        name = (name if name else vend_or_name).lower()
        tool_def : Tool = cls.get_by_name((vendor, name))
        if not tool_def:
            raise ToolError(f"No tool known for name '{name}' from vendor '{vendor}'")
        tool = tool_def()
        tool.default.default = False
        tool.default = tool.get_version(version)
        tool.default.default = True

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
    :param binds:       Paths to bind into the container from the host. Can be
                        provided as a single path in which case the container
                        path will be inferred, or as a tuple of a host path and
                        a container path.
    :param env:         Environment variables to add to the container
    :param path:        Path variables to extend within the container
    """

    def __init__(self,
                 version     : Version,
                 execute     : Path,
                 args        : Optional[List[Union[str, Path]]] = None,
                 workdir     : Optional[Path] = None,
                 display     : bool = False,
                 interactive : bool = False,
                 binds       : Optional[List[Union[Path, Tuple[Path, Path]]]] = None,
                 env         : Optional[Dict[str, str]] = None,
                 path        : Optional[Dict[str, List[str]]] = None) -> None:
        self.version     = version
        self.execute     = execute
        self.args        = args or []
        self.workdir     = workdir
        self.display     = display
        self.interactive = interactive or display
        self.binds       = binds or []
        self.env         = env or {}
        self.path        = path or {}

    def map_args_to_container(self, context : Context) -> List[Union[str, Path]]:
        """
        Map all of the arguments of the invocation to be relative to the container.

        :param context: Context object
        :returns:       List of mapped arguments
        """
        args = []
        for arg in self.args:
            # If this is a string, but appears to be a relative path, convert it
            if isinstance(arg, str) and (as_path := (Path.cwd() / arg)).exists():
                arg = as_path
            # For path arguments, check they will be accessible in the container
            if isinstance(arg, Path):
                try:
                    c_path = context.map_to_container(arg.absolute())
                    args.append(c_path.as_posix())
                except ContextHostPathError:
                    logging.debug(f"Assuming '{arg}' is a container-relative path")
                    args.append(arg.as_posix())
            # Otherwise, just pass through the argument
            else:
                args.append(arg)
        return args
