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

class Verilator(Tool):
    versions = [
        Version(location = install_root / "verilator-4.106"
                version  = "4.106"
                env      = { "VERILATOR_ROOT": Tool.TOOL_ROOT }
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] }),
    ]
```

Working through this example:

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

    The `Tool.TOOL_ROOT` variable points to the equivalent of the `location` when
    mapped into the container (i.e. the root directory of the bound tool)

Tools are mapped into the container using a standard path structure:

`/bw/tools/<TOOL_NAME>/<VERSION>`

The `<TOOL_NAME>` will be replaced by a lowercase version of the class name, for
the example given above this would mean `<TOOL_NAME>` becomes `verilator`. The
`<VERSION>` always matches the `version` field (i.e. `4.106` in this case). For the
Verilator example, this would give a path of:

`/bw/tools/verilator/4.106`

## Vendor Grouping

If a suite of tools from a single supplier, the syntax also allows for the `vendor`
keyword to be provided which adds an extra section into the path. For example:

```python
class Make(Tool):
    vendor   = "GNU"
    versions = [
        Version(location = install_root / "make-4.4",
                version  = "4.4",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] }),
    ]
```

Will be mapped using the form `/bw/tools/<VENDOR>/<TOOL_NAME>/<VERSION>` to:

`/bw/tools/gnu/make/4.4`

!!!note

    Vendor and tool name will always be converted to lowercase, Blockwork will check
    before binding that no two mapped tools collide

## Multiple Versions

When multiple tool versions are defined, there must be one marked as default which will
be bound when a version is not explicitly given:

```python
class Make(Tool):
    vendor   = "GNU"
    versions = [
        Version(location = install_root / "make-4.4",
                version  = "4.4",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] },
                default  = True),
        Version(location = install_root / "make-4.3",
                version  = "4.3",
                paths    = { "PATH": [Tool.TOOL_ROOT / "bin"] }),
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

class Python(Tool):
    """ Base Python installation """
    versions = [
        Version(location = install_root / "python-3.11",
                version  = "3.11",
                paths    = { "PATH"           : [Tool.TOOL_ROOT / "bin"],
                             "LD_LIBRARY_PATH": [Tool.TOOL_ROOT / "lib"] })
    ]

class PythonSite(Tool):
    """ Versioned package installation """
    versions = [
        Version(location = install_root / "python-site-3.11",
                version  = "3.11",
                env      = { "PYTHONUSERBASE": Tool.TOOL_ROOT },
                paths    = { "PATH"      : [Tool.TOOL_ROOT / "bin"],
                             "PYTHONPATH": [Tool.TOOL_ROOT / "lib" / "python3.11" / "site-packages"] },
                requires = [Require(Python, "3.11")]),
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

class GTKWave(Tool):
    versions = [
        Version(location = tool_root / "gtkwave-3.3.113",
                version  = "3.3.113",
                paths    = { "PATH": [Tool.TOOL_ROOT / "src"] }),
    ]

    @Tool.action("GTKWave", default=True)
    def view(self,
             version  : Version,
             wavefile : str,
             *args    : List[str]) -> Invocation:
        path = Path(wavefile).absolute()
        return Invocation(
            version = version,
            execute = Tool.TOOL_ROOT / "src" / "gtkwave",
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
