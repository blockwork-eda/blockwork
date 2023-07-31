![Blockwork](docs/assets/mascot_b_black_e_white.png)

**NOTE** Blockwork is currently in active development and is not yet suitable
for production environments. It is missing many features and does not yet fulfill
its stated aims.

# Getting Started

## Recommended Pre-requisites for macOS

On macOS we recommend the following:

 * [XQuartz](https://www.xquartz.org) - to support X11 forwarding from applications
   running in the contained environment.
 * [Docker](http://docker.com) or [Orbstack](https://orbstack.dev) as the container
   runtime. [Podman](https://podman-desktop.io) is supported but it exhibits poor
   filesystem performance.
 * Python 3.11 installed through [pyenv](https://github.com/pyenv/pyenv) to
   protect your OS's default install from contamination.
 * [Poetry](https://python-poetry.org) installed through Python's package manager
   i.e. `python -m pip install poetry`.

## Recommended Pre-requisites for Linux

On Linux we recommend the following:

 * [Docker](http://docker.com) as the container runtime. [Podman](https://podman-desktop.io)
   is supported but it exhibits poor filesystem performance (there are some notes
   to improve this in the [troubleshooting section](#troubleshooting)).
 * Python 3.11 installed through [pyenv](https://github.com/pyenv/pyenv) to
   protect your OS's default install from contamination.
 * [Poetry](https://python-poetry.org) installed through Python's package manager
   i.e. `python -m pip install poetry`.

## Installing Blockwork

To install the bleeding edge version of Blockwork, use the following command:

```bash
$> python3 -m pip install git+https://github.com/blockwork-eda/blockwork
```

## Setting up a Development Environment

Follow these steps to get a development environment:

```bash
# Clone the repository
$> git clone git@github.com:blockwork-eda/blockwork.git
$> cd blockwork
# Activate a poetry shell
$> poetry shell
# Install all dependencies (including those just for development)
$> poetry install --with=dev
# Bootstrap the example project
$> bw -C example bootstrap
# Run a test command
$> bw -C example exec -- echo "hi"
```

# Troubleshooting

## macOS

### X11 Forwarding

 * Ensure [XQuartz](https://www.xquartz.org) is installed
 * Tick "Allow connections from network clients" in XQuartz preferences
 * Quit and re-open XQuartz
 * Execute `xhost + 127.0.0.1`


**NOTE** The `DISPLAY` environment variable must be set to `host.internal:0` for
Docker/Orbstack or `host.containers.internal:0` for Podman, this should be setup
automatically by the framework.

## Linux

### Podman Socket

To start the user-space socket service execute:

```bash
$> systemctl --user status podman.socket
```

**NOTE** Do not use `sudo` as the service needs to run in user-space.

### Slow Podman Performance

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
