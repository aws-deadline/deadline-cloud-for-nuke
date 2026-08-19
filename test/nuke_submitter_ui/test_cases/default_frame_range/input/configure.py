# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Dialog configurator for the default_frame_range case.

Port of the Squish default_frame_range_gui case: submit WITHOUT touching
the frame-range controls, so the golden's Frames parameter proves the
scene's own root range (25-75, set by scene.py) is inherited. The override
checkbox is asserted off rather than set, since inheriting the scene range
is exactly what this case verifies.
"""


def configure(dialog) -> None:
    dialog.set_job_name("Default Frame Range Job")
    dialog.set_job_description(
        "This test verifies that the default frame range specified in the Nuke Script is used"
    )
    dialog.switch_to_job_specific_tab()
    dialog.select_write_node("Write1")
    assert not dialog.override_frame_range_enabled(), (
        "the frame-range override is on by default in this dialog; this case must submit with it "
        "off to prove the scene range is inherited"
    )
