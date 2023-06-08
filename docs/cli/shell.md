The `shell` command opens a bash shell within the development environment, with
the entire project and all tools mapped in. The environment can be customised
using options to the command.

It has no sub-commands.

## Options

 * `--tool <TOOL>` / `-t <TOOL>` - bind a tool into the container - this must use
   one of the following forms:

    * `<VENDOR>:<NAME>=<VERSION>` - full syntax that explicitly identifies the
      vendor, tool name, and version;
    * `<VENDOR>:<NAME>` - identifies vendor and tool name, implicitly selecting
      the default version;
    * `<NAME>=<VERSION>` - identifies tool name and version where there is no
      vendor specified for the tool;
    * `<NAME>` - identifies only the tool name, where there is no vendor and the
      default version is implicitly selected.

 * `--no-tools` - disable automatic binding of all known tools into the container.

!!!note

    If neither `--tool` or `--no-tools` options are provided, then Blockwork will
    automatically bind the default version of all known tools into the container.
    If a single `--tool` is specified, then automatic tool binds will be disabled.

## Usage Example

```bash
$> bw shell --tool GNU:make=4.4
[12:05:26] INFO     Binding tool make from N/A version 4.4 into shell
[root@example_shell project]# make -v
GNU Make 4.4
```
