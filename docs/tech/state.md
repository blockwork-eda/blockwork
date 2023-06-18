Some operations related to the project may be stateful - for example any setup
performed by [bootstrapping operations](../syntax/bootstrap.md) only needs to be
executed on a fresh checkout or whenever the setup process is changed. Blockwork
offers a mechanism to persist variables that can then be retrieved in later
invocations.

Persisted variables are separated into different namespaces, and different tools
can register their own namespaces if required. For example, the
[bootstrap](../syntax/bootstrap.md) state is preserved into a namespace called
'bootstrap'.

Each namespace is serialised to JSON, and reloaded lazily - avoiding unnecessary
delays when invoking the Blockwork command as only the state which is required
will be read from disk. Serialised data will be stored into the directory set by
[`state_dir` in the !Blockwork configuration](../config/bw_yaml.md).

For most usecases, state will be access via the context object that is passed
into different routines. For example, the [bootstrap](../syntax/bootstrap.md)
stage shown in the example below accesses the state dictionary via the `context`
argument:

```python linenums="1" title="infra/bootstrap/tool_a.py"
import logging
import os
import pwd
from datetime import datetime
from pathlib import Path

from blockwork.bootstrap import Bootstrap
from blockwork.context import Context

@Bootstrap.register()
def setup_tool_a(context : Context, last_run : datetime) -> bool:
    # Log any previous install
    if (prev_url := context.state.tool_a.url) is not None:
        logging.info(f"Previous version of tool A was installed from {prev_url}")
    # URL to download the tool from
    url = "http://example.com/tool_a.zip"
    # ...some actions to download the tool and install it...
    # Remember some details about the install
    context.state.tool_a.url          = url
    context.state.tool_a.install_date = datetime.now().timestamp()
    context.state.tool_a.installed_by = pwd.getpwuid(os.getuid()).pw_name
    # See bootstrapping section to explain the return value
    return False
```

The instance of the `State` class is accessed via `context.state` - this is the
correct way to manage state in most cases (as opposed to manually creating an
instance of `State`). Different state namespaces are accessed by using the `.`
operator - for example `context.state.tool_a` opens a namespace called `tool_a`,
automatically creating it if it doesn't already exist. Namespaces can alternatively
be accessed using the `get` method - for example `context.state.get("tool_a")`.

Each namespace is an instance of the `StateNamespace` class, and variables can
be similiarly set and retrieved using the `.` operator or the `set` and `get`
methods - examples of both methods are shown below:

```python title="Using the '.' operator"
# Reading a value
existing = context.state.my_tool.some_var
if existing is not None:
    print(f"An existing value was already set: {existing}")
# Writing a value
context.state.my_tool.some_var = 123
```

```python title="Using the 'set' and 'get' methods"
# Reading a value
existing = context.state.my_tool.get("some_var")
if existing is not None:
    print(f"An existing value was already set: {existing}")
# Writing a value
context.state.my_tool.some_var.set("123")
```

!!!warning

    State variables may only have primitive types such as string, integer, float,
    and boolean - using any other type will raise an exception. Namespaces are
    also shallow, so do not support deep variable hierarchies (i.e. only
    `context.state.my_tool.some_var` is supported and not
    `context.state.my_tool.lvl_one.lvl_two.some_var`).
