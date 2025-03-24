A Blockwork workspace is configured through a `.bw.yaml` file located in the root
folder of the project. It identifies the project, locates tool definitions, and
defines various other behaviours.

The file must use a `!Blockwork` tag as its root element, as per the example below:

```yaml linenums="1"
!Blockwork
project     : example
root        : /project
scratch     : /scratch
tools       : /tools
host_scratch: ../{project}.scratch
host_state  : ../{project}.state
host_tools  : ../{project}.tools
bootstrap   :
  - infra.bootstrap.setup
tooldefs    :
  - infra.tools.linters
  - infra.tools.compilers
```

The fields of the `!Blockwork` tag are:

| Field                | Required         | Default                | Description                                                                |
|----------------------|:----------------:|------------------------|----------------------------------------------------------------------------|
| project              | :material-check: |                        | Sets the project's name                                                    |
| root                 |                  | `/project`             | Location to map the project's root directory inside the container          |
| scratch              |                  | `/scratch`             | Location to map the scratch area inside the container                      |
| tools                |                  | `/tools`               | Location to map the tools inside the container                             |
| host_scratch         |                  | `../{project}.scratch` | Directory to store build objects and other artefacts                       |
| host_state           |                  | `../{project}.state`   | Directory to store Blockwork's state information for the project           |
| host_tools           |                  | `../{project}.tools`   | Directory containing tool installations on the host                        |
| default_cache_config |                  |                        | Path to the default cache configuration, see [Caching](../tech/caching.md) |
| bootstrap            |                  |                        | Python paths containing [Bootstrap](../syntax/bootstrap.md) definitions    |
| tooldefs             |                  |                        | Python paths containing [Tool](../syntax/tools.md) definitions             |

!!!note

    The `host_scratch`, `host_state`, and `host_tools` directories are resolved
    relative to the project's root directory on the host, and the `{project}`
    keyword will be substituted for the projects name (taken from the `project`
    field).

## Variable Substitutions

Some configuration fields support variable substitution into values, these are
summarised in the table below:

| Variable     | Supported By      | Description                                                    |
|--------------|-------------------|----------------------------------------------------------------|
| `{project}`  | `root`, `scratch` | Name of the project (from the `project` field)                 |
| `{root_dir}` | `root`, `scratch` | Name of the directory that's an immediate parent to `.bw.yaml` |
