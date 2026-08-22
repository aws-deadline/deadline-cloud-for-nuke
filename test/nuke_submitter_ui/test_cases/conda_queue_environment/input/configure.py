# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Configurator for conda_queue_environment.

Port of the Squish invalid_conda_gui case, with the subject changed on
purpose. Squish typed a non-existent package and asserted the submission
failed, which is a farm-side outcome nothing here can reproduce. What is
verifiable offline is the client-side contract that case relied on: the
submitter fills these fields in for the running Nuke, the client adds the
deadline-cloud-v2 channel, and typed values reach the bundle unaltered. That
last part is why an invalid package fails on the farm rather than being
swallowed in the submitter.
"""

INVALID_PACKAGES = "invalid-package=1.0"
INVALID_CHANNEL = "invalid-channel"


def configure(dialog) -> None:
    dialog.set_job_name("Invalid Conda Settings Job")
    dialog.set_job_description("This test verifies handling of invalid Conda packages and channels")

    packages = dialog.conda_packages()
    assert (
        "nuke=" in packages and "nuke-openjd=" in packages
    ), f"expected auto-populated Nuke and adaptor versions; saw {packages!r}"
    channels = dialog.conda_channels()
    assert channels.split()[:2] == [
        "deadline-cloud-v2",
        "deadline-cloud",
    ], f"expected the v2 channel ahead of the default; saw {channels!r}"

    dialog.set_conda_packages(INVALID_PACKAGES)
    dialog.set_conda_channels(INVALID_CHANNEL)
    assert dialog.conda_packages() == INVALID_PACKAGES
    assert dialog.conda_channels() == INVALID_CHANNEL
