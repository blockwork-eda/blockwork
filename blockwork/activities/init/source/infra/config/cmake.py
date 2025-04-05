from collections.abc import Iterable
from dataclasses import field
from pathlib import Path

from blockwork.config.base import Config, ConfigProtocol
from blockwork.tools import Tool
from blockwork.transforms import Transform

from ..transforms.cmake import CMakeTF


class CMake(Config):
    source: str | Path
    build: str | Path
    install: str | Path
    toolchain: str | Path | None = None
    defines: dict[str, str] = field(default_factory=dict)
    tools: dict[str, str | None] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)

    def iter_transforms(self) -> Iterable[Transform]:
        tools = {}
        for tool_name, tool_version in self.tools.items():
            tool = Tool.get(tool_name, version=tool_version)
            if tool is None:
                raise ValueError(f"Cannot find tool '{tool_name}' with version '{tool_version}'")
            tools[tool_name] = tool.as_interface(self.api.ctx)

        yield CMakeTF(
            tools=tools,
            source=self.api.path(self.source),
            toolchain=self.api.path(self.toolchain) if self.toolchain else None,
            defines=self.defines,
            build_dir=self.api.static_path(self.build),
            install_dir=self.api.path(self.install),
            outputs=list(map(self.api.path, self.outputs)),
        )


class CMakeSet(Config):
    FILE_NAME = "cmake"

    items: list[CMake] = field(default_factory=list)

    def iter_config(self) -> Iterable[ConfigProtocol]:
        yield from self.items
