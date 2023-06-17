A Blockwork workspace is configured through a `.bw.yaml` file located in the root
folder of the project. It identifies the project, locates tool definitions, and
defines various other behaviours.

The file must use a `!Blockwork` tag as its root element, as per the example below:

```yaml linenums="1"
!Blockwork
project  : example
root     : /bw/project
state_dir: .bw_state
bootstrap:
  - infra.bootstrap.setup
tooldefs :
  - infra.tools.linters
  - infra.tools.compilers
```

The fields of the `!Blockwork` tag are:

| Field     | Required         | Default       | Description                                                             |
|-----------|:----------------:|---------------|-------------------------------------------------------------------------|
| project   | :material-check: |               | Sets the project's name                                                 |
| root      |                  | `/bw/project` | Root directory where project is mapped inside the container             |
| state_dir |                  | `.bw_state`   | Directory to store Blockwork's state information for the project        |
| bootstrap |                  |               | Python paths containing [Bootstrap](../syntax/bootstrap.md) definitions |
| tooldefs  | :material-check: |               | Python paths containing [Tool](../syntax/tools.md) definitions          |
