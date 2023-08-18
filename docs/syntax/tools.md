As many tools and versions may be declared, the syntax needs to be concise. There
are three requirements:

 1. The binaries, libraries, and supporting files that form the tool need to be
    bound into the container instance;

 2. Some environment variables may need to be setup to modify the execution
    behaviour (e.g. `VERILATOR_ROOT`);

 3. Path-type environment variables need to be extended to include the tool's
    binary and library directories (e.g. `PATH` for binaries and
    `LD_LIBRARY_PATH` for shared object libraries).

Blockwork tool declarations are handled in Python, and the following is an example
of the syntax:

```python
from pathlib import Path

from blockwork.tools import Tool, Version

install_root = Path("/some/path/to/tool/installs")

@Tool.register()
class Verilator(Tool):
    versions = [
        Version(location = install_root / "verilator-4.106"
                version  = "4.106"
                env      = { "VERILATOR_ROOT": Tool.ROOT }
                paths    = { "PATH": [Tool.ROOT / "bin"] }),
    ]
```

Working through this example:

 * `@Tool.register()` - associates the tool description with Blockwork's internal
   registry, allowing it to be used in a flow;

 * `class Verilator(Tool):` - extends from the `Tool` base class and defines the
   name associated with this definition (e.g. `Verilator`);

 * `versions` - defines different named versions of a tool;

 * Each version is defined by an instance of `Version` where:

   * `location` - identifies the path on the **host** where the tool is installed,
     in this example all tools are installed under a common directory which is
     referenced via `install_root`;

   * `version` - sets the version number for the tool, this is to make it distinct
     from other declarations;

   * `env` - dictionary of variables to append into the container's shell environment;

   * `paths` - dictionary of lists, where each list entry is a section to append to
     a `$PATH`-type variable within the container's shell environment.

!!!note

    The `Tool.ROOT` variable points to the equivalent of the `location` when
    mapped into the container (i.e. the root directory of the bound tool)

Tools are mapped into the container using a standard path structure:

`/tools/<TOOL_NAME>/<VERSION>`

The `<TOOL_NAME>` will be replaced by a lowercase version of the class name, for
the example given above this would mean `<TOOL_NAME>` becomes `verilator`. The
`<VERSION>` always matches the `version` field (i.e. `4.106` in this case). For the
Verilator example, this would give a path of:

`/tools/verilator/4.106`

## Vendor Grouping

If a suite of tools from a single supplier, the syntax also allows for the `vendor`
keyword to be provided which adds an extra section into the path. For example:

```python
@Tool.register()
class Make(Tool):
    vendor   = "GNU"
    versions = [
        Version(location = install_root / "make-4.4",
                version  = "4.4",
                paths    = { "PATH": [Tool.ROOT / "bin"] }),
    ]
```

Will be mapped using the form `/tools/<VENDOR>/<TOOL_NAME>/<VERSION>` to:

`/tools/gnu/make/4.4`

!!!note

    Vendor and tool name will always be converted to lowercase, Blockwork will check
    before binding that no two mapped tools collide

## Multiple Versions

When multiple tool versions are defined, there must be one marked as default which will
be bound when a version is not explicitly given:

```python
@Tool.register()
class Make(Tool):
    vendor   = "GNU"
    versions = [
        Version(location = install_root / "make-4.4",
                version  = "4.4",
                paths    = { "PATH": [Tool.ROOT / "bin"] },
                default  = True),
        Version(location = install_root / "make-4.3",
                version  = "4.3",
                paths    = { "PATH": [Tool.ROOT / "bin"] }),
    ]
```

!!!warning

    If no version is marked as default then a `ToolError` will be raised. Similarly,
    if multiple versions are marked as default then a `ToolError` will be raised.

## Forming Requirements

Tools may rely on other tools to provide binaries or libraries to support their
execution, these relationships are described through `Require` objects:

```python
from blockwork.tools import Require, Tool, Version

@Tool.register()
class Python(Tool):
    """ Base Python installation """
    versions = [
        Version(location = install_root / "python-3.11.4",
                version  = "3.11.4",
                paths    = { "PATH"           : [Tool.ROOT / "bin"],
                             "LD_LIBRARY_PATH": [Tool.ROOT / "lib"] })
    ]

@Tool.register()
class PythonSite(Tool):
    """ Versioned package installation """
    versions = [
        Version(location = install_root / "python-site-3.11.4",
                version  = "3.11.4",
                env      = { "PYTHONUSERBASE": Tool.ROOT },
                paths    = { "PATH"      : [Tool.ROOT / "bin"],
                             "PYTHONPATH": [Tool.ROOT / "lib" / "python3.11" / "site-packages"] },
                requires = [Require(Python, "3.11.4")]),
    ]
```

The `Require` class takes two arguments:

 * `tool` - which must carry a `Tool` definition;
 * `version` - which can either be omitted (implicitly selecting the default
   version) or can be a string identifying a version number.

## Actions and Invocations

Many tools will offer a command line interface that can perform certain discrete
tasks, for example a wave viewer like GTKWave will be able to display the
contents of a VCD. Such tasks can be wrapped up as an 'action' within a tool
declaration, which can then be invoked directly from the command line.

Actions return `Invocation` objects that encapsulates the command to run, any
arguments to provide, and files or folders to be bound in to the container.

```python
from pathlib import Path
from typing import List

from blockwork.tools import Invocation, Tool, Version
from blockwork.context import Context

@Tool.register()
class GTKWave(Tool):
    versions = [
        Version(location = tool_root / "gtkwave-3.3.113",
                version  = "3.3.113",
                paths    = { "PATH": [Tool.ROOT / "src"] }),
    ]

    @Tool.action("GTKWave", default=True)
    def view(self,
             ctx      : Context
             version  : Version,
             wavefile : str,
             *args    : List[str]) -> Invocation:
        path = Path(wavefile).absolute()
        return Invocation(
            version = version,
            execute = Tool.ROOT / "src" / "gtkwave",
            args    = [path, *args],
            display = True,
            binds   = [path.parent]
        )
```

!!!warning

    The name provided as the first argument to `@Tool.action()` must match the
    name of the class that declares the tool.

This action can then be invoked from the shell using the `bw tool` command:

```bash
$> bw tool gtkwave.view waves.vcd
```

Or, as `view` is marked as a default action, this can be shortened to just:

```bash
$> bw tool gtkwave waves.vcd
```

!!!note

    As this action will invoke an X11 GUI, the `display = True` argument must be
    provided in the `Invocation` instance.

### Paths and Binds

The example of the GTKWave `view` action above relies on reading files from the
host filesystem, this means that they need to be bound into the container prior
to invoking the tool. When an action is invoked it may manually specify binds,
but the arguments list can also contain paths which will be automatically bound
into the container.

Each bound path must be relative to the project root directory on the host, for
example if a project is located under `/home/fred/example` then all paths bound
in must be under this directory - that is to say `/home/fred/example/waves.vcd`
is okay, but `/home/fred/outside.vcd` is not.

## Installers

Blockwork provides a special `@Tool.installer(...)` decorator for registering a
specific action for installing a tool's binaries/libraries in some way. How a
tool is installed (i.e. by downloading or compiling) is up to the action to
determine.

The example below demonstrates how an installer action can be setup to download
the source code for a specific version of Python and compile it.

```python
from pathlib import Path

from blockwork.tools import Invocation, Require, Tool, Version
from blockwork.context import Context

install_root = Path("/some/path/to/tool/installs")

@Tool.register()
class Python(Tool):
    """ Base Python installation """
    versions = [
        Version(location = install_root / "python-3.11.4",
                version  = "3.11.4",
                paths    = { "PATH"           : [Tool.ROOT / "bin"],
                             "LD_LIBRARY_PATH": [Tool.ROOT / "lib"] })
    ]

    @Tool.installer("Python")
    def install(self, context : Context, version : Version, *args : List[str]) -> Invocation:
        vernum = version.version
        tool_dir = Path("/tools") / version.location.relative_to(TOOL_ROOT)
        script = [
            f"wget --quiet https://www.python.org/ftp/python/{vernum}/Python-{vernum}.tgz",
            f"tar -xf Python-{vernum}.tgz",
            f"cd Python-{vernum}",
            f"./configure --enable-optimizations --with-ensurepip=install "
            f"--enable-shared --prefix={tool_dir.as_posix()}",
            "make -j4",
            "make install",
            "cd ..",
            f"rm -rf Python-{vernum} ./*.tgz*"
        ]
        return Invocation(
            version = version,
            execute = "bash",
            args    = ["-c", " && ".join(script)],
            workdir = tool_dir
        )
```

There is a built-in bootstrapping action that locates and executes all of the
tool installation methods:

```bash
$> bw -v bootstrap
...
[16:11:17] DEBUG    Evaluating bootstrap step 'blockwork.bootstrap.tools.install_tools'
           DEBUG    Ordering 17 tools based on requirements:
           DEBUG     - 0: n/a gcc 13.1.0
           DEBUG     - 1: n/a help2man 1.49.3
           ...
           INFO     Installing 17 tools:
           INFO      - 0: Launching installation of n/a gcc 13.1.0
           ...
```
