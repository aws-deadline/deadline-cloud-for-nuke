[![pypi](https://img.shields.io/pypi/v/deadline-cloud-for-nuke.svg?style=flat)](https://pypi.python.org/pypi/deadline-cloud-for-nuke)
[![python](https://img.shields.io/pypi/pyversions/deadline-cloud-for-nuke.svg?style=flat)](https://pypi.python.org/pypi/deadline-cloud-for-nuke)
[![license](https://img.shields.io/pypi/l/deadline-cloud-for-nuke.svg?style=flat)](https://github.com/aws-deadline/deadline-cloud-for-nuke/blob/mainline/LICENSE)

# AWS Deadline Cloud for Nuke

AWS Deadline Cloud for Nuke is a python package that allows users to create [AWS Deadline Cloud][deadline-cloud] jobs from within Nuke. Using the [Open Job Description (OpenJD) Adaptor Runtime][openjd-adaptor-runtime] this package also provides a command line application that adapts Nuke's command line interface to support the [OpenJD specification][openjd].

[deadline-cloud]: https://docs.aws.amazon.com/deadline-cloud/latest/userguide/what-is-deadline-cloud.html
[deadline-cloud-client]: https://github.com/aws-deadline/deadline-cloud
[openjd]: https://github.com/OpenJobDescription/openjd-specifications/wiki
[openjd-adaptor-runtime]: https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python
[openjd-adaptor-runtime-lifecycle]: https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python/blob/release/README.md#adaptor-lifecycle

## Compatibility

This library requires:

1. Nuke 15,
1. Python 3.9 or higher; and
1. Linux, Windows, or a macOS operating system.

## Submitter

This package provides a Nuke plugin that creates jobs for AWS Deadline Cloud using the [AWS Deadline Cloud client library][deadline-cloud-client]. Based on the loaded comp it determines the files required, allows the user to specify render options, and builds an [OpenJD template][openjd] that defines the workflow.

### Getting Started

To install the submitter manually, you can use `pip`.

1. Install the package using `pip`.
    ```sh
    pip install deadline-cloud-for-nuke -t <target-directory>
    ```

2. Set the `NUKE_PATH` environment variable.
    For Windows,
    ```sh
    set NUKE_PATH=<target-directory>;<target-directory>/deadline/nuke_submitter
    ```

    For Linux and MacOS:
    ```sh
    export NUKE_PATH=<target-directory>:<target-directory>/deadline/nuke_submitter
    ```

3. After installation and within the same terminal, run `Nuke<version>` executable. The Nuke submitter should now be available in the AWS Deadline menu.

    NOTE: If you want the submitter available outside of this shell, consider using `NUKE_PATH` as an environment variable rather than a shell variable.

## Adaptor

The Nuke Adaptor implements the [OpenJD][openjd-adaptor-runtime] interface that allows render workloads to launch Nuke and feed it commands. This gives the following benefits:
* a standardized render application interface,
* sticky rendering, where the application stays open between tasks,
* path mapping, that enables cross-platform rendering

Jobs created by the submitter use this adaptor by default.

### Getting Started

The adaptor can be installed by the standard python packaging mechanisms:
```sh
pip install deadline-cloud-for-nuke
```

After installation it can then be used as a command line tool:
```sh
nuke-openjd --help
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

See [telemetry](https://github.com/aws-deadline/deadline-cloud-for-nuke/blob/release/docs/telemetry.md) for more information.

## License

This project is licensed under the Apache-2.0 License.
