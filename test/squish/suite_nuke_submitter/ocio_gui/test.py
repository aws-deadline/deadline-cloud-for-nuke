# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import names
import squish
import squish_helpers

"""
GUI test for submitting Nuke jobs with OCIO color management configurations to AWS Deadline Cloud.

This test verifies that users can successfully submit jobs that utilize OCIO color management:
The test demonstrates the ability to submit multiple render jobs from a single Nuke script that 
uses OCIO (OpenColorIO) color management. It tests this by submitting separate jobs for different 
write nodes within the same ACES-configured Nuke script, ensuring that the color management settings 
and transformations are properly preserved and handled during job submission. This verification is 
crucial for maintaining color accuracy and consistency in professional workflows that rely on OCIO 
for color space transformations and management.
"""


def submit_ocio_job(write_node: str):
    """Helper function to submit a job with specified write node."""
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.set_job_name("OCIO Config Job Submission")
    squish_helpers.set_job_description(
        "This test includes a render that includes the use of OCIO color management."
    )

    # Configure job-specific settings
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Job-specific settings"
    )
    combo_box = squish.waitForObject(names.write_nodes_QComboBox)
    squish.mouseClick(combo_box)
    combo_box.setCurrentText(write_node)

    # Configure shared settings
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Shared job settings"
    )
    squish_helpers.configure_storage_profile("<none selected>")
    squish_helpers.configure_aws_profile()
    squish_helpers.submit_job()


def main():
    squish_helpers.launch_nuke()
    squish.setWindowState(
        squish.waitForObject(names.nukeMainWindow_Foundry_UI_DockMainWindow),
        squish.WindowState.Maximize,
    )

    squish_helpers.open_nuke_script(
        "nuke_submitter_v02_nuke_aces_stock_test_samples",
        "nukeSubmitter_OCIO_v02_aces_stock.nk",
    )
    squish.type(squish.waitForObject(names.nukeMainWindow_DAG_DAG_Window), "<Ctrl+S>")

    submit_ocio_job("Write1")
    submit_ocio_job("Write2")

    squish_helpers.close_nuke()
