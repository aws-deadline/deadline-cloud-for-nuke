# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# mypy: disable-error-code="attr-defined"
import names
import squish_helpers
import squish

"""
GUI test for submitting a Nuke job with custom frame range settings to AWS Deadline Cloud.

This test verifies that users can successfully override and submit jobs with custom frame ranges:
This test enables the frame range override option and configures a specific frame range (1-10) 
instead of using the default range from the Nuke script. This test submits a job with the custom 
frame range and ensures that the override is properly applied to the submitted job.
"""


def main():
    squish_helpers.launch_nuke()
    squish.setWindowState(
        squish.waitForObject(names.nukeMainWindow_Foundry_UI_DockMainWindow),
        squish.WindowState.Maximize,
    )
    squish_helpers.open_nuke_script("intro_to_compositing_test_samples", "Shot002.v01.001.nk")
    squish.snooze(3)
    squish.type(squish.waitForObject(names.nukeMainWindow_DAG_DAG_Window), "<Ctrl+S>")
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.configure_aws_profile()
    squish_helpers.set_conda_package_channel()
    squish_helpers.set_job_name("Custom Frame Range Job")
    squish_helpers.set_job_description(
        "This test verifies that a custom frame range can be specified"
    )
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Job-specific settings"
    )

    combo_box = squish.waitForObject(names.write_nodes_QComboBox)
    squish.mouseClick(combo_box)
    combo_box.setCurrentText("Write1")

    if not squish.waitForObject(names.override_frame_range_QCheckBox).isChecked():
        squish.clickButton(squish.waitForObject(names.override_frame_range_QCheckBox))
        squish_helpers.test_log("Clicked the override frame range checkbox")

    override_frame_range_edit = squish.waitForObject(names.override_frame_range_QLineEdit)
    override_frame_range_edit.selectAll()
    squish.type(override_frame_range_edit, "1-10")
    squish_helpers.test_log("Overrided frame range to 1-10")
    squish_helpers.configure_storage_profile("<none selected>")
    squish_helpers.submit_job()
    squish_helpers.close_nuke()
