# Foundation Container

This directory contains the definition of the foundation container.

## Building

```bash
$> cd containers/foundation
$> podman build --file=Containerfile --format=oci --rm=true --tag=foundation .
```

## Saving

```bash
$> podman save foundation --format=oci-archive --output=foundation.tar
```
