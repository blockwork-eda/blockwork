A Blockwork workspace is configured through a `.bw.yaml` file located in the root
folder of the project. It identifies the project, locates tool definitions, and
defines various other behaviours.

The file must use a `!Blockwork` tag as its root element, as per the example below:

```yaml linenums="1"
!Blockwork
project : example
root    : /bw/project
tooldefs:
  - infra.linters
  - infra.compilers
```

The fields of the `!Blockwork` tag are:

| Field    | Required         | Default       | Description                                                    |
|----------|:----------------:|---------------|----------------------------------------------------------------|
| project  | :material-check: |               | Sets the project's name                                        |
| root     |                  | `/bw/project` | Root directory where project is mapped inside the container    |
| tooldefs | :material-check: |               | Python paths containing [Tool](../syntax/tools.md) definitions |
