# Introduction

Configuration in Blockwork is used to configure Blockwork itself (`.bw.yaml`) 
and separately to define the graph of objects to build. 

These two use-cases are very different, and generally we'll use 'configuration'
or 'block configuration' to refer to the latter case and 'root configuration'
to refer to the former.

Root configuration:
 - is internally defined by blockwork
 - defines meta information
 - defines various configurable global paths
 - defines where to find the definitions of tools, transforms
 - defines where to find the definitions of block configuration

Block configuration:
 - is defined by users of blockwork
 - is used as the target of workflows
 - defines transforms and how they link together to create build graphs
 - defines workflows

Both are:
 - Specified in YAML
 - Defined as python dataclasses
 - Type-checked at runtime

See [the documentation on root configuration](./bw_yaml.md) for a detailed
reference on the bw.yaml file.

Read on for more information on how configuration is implemented.


# Configuration Internals

This section describes the internals of how Blockwork's configuration works and
is intended to primarily help those wanting to contribute to Blockwork rather
than those wanting only to use it. 

Configuration is written in YAML but defined in Python as 
[type checked dataclasses](#checked-dataclasses) which are converted from YAML
using [YAML converters and parser](#yaml-converters-and-parsers).

We use [Into](#into) to allow type coercian in config files and enable a lot of
flexibility, and [scopes](#scopes) to make context dependent data and 
functionality available where it's needed.


## Checked Dataclasses

Blockwork defines a wrapper around [Python Dataclasses](https://docs.python.org/3/library/dataclasses.html) 
which uses the (very cool) [Typeguard library](https://github.com/agronholm/typeguard)
to perform runtime type checking on Dataclasses. The wrapper module is
unimaginately named `checkeddataclasses`. We use this internally in places
where user defined data is passed  into Blockwork, but we primarily use it to
type check configuration.

There are a couple of known limitations:
 - Typeguard cannot check forward type declarations, i.e. type declarations 
   that need to be quoted so that they can refer to types that are defined
   later in a file. We've found it common to have recursive Blockwork 
   configuration that encounters this issue and becomes unchecked.
 - A callback mechanism to coerce types would give us a lot of flexibility.
   It is sometimes useful to define a value as a "type that can be converted
   into another type" rather than the type itself. This is the reason the 
   utility [Into](#into) was created, and is partially resolved by it.


## Into

Blockwork uses 'Into' to allow for more flexibility in configuration. It allows
types to be defined as 'any type that can be converted into X or X itself', the
registering of converters between another type and 'X' and a method to try and 
convert into X from other types.

This is useful for creating flexible configuration that can accept options in
many different forms, without having to be aware-of and handle them all. An
example is configuration that takes a string, does it matter to the consumer 
if the string instead comes from a structured field with a string
representation?

The main limitations of 'Into' are that consumers need to be aware of it and
make a call to do the conversion explicitely, and that it defers some of the
type checking until the conversion occurs (this has potential to be resolved).


## Yaml Converters and Parsers

Blockwork uses [PyYAML](https://github.com/yaml/pyyaml) to parse YAML files 
into python objects but wraps around it with Converters and Parsers. 

Converters are used to define how to convert between a YAML Tag and a Python
type. Tags are used to denote types in YAML and start with an exclamation 
mark `!`.

Parsers are wrappers around PyYAML's loaders and dumpers and can be considered
as collections of converters that can be used to parse a YAML file. Converters
are registered with particular parsers rather than globally, meaning we can
scope which tags and types are valid in which file context.

When a YAML file is parsed, it can optionally be parsed with an expected type
for the top level.


### Dataclass Converter

We define a dataclass converter which can be used with or without
[checked dataclasses](#checked-dataclasses) and provides an easy way of
defining structured configuration and easy access in Python. The dataclass
fields as specified as a mapping in YAML. We use this for the root
configuration. 


### Config Converter

We further wrap the dataclass converter for use with block configuration. All
block configuration must subclass the Config class which is created by this
converter and has additional functionality beyond a dataclass, see 
<!-- TODO REF --> for more details of the Config class.

The config converter:
 - allows elements to either be specified in place as a mapping (as with the 
   dataclass converter), or as a reference to another file who's root element
   must be the matching type.
 - wraps the config creation with a context dependent api scope through which
   various context dependent functionality can be accessed, for example,
   resolving a file relative to the current block. See the [Scopes](#scopes) 
   utility for more details on scopes and <!-- TODO API REF --> for more details 
   on config API.


## Scopes

The scopes utilities simply create context managers which hold a stack of data
and provide access to the top of the stack. This is particularly useful when
you have data that you cannot or do not wish to pass down through layers of
function calls. An example of where it's used in Blockwork is to pass verbosity
configuration through to logging functions. We also use it to create the 
`api` property on Config elements, see <!-- TODO API REF --> and <!-- TODO Config REF -->.
