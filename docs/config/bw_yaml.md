A Blockwork workspace is configured through a `.bw.yaml` file located in the root
folder of the project. It identifies the project, locates tool definitions, and
defines various other behaviours.

The file must use a `!Blockwork` tag as its root element, as per the example below:

```yaml linenums="1"
!Blockwork
project : example
tooldefs:
  - infra.linters
  - infra.compilers
```

The fields of the `!Blockwork` tag are:

| Field    | Required         | Description                                                    |
|----------|:----------------:|----------------------------------------------------------------|
| project  | :material-check: | Sets the project's name                                        |
| tooldefs | :material-check: | Python paths containing [Tool](../syntax/tools.md) definitions |
