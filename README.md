# Amazon Deadline Cloud for Nuke

This package provides user interface inside of Nuke for submitting jobs to Deadline Cloud, and
an adaptor that runs Nuke on render hosts.

This package has two active branches:

- `mainline` -- For active development. This branch is not intended to be consumed by other packages. Any commit to this branch may break APIs, dependencies, and so on, and thus break any consumer without notice.
- `release` -- The official release of the package intended for consumers. Any breaking releases will be accompanied with an increase to this package's interface version.

## Development Process

See [DEVELOPMENT](DEVELOPMENT.md) for information about developing this package.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the Apache-2.0 License.
