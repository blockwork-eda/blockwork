Caching is configured through `.yaml` files. The `.bw.yaml`
(see [bw_yaml](../config/bw_yaml.md)) defines the default caching configuration
but this can be overriden on the command line with the `--cache-config` option.

Each caching configuration must use a `!Caching` tag as its root element, as
per the example below:

```yaml linenums="1"
!Caching
enabled: True
targets: False
caches:
- !Cache
  path: infra.caches.Local
  fetch_condition: True
  store_condition: True
  max_size: 5GB
- !Cache
  path: infra.caches.FileStore
  fetch_condition: 10 MB/s
  store_condition: False

```

The fields of the `!Caching` tag are:

| Field                | Default | Description                                                        |
|----------------------|-------- |--------------------------------------------------------------------|
| enabled              | `True`  | Whether to enable caching by default (overridable on command line) |
| targets              | `False` | Whether to pull targetted<sup>1</sup> transforms from the cache    |
| caches               | `[]`    | A list of `!Cache` configurations (see below)                      |


<sup>1</sup> Targetted transforms are those selected to be run by a workflow,
in contrast to those which are only dependencies of targetted transforms.


The fields of the `!Cache` tag are:

| Field           | Required         | Default | Description                                                        |
|-----------------|:----------------:|-------- |--------------------------------------------------------------------|
| path            | :material-check: |         | The python import path to the cache implementation<sup>2</sup>     |
| max_size        |                  | `None`  | The maximum cache size, which the cache will self-prune down to    |
| store_condition |                  | `False` | The condition for storing to the cache<sup>3</sup>                 |
| fetch_condition |                  | `False` | The condition for fetching from the cache<sup>3</sup>              |
| check_only      |                  | `False` | A list of !Cache configurations (see below)                        |

<sup>2</sup> Specified as `<package>.<sub-package>.<class-name>`

<sup>3</sup> Specified as:

 - `True`: Always store-to or fetch-from this cache
 - `False`: Never store-to or fetch-from this cache
 - `<x>B/s`: Only store-to or fetch-from this cache if the transforms byte-rate
  is below the provided value. This is useful when a cache is networked, and it
  may be more efficient to just re-compute quick-to-run, high-output transforms
  than pull them down. Some example values are:
    - `1B/s`: > 1 second to create each byte.
    - `1GB/h`: > 1 hour to create each Gigabyte.
    - `5MB/4m` > 4 minutes to create each 5 Megabytes.

    Note: The rate-specification may be removed in the future, in favour of a
    dynamic scheme.
