# AWS Deadline Cloud for Nuke

### [User guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/foundry-nuke.html) | [Service documentation](https://docs.aws.amazon.com/deadline-cloud/) | [Deadline Cloud on GitHub](https://github.com/aws-deadline/) 

[![pypi](https://img.shields.io/pypi/v/deadline-cloud-for-nuke.svg?style=flat)](https://pypi.python.org/pypi/deadline-cloud-for-nuke)
[![python](https://img.shields.io/pypi/pyversions/deadline-cloud-for-nuke.svg?style=flat)](https://pypi.python.org/pypi/deadline-cloud-for-nuke)
[![license](https://img.shields.io/pypi/l/deadline-cloud-for-nuke.svg?style=flat)](https://github.com/aws-deadline/deadline-cloud-for-nuke/blob/mainline/LICENSE)

AWS Deadline Cloud for Nuke is a python package that allows users to create [AWS Deadline Cloud][deadline-cloud] jobs from within Nuke. Using the [Open Job Description (OpenJD) Adaptor Runtime][openjd-adaptor-runtime] this package also provides a command line application that adapts Nuke's command line interface to support the [OpenJD specification][openjd].

[deadline-cloud]: https://docs.aws.amazon.com/deadline-cloud/latest/userguide/what-is-deadline-cloud.html
[deadline-cloud-client]: https://github.com/aws-deadline/deadline-cloud
[openjd]: https://github.com/OpenJobDescription/openjd-specifications/wiki
[openjd-adaptor-runtime]: https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python
[openjd-adaptor-runtime-lifecycle]: https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/release/README.md#adaptor-lifecycle

## Compatibility

This library requires:

1. Nuke 15, 16, or 17.
1. Python 3.9 or higher.
1. Linux, Windows, or a macOS operating system.

## Submitter

This package provides a Nuke plugin that creates jobs for AWS Deadline Cloud using the [AWS Deadline Cloud client library][deadline-cloud-client]. Based on the loaded comp it determines the files required, allows the user to specify render options, and builds an [OpenJD template][openjd] that defines the workflow.

The submitter supports [task chunking][task-chunking], which groups multiple frames into contiguous chunks to reduce per-task overhead. When combined with the adaptor's sticky rendering, this provides optimal performance by eliminating both repeated application startup and scene loading time.

[task-chunking]: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle-chunking.html

## Submission Hooks

The Nuke submitter supports Deadline Cloud **submission hooks** — studio scripts that run at
submission time: **pre-GUI** hooks pre-populate the submitter dialog before it opens, and
**pre-/post-submission** hooks run before files are uploaded and after the job is created. Both
submitter menu items run these hooks — **AWS Deadline → Submit to Deadline Cloud** and **AWS
Deadline → Submit CopyCat Training to Deadline Cloud**.

Enable environment-sourced hooks (from the directory named by `DEADLINE_HOOKS_DIR`), which are off
by default:
```
deadline config set settings.allow_environment_hooks true
```
At pre-GUI time the Nuke submitter has no on-disk job bundle, so `DEADLINE_HOOKS_DIR` is its only
pre-GUI hook source; pre-/post-submission hooks can additionally come from a bundle `hooks.yaml`
(gated by `settings.allow_bundle_hooks`).

For the `hooks.yaml` format, the hook stdin/stdout contract, the recognized `deadline:` job
properties, and the confirmation-prompt / `settings.auto_accept` behavior, see the base client
documentation: [docs/submission-hooks.md](https://github.com/aws-deadline/deadline-cloud/blob/mainline/docs/submission-hooks.md).

A few things differ for the in-process Nuke submitter and are worth knowing before following that doc:

- **What a pre-GUI hook can set:** `name`, `description`, the `deadline:` job properties, and queue
  parameters your queue exposes (e.g. `CondaPackages`, `RezPackages`, `CondaChannels`). It cannot set
  Nuke job-template parameters (frame range, write node, view, chunk size, etc.) — the submitter
  rebuilds those from the dialog's scene settings at bundle-build time, so hook values for them are
  silently ignored.
- **No job-type distinction:** hooks run for both the render and CopyCat-training dialogs with the
  same `submitterName` (`"nuke"`) and no job-type field, so a hook cannot tell them apart. Write it
  to be job-type agnostic — e.g. extend the incoming `CondaPackages` rather than hardcoding a
  render-only value (CopyCat jobs do not use `nuke-openjd`).
- **Hook output is not surfaced in Nuke:** pre-GUI hook progress and failure diagnostics are not
  streamed to the artist or shown in the Script Editor; they are written to
  `~/.deadline/logs/submitters/nuke.log` (and `INFO`-level lines appear there only if the `deadline`
  logger level is lowered). To iterate on a pre-GUI hook with visible output, run it under
  `deadline bundle gui-submit`.

## Adaptor

The Nuke Adaptor implements the [OpenJD][openjd-adaptor-runtime] interface that allows render workloads to launch Nuke and feed it commands. This gives the following benefits:
* a standardized render application interface,
* sticky rendering, where the application stays open between tasks,
* path mapping, that enables cross-platform rendering

Jobs created by the submitter use this adaptor by default, and that both the installed adaptor
and the Nuke executable be available on the PATH of the user that will be running your jobs.

Or you can set the `NUKE_EXECUTABLE` to point to the Nuke executable.

### Getting Started

The adaptor can be installed by the standard python packaging mechanisms:
```sh
$ pip install deadline-cloud-for-nuke
```

After installation it can then be used as a command line tool:
```sh
$ nuke-openjd --help
```

For more information on the commands the OpenJD adaptor runtime provides, see [here][openjd-adaptor-runtime-lifecycle].

## Versioning

This package's version follows [Semantic Versioning 2.0](https://semver.org/), but is still considered to be in its
initial development, thus backwards incompatible versions are denoted by minor version bumps. To help illustrate how
versions will increment during this initial development stage, they are described below:

1. The MAJOR version is currently 0, indicating initial development.
2. The MINOR version is currently incremented when backwards incompatible changes are introduced to the public API.
3. The PATCH version is currently incremented when bug fixes or backwards compatible changes are introduced to the public API.

## Security

See [CONTRIBUTING](https://github.com/aws-deadline/deadline-cloud-for-nuke/blob/release/CONTRIBUTING.md#security-issue-notifications) for more information.

## Telemetry

See the [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/opt-out.html) for more information.

## License

This project is licensed under the Apache-2.0 License.
