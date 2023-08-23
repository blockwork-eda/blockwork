from pathlib import Path
from typing import Iterable, cast, overload, TYPE_CHECKING
from ..common.registry import RegisteredClass
from ..common.singleton import Singleton
if TYPE_CHECKING:
    from ..context import Context
from . import base

class Config(RegisteredClass, metaclass=Singleton):
    'Configuration object which is passed into workflows'
    def __init__(self, ctx: "Context", site: base.Site, project: base.Project, target: base.Element) -> None:
        self.ctx = ctx
        self.site = site
        self.project = project
        self.target = target

    def depth_first_elements(self, element: base.Element) -> Iterable[base.Element]:
        'Recures elements and yields depths first'
        for sub_element in element.iter_sub_elements():
            yield from self.depth_first_elements(sub_element)
        yield element

    def resolve(self):
        'Resolves paths in the config'
        linker = Linker(self)
        for element in self.depth_first_elements(self.target):
            if isinstance(element, base.Transform):
                linker.link_outputs(element)

        for element in self.depth_first_elements(self.target):
            linker.link_inputs(element)

class Linker:
    '''
    This class is responsible for finalising input and output paths
    and linking them together.

    @ed.kotarski: The next extension to this will be to use that
    information to create dependencies between transforms to determine 
    the order they need to be run.
    '''
    def __init__(self, config: Config):
        self.config = config
        self.pairs: dict[tuple[str, str], Path] = {}

    def link_inputs(self, element: base.Element):
        unit = cast(base.ElementContext, element._context).unit
        block_root = self.config.ctx.host_root / self.config.project.units[unit]

        @overload
        def resolve(paths: str) -> str: ...
        @overload
        def resolve(paths: list[str]) -> list[str]: ...
        def resolve(paths):
            if (is_single := isinstance(paths, str)):
                paths = [paths]

            resolved_paths: list[str] = []
            for path in paths:
                pair = (unit, path)
                if pair in self.pairs:
                    full_path = self.pairs[pair]
                else:
                    full_path = (block_root / path)
                resolved_paths.append(full_path.as_posix())
            return resolved_paths[0] if is_single else resolved_paths

        element.resolve_input_paths(resolve)

    def link_outputs(self, element: base.Transform):
        unit = cast(base.ElementContext, element._context).unit
        block_scratch = self.config.ctx.host_scratch / self.config.project.units[unit]

        @overload
        def resolve(paths: str) -> str: ...
        @overload
        def resolve(paths: list[str]) -> list[str]: ...
        def resolve(paths):
            if (is_single := isinstance(paths, str)):
                paths = [paths]

            resolved_paths: list[str] = []
            for path in paths:
                full_path = block_scratch / path
                self.pairs[(unit, path)] = full_path
                resolved_paths.append(full_path.as_posix())

            return resolved_paths[0] if is_single else resolved_paths

        element.resolve_output_paths(resolve)
