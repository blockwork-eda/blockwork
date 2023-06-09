# blockwork

## X11 Forwarding under macOS

 * Install XQuartz
 * Tick "Allow connections from network clients" in XQuartz preferences
 * Quit and re-open XQuartz
 * Execute `xhost + 127.0.0.1`
 * `DISPLAY` must be set to `host.containers.internal:0`

## Podman Socket on Ubuntu

To start the socket service execute:

```bash
$> systemctl --user status podman.socket
```

## Podman Slow on Ubuntu

Ensure that you are using the overlay filesystem (`fuse-overlayfs`), as the
default `vfs` is very slow!

```bash
$> sudo apt install -y fuse-overlayfs
$> podman system reset
$> podman info --debug | grep graphDriverName
```

If the `graphDriverName` is not reported as `overlay`, then you can try forcing
it by editing `~/.config/containers/storage.conf` to contain:

```toml
[storage]
driver = "overlay"
```

Then execute `podman system reset` again, and perform the same check for the
graph driver.

After changing the filesystem driver, you will need to rebuild the foundation
container as it is deleted by the reset command.
