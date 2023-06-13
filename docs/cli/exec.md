The `exec` command executes a shell command within the contained environment,
binding in as many tools as requested. It can be made to run interactively (i.e.
the TTY forwards both STDIN and STDOUT) if required.

The exit code of the contained process will be forwarded to the host, so that it
can be used in a script's control flow.

The `exec` command has no sub-commands.

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

 * `--no-tools` - disable automatic binding of all known tools into the container;
 * `--interactive` / `-i` - attaches a TTY onto the shell and interactively
   forwards STDIN and STDOUT;
 * `--cwd <DIR>` - optionally set the working directory, defaults to using the
   container project root.

## Arguments

All positional and unrecognised arguments will be taken as being part of the
command to execute. The `--` delimiter may be used to explicitly mark the end of
the arguments to Blockwork and the start of the command to execute.

## Usage Example

With implicit separation between Blockwork arguments and the command:

```bash
$> bw exec --tool pythonsite python3 my_script.py
```

However, if the command needs to take any `-` or `--` arguments then explicit
separation must be used. For example:

```bash
$ bw exec --tool pythonsite python3 -c "print('hello')"
Usage: bw exec [OPTIONS] [RUNARGS]...
Try 'bw exec --help' for help.

Error: No such option: -c
```

So instead the `--` delimiter should be used:

```bash
$> bw exec --tool pythonsite -- python3 -c "print('hello')"
hello
```
