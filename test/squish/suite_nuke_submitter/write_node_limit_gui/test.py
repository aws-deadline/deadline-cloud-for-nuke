# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# mypy: disable-error-code="attr-defined"
import names
import squish_helpers
import squish

"""
GUI test for submitting a Nuke job with write nodes that have frame range limits to AWS Deadline Cloud.

This test verifies that the submitter correctly handles write nodes with frame range restrictions:
This test uses a Nuke script containing write nodes with specific frame range limits and submits 
a job targeting one of these write nodes. This test ensures that the submitter properly detects 
and respects the frame range limits defined in the write node, preventing rendering outside the 
node's specified frame range regardless of the project's overall frame range.
"""


def main():
    squish_helpers.launch_nuke()
    squish.setWindowState(
        squish.waitForObject(names.nukeMainWindow_Foundry_UI_DockMainWindow),
        squish.WindowState.Maximize,
    )
    squish_helpers.open_nuke_script(
        "intro_to_compositing_test_samples", "Shot002_modified_write_frame_limits.nk"
    )
    squish.snooze(3)
    squish.type(squish.waitForObject(names.nukeMainWindow_DAG_DAG_Window), "<Ctrl+S>")
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.configure_aws_profile()
    squish_helpers.set_conda_package_channel()
    squish_helpers.set_job_name("Write Node Frame Range Limits Job")
    squish_helpers.set_job_description(
        "Verify that the Write node frame range limits are respected"
    )
    squish_helpers.configure_storage_profile("<none selected>")
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Job-specific settings"
    )
    combo_box = squish.waitForObject(names.write_nodes_QComboBox)
    squish.mouseClick(combo_box)
    combo_box.setCurrentText("Write1")
    squish_helpers.submit_job()
    squish_helpers.close_nuke()
