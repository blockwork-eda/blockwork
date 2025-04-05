from collections.abc import Generator
from pathlib import Path

from blockwork.context import Context
from blockwork.tools import Invocation, Tool
from blockwork.transforms import Transform
from blockwork.transforms.transform import TransformResult

from ..tools.cmake import CMake


class CMakeTF(Transform):
    cmake: CMake = Transform.TOOL()
    tools: dict[str, Tool] = Transform.IN(default_factory=dict)
    source: Path = Transform.IN()
    toolchain: Path | None = Transform.IN(default=None)
    generator: str | None = Transform.IN(default=None)
    defines: dict[str, str] = Transform.IN(default_factory=dict)
    build_dir: Path = Transform.OUT(deterministic=False, init=True, default=...)
    install_dir: Path = Transform.OUT(init=True, default=...)
    outputs: list[Path] = Transform.OUT(init=True, default=...)

    def execute(self, ctx: Context) -> Generator[Invocation, TransformResult, None]:
        toolchain_args = () if self.toolchain is None else ("--toolchain", self.toolchain)
        generator_args = () if self.generator is None else ("-G", self.generator)
        define_args = (f'-D{k}="{v}"' for k, v in self.defines.items())

        yield self.cmake.run(
            ctx,
            "-S",
            self.source,
            "-B",
            self.build_dir,
            *toolchain_args,
            *generator_args,
            *define_args,
        )

        yield self.cmake.run(ctx, "--build", self.build_dir)
        yield self.cmake.run(ctx, "--install", self.build_dir, "--prefix", self.install_dir)
