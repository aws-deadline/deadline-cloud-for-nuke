# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Dialog configurator for the custom_frame_range case.

Port of the Squish custom_frame_range_gui case: enable the frame-range
override and submit a range (1-10) narrower than the scene's own 1-100, so
the golden's Frames parameter proves the override was applied rather than
the scene range inherited.
"""

FRAME_RANGE = "1-10"


def configure(dialog) -> None:
    dialog.set_job_name("Custom Frame Range Job")
    dialog.set_job_description("This test verifies that a custom frame range can be specified")
    dialog.switch_to_job_specific_tab()
    dialog.select_write_node("Write1")
    dialog.set_frame_range(FRAME_RANGE)
    assert (
        dialog.frame_range_field().element().value == FRAME_RANGE
    ), "frame-range override did not take the typed value"
