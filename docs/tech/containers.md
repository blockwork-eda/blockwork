Containerisation allows build environments to be created that are separated from
the host operating system. They are widely used in software development for both
their ease of deployment, and for the security benefits they bring in isolating
an application from other software running around it. For Blockwork, containers
bring a number of benefits:

 * Controlled environments - commercial EDA tools often come with a detailed
   specification for exactly how the host should be configured including OS,
   libraries, and versions of other tools like Perl and Tcl. It is not uncommon
   for different EDA tools to have conflicting requirements, and containers give
   a way to effectively manage these different environments.

 * Portability - modern commercial development environments are often heterogenous,
   mixing on-site and remote compute ('hybrid cloud'). Being able to reliably
   reproduce the same environment on different systems is essential. The fewer
   requirements placed on the host system the better, so a minimal install of
   only a container runtime and Blockwork is ideal.

 * Dependency tracking - silicon design flows often comprise pipelines with
   significant depth, that pull in information from many different places. It is
   often difficult to discern the complete list of files required by any given
   step. By using a container, a virtual filesystem is created that can selectively
   bind different files and folders from a project area. In this way, dependencies
   that are not identified will simply be unavailable to the transformation.

There are a number of factors to consider in how containers are used, which will
be addressed in the following sections.

## Managing Tools

A flow may need to use many different tools in varying combinations as it executes,
and there are two main ways to address this.

### 1. Bundle Tools into the Container Image

Custom containers can be defined using a number of formats, the most common being
the proprietary Dockerfile and the OCI's Containerfile. These definitions identify
files to be copied into the container images and list any number of required build
stages. Once the container is built, the image can be inherited to form further
images and any number of instances may be launched.

The upside of this approach is that once the container is launched, tool launch
times are fast as accessing local disk. Container images can also be distributed
as a compressed archive, which makes it easy to reproduce an environment.

However, if the desire is to only load tools matched to the activity being performed
then the number of containers quickly explodes. For example, with just four tools
(e.g. GCC, Python, Icarus Verilog, and Verilator) there are already 15 unique
combination - and this doesn't take account of the possibility of multiple tool
versions (e.g. Python 3.8 vs 3.11). The use of inheritance (e.g. root container has
GCC, then is inherited to add Python) makes this problem slightly more tractable,
but then leads to a high penalty for changing the tool version in a root container as
all downstream containers need to be rebuilt.

### 2. Bind Tools at Runtime into the Container Instance

A compelling alternative is to built a light-weight container with a minimal load-out
of standard tools - for example taking a Rocky Linux container image and adding
`iputils` (for `ping`) and `wget` (for downloading files). Then, instead of creating
lots of variants, instead 'bind' tools from the host into the container image.

The upside of this approach is that any combination of tools and versions can be
active without the penalty of rebuilding the container image. Overall this takes up
considerably less disk space as tool installations are not replicated in different
images.

This approach is not without issue however - firstly it means now distributing both
the container image along with pre-built copies of required tools. Secondly, the
performance of binds into the virtual filesystem can be highly variable across
different platforms and container runtimes. For example, Docker on macOS can use the
virtio-fs FUSE-based filesystem which has good performance, but Podman uses the
significantly less performant virtio-9p filesystem. This difference in performance
is quite noticeable when launching lots of tools from bound mounts.

### 3. Store Tools in Volumes

This option is still to be explored and is very similar to option 2 except that
rather than storing tools on the host's filesystem, they would instead be kept
in container volumes. These can be selectively attached to the container in a
similar fashion, but would seem to have better I/O performance than direct binds.

### Outcome

Blockwork adopts the second approach and binds tools from the host into a baseline
container image. This is chosen as it is significantly more flexible, and the
performance issues seen with some container runtimes can be avoided by selecting
the best virtual filesystem for the platform.

### Syntax

The syntax for defining tools is explained [here](../syntax/tools.md).

## API Access

So far programmattic access to the container runtime has been implied but not
explicitly detailed. Most container runtimes expose REST APIs that are compatible
with the Docker API, even though they are not based on the Docker runtime. This is
done to ensure compatibility with the wider Docker ecosystem (e.g. Kubernetes).

The Docker API offers a robust complement of methods for creating, launching, and
interacting with containers, and Blockwork wraps this to provide reusable methods
for launching build steps with different tools bound in.

During development, the use of alternative APIs such as Podman's REST API, were
explored but the Python client implementation was found to be lacking an
implementation of methods such as `attach`. The Docker Python client does support
these methods, and interacts well with the Podman API.

## Running Interactively

While many tasks such as compilation or executing a script can be performed
non-interactively, other tasks may require input to the console or via a GUI. Either
of these mechanisms means that the host needs to be able to establish an active
connection with the container.

Interactive shell access is achieved via the `attach` Docker API method, this
creates a bi-directional text link to the container which forwards STDIN from the
host and prints out STDOUT and STDERR received from the container. STDIO is
processed byte-by-byte to ensure all terminal features such as colour sequences
and control keys (arrows, etc) are handled correctly.

GUI access is achieved by forwarding X11 connections from the container to the host.
This is handled in various ways by different platforms:

 * On macOS the container can connect to XQuartz running on the host by using
   the `host.containers.internal` host entry;
 * On Debian the container can connect to the host's X-server by binding the
   X11 socket file (`/tmp/.X11-unix`) into the container.

The container launch routine can abstract this complexity so that X11 applications
starting within the container do not need to concern themselves with the behaviour
of the host.
