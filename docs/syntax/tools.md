
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