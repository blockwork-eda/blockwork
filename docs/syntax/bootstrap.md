Bootstrapping is an extensible mechanism for running custom setup steps to prepare
a checkout for use - some examples:

 * Performing sanity checks on the host system;
 * Downloading tools to run within the contained environment;
 * Compiling common libraries needed by different stages of a flow.

In more general terms a good candidate as a bootstrapping step is a relatively
complex action that needs to be performed only once to support many workflows.
The action may change over time, and the bootstrapping mechanism provides means
for testing if an action needs to be re-run (discussed in more detail below).

## Declaring a Bootstrap Step

A bootstrap step is declared simply as a method marked with the `@Bootstrap.register()`
decorator, for example:

```python title="infra/bootstrap/tool_a.py" linenums="1"
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from urllib import request

from blockwork.bootstrap import Bootstrap
from blockwork.context import Context

@Bootstrap.register()
def setup_tool_a(context : Context, last_run : datetime) -> bool:
    """ Download a tool from a shared server and extract it locally """
    install_loc = context.host_root / "tools" / "tool_a"
    # Check to see if tool is already installed
    if install_loc.exists():
        return True
    # Fetch the tool
    with tempfile.TemporaryDirectory() as tmpdir:
        local = tmpdir / "tool_a.zip"
        request.urlretrieve("http://www.example.com/tool_a.zip", local)
        with zipfile.ZipFile(local, "r") as zh:
            zh.extractall(install_loc)
    return False
```

The decorator `@Bootstrap.register()` marks the function that follows it as
defining a bootstrapping step. When the full bootstrapping process is invoked,
all bootstrap steps will be executed in the order they were registered.

A bootstrap step must have the following attributes:

 * It must accept an argument called `context` which will carry an instance of
   the `Context` object - this can be used to locate the root area of the project,
   read the configuration, and access state information;

 * It must accept an argument called `last_run` which is a `datetime` instance
   carrying the last date the bootstrapping action was run, or set to UNIX time
   zero if its never been run before;

 * It must return a boolean value - `True` indicates that the bootstrap step was
   already up-to-date (no action was required), while `False` indicates that the
   step was not up-to-date (some action was required to setup the work area).

## Project Configuration

Paths to bootstrapping routines must also be added into the
[project configuration](../config/bw_yaml.md) so that Blockwork can discover them.

For example:

```yaml title=".bw.yaml" linenums="1"
!Blockwork
project  : my_project
bootstrap:
  - infra.bootstrap.tool_a
```

## Bootstrapping

All of the registered bootstrapping steps can be executed using the
[bootstrap](../cli/bootstrap.md) command:

```bash
$> bw bootstrap
[20:12:06] INFO     Importing 1 bootstrapping paths
           INFO     Invoking 1 bootstrap methods
           INFO     Ran bootstrap step 'infra.bootstrap.tool_a.setup_tool_a'
           INFO     Bootstrap complete
```

If any individual bootstrapping step fails, the entire run will be aborted.

## Avoiding Redundant Actions

As a project evolves, it is likely that new bootstrapping methods will be added
and existing ones updated - for example a new tool version may need to be installed.
This means that the project will need to be periodically re-bootstrapped, but if
the project is large this could be a long operation.

To reduce the amount of unnecessary compute as far as possible, two mechanisms
are available to skip individual steps.

### Check Point File

The simplest mechanism is to define a check point when registering the bootstrap
step - this can be a file or folder path that signals the step is out-of-date
whenever it is newer than the last run of the bootstrapping step.

In the example below `tools/tool_urls.json` is identified as a file that will
change whenever a new tool is added or a version updated. Blockwork will invoke
the bootstrapping step whenever:

 1. The check point file does not exist (in case it's an output of the step);
 2. The step has never been run before;
 3. The last recorded run of the step is older than the last modified date of
    the checkpoint file.

```python title="infra/bootstrap/tool_a.py linenums="1"
from datetime import datetime
from pathlib import Path

from blockwork.bootstrap import Bootstrap
from blockwork.context import Context

@Bootstrap.register(check_point=Path("tools/tool_urls.json"))
def setup_tool_a(context : Context, last_run : datetime) -> bool:
    # ...setup the tool...
```

!!!note

    Check point paths are always resolved relative to the root of the project
    work area.

### Last Run Date

If check point files are too simple to work for certain bootstrapping steps,
then the alternative mechanism is to test the `last_run` argument within the
method. This check should be made as soon as possible to avoid unnecessary
compute and should return `True` if the step is already up-to-date.

The example below implements the same check as is performed by check point files,
just to demonstrate how the mechanism may be used:

```python title="infra/bootstrap/tool_a.py linenums="1"
from datetime import datetime
from pathlib import Path

from blockwork.bootstrap import Bootstrap
from blockwork.context import Context

@Bootstrap.register()
def setup_tool_a(context : Context, last_run : datetime) -> bool:
    urls_file = context.host_root / "tools" / "tool_urls.json"
    # If the URL file hasn't changed, return True to signal we're up-to-date
    if datetime.fromtimestamp(urls_file.stat().st_mtime) <= last_run:
        return True
    # ...other stuff to setup the tool...
    # Return False to signal that we were NOT up-to-date prior to running
    return False
```
