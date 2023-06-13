The `tool` command launches an action offered by a [Tool](../syntax/tools.md)
declaration (see the [Tool](../syntax/tools.md) documentation on how actions are
declared). These can run interactively and with X11 display forwarding, as
specified by the action.

Similarly to [exec](exec.md), the exit code of the contained process will be
forwarded to the host.

The `tool` command has no sub-commands or options of its own so all positional
arguments, and those after a `--` delimiter, are forwarded to the action.

## Usage Example

As with [exec](exec.md), using the explicit argument delimiter is recommended:

```bash
$> bw tool gtkwave.view -- a/waves.vcd b/waves.gtkw
```
