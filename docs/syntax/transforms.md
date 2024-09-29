# Transform Syntax

Transforms are a definition of how to process a set of inputs to get a set
of outputs. The inputs and outputs to transforms are collectively termed
"interfaces" and should include everything a transform needs to run.

This document covers the syntax of transforms. We will start with a simple
example introducing the main elements, then do a deep dive on each.

## Basic Defintion

```python
from blockwork.transforms import Transform

class Copy(Transform):
    tools = (Bash,)
    frm: Path = Transform.IN()
    to: Path = Transform.OUT(init=True)

    def execute(self, ctx, tools):
        copy = tools.bash.get_action("cp")
        yield copy(ctx, frm=self.frm, to=self.to)
```

The first thing to note is that all transforms must inherit from the Transform
class which does lots of setup behind the scenes.

Next we have some class variables.

```python
tools = (Bash,)
```

> Here `tools` is a reserved class variable, and should be a a tuple listing the
> tools the transform uses. In this case, the transform uses the Bash tool.

```python
frm: Path = Transform.IN()
```

> Here we define an inbound interface with the name `frm` and the type `Path`

```python
to: Path = Transform.OUT(init=True)
```

> Here we define an outbound interface with the name `to`, the type `Path` and
> the field option `init` (see section on interfaces for what that means).

```python
def execute(self, ctx, tools, iface):
```

> The execute method defines the process to produce tranform outputs from
> transform inputs. The three arguments are as follows:
>
> 1. `ctx` the Blockwork context object, which has many useful values and

     methods.

> 2. `tools` the tools that are mapped into the container
> 3. `iface` the values provided by the interfaces, mapped into the container.

```python
copy = tools.bash.get_action("cp")
```

> Retrieves an action named `cp` from the bash tool

```python
yield copy(ctx, frm=iface.frm, to=iface.to)
```

> Reads the values from the `frm` and `to` interfaces, and passes them through
> to the copy action. Actions must be yielded in order to run.

## Basic Use

We use transforms by instantiating them, and calling the run method as follows:

```python
tf = Copy(frm=Path('/my/input/path'), to=Path('my/output/path'))
# Where ctx is the blockwork context object
tf.run(ctx)
```

## Interfaces

Interfaces are defined with a _name_, a _type_, a _direction_, and _options_.
The _name_ and _direction_ are trivial and indicated by the property name, and
the `IN` and `OUT` in `Transform.IN()` and `Transform.OUT()` respectively. The
_type_ and _options_ have more depth and will be the focus of this
section, starting with options.

### Options

Options are passed in through the `IN` and `OUT` transform methods. They will
are best described by example.

```python
files: dict[str, Path] = Transform.IN()
```

> An input interface which accepts a dictionary of paths and exposes them
> inside the container

```python
name: str = Transform.IN(env="NAME", default="Blocky")
```

> An optional input interface with a default value, and which additionally
> exposes the value in an environment variable `$NAME`.

```python
pypath: list[Path] = Transform.IN(env="PYTHONPATH", env_policy=EnvPolicy.APPEND, default_factory=list)
```

> An optional input interface with a default which accepts a list of paths
> and exposes them in an environment variable `$PYTHONPATH`. The specified
> `env_policy` indicates the new items should be added to the env of the env
> variable if it is already set, see the section on `IEnv` for detail.

```python
result: Path = Transform.OUT()
```

> An automatic output interface. The output path will be automatically
> generated based on the transform directory and the interface name. This field
> cannot be set when instancing the transform.

```python
result: Path = Transform.OUT(init=True)
```

> An initialised output interface. The output path must be specified when the
> transform is instanced. It will not be set automatically if not supplied.

```python
result: Path = Transform.OUT(init=True, default=...)
```

> An initialisable output interface with an automatic default if a value is not
> specified. The magic value '...' can also be used with input interfaces
> for list and dict types to create an empty list or dict.

## Types

Interface fields accept the following constant types:

- `str`
- `int`
- `float`
- `bool`
- `None`

Along with the additional interface primitives:

- `Path` (from `pathlib`)
- `IPath` (`Blockwork.transforms.IPath`)
- `IEnv` (`Blockwork.transforms.IEnv`)
- `IFace` (`Blockwork.transforms.IFace`)

And the collection types (which can contain any of the above):

- `list`
- `dict` (keys must be strings)

The constant and collection types are straightforward, they will appear in
the execute method's `iface` argument exactly as they are specified.

The interface primitives require further discussion.

### Path and IPath

When `Path` is used, the value specified will be taken as a path on the host
machine. When the execute method is called, the path is mapped into the
container (the directory becomes available in the container under a
different name), and the mapped container path is exposed in the `iface`
argument. The directory where the path is bound is selected automatically.

`IPath` gives more control, it allows you to specify both the host path
and the container path which it will get mapped to. It also allows you
to specify a path on the container without mapping one from the host by
setting the host path to None.

```Python
class MyTF(Transform):
    inbound: IPath = Transform.IN()
    ...

MyTF(inbound=IPath(host='/some/host/path', cont='/some/cont/path'))
```

### IEnv

`IEnv` is used to pass arbitrary environment into the container, as opposed
to the `env='NAME'` field option which is used to pass specific environment
variables with a name known when the transform is defined. This is useful for
writing generic and reusable transforms. `IEnv` accepts the following value
types:

- `str`
- `int`/`float` (coerced to `str`)
- `Path`/`IPath` (mapped as above)
- `None` (ignored)
- `list` (of any mix of the above)

`IEnv` also accepts a `policy` argument which controls it's behaviour if a
variable is already set (the same behaviour is applied for lists of values).
The following policies are available:

conflict
: The default, raise an error if the value is already set.

append
: Append to the existing value with '`:`' separator.

prepend
: Prepend to the existing value with '`:`' separator. Note, when a list
of values `['a','b','c']` is provided the resultant env string will be
reversed `c:b:a`.

replace
: Replace the existing value with the new one. Note, when a list of values
is provided, this will result in only the last value being used.

```Python
class MyTF(Transform):
    env: list[Env] = Transform.IN()
    ...

MyTF(env=[IEnv("VERBOSITY", "INFO", policy="replace")])
```
