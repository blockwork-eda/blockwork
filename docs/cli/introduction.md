The command line interface (CLI) is the main way to interact with Blockwork. It
adopts a style similar to `git` with stacked sub-commands and scoped options.
It may be invoked using the `blockwork` command, or by using the short-hand
version of just `bw`.

## Top-Level Options

 * `--help` - displays the built-in help, listing the top-level options and the
   first level of subcommands;

 * `--cwd <DIR>` / `-C <DIR>` - by default Blockwork will expect the current
   working directory or one of its parents to contain a `.bw.yaml` configuration
   file, if commands are being run from outside of this hierarchy then the
   working directory can be overridden using this option.

## Commands

 * [bootstrap](bootstrap.md) - runs all known bootstrapping stages;
 * [exec](exec.md) - executes a command within the contained environment;
 * [info](info.md) - displays information about the current project;
 * [shell](shell.md) - opens a shell within the contained environment;
 * [tool](tool.md) - invoke a specific action of a selected tool;
 * [tools](tools.md) - lists all available [tools](../syntax/tools.md).

## Usage Example

```bash
$> bw --help
Usage: bw [OPTIONS] COMMAND [ARGS]...

Options:
  -C, --cwd DIRECTORY  Override the working directory
  --help               Show this message and exit.

Commands:
  info   List information about the project
  shell
  tools  Tabulate all of the available tools
```
