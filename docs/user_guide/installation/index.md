# Installing AWS Deadline Cloud for Nuke 

To install the AWS Deadline Cloud for Nuke submitter, you will need:

- A Windows, MacOS, or Linux workstation
- Nuke 14, 15 or 16. We recommend Nuke 15 or 16 over Nuke 14, as these versions are supported by the [default Conda queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment) on service-managed fleets. To use Nuke 14 with a service-managed fleet you will need to make Nuke 14 available to the worker. The recommended way of doing this would be to create your own Conda package following the documentation [here](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/conda-package.html).

There are two ways to install the Deadline Cloud for Nuke submitter:

- [Using the Deadline Cloud submitter installer](installation.md) (recommended)
- [Manually installing the submitter from source](https://github.com/aws-deadline/deadline-cloud-for-nuke/blob/mainline/DEVELOPMENT.md#manual-installation) (links to GitHub)