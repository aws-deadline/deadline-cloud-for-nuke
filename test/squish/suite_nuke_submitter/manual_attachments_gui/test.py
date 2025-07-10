# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# mypy: disable-error-code="attr-defined"
import names
import squish_helpers
import squish
import os

"""
GUI test for submitting a Nuke job with manually added file attachments to AWS Deadline Cloud.

This test verifies that users can successfully add and submit jobs with manual file attachments:
The test demonstrates the ability to manually attach additional input files and output directories 
that may not be automatically detected from the Nuke script. It adds specific test files 
(EXR, NK, and PNG) as input attachments and configures a custom output directory. This ensures 
that the manual attachment functionality works correctly for both input files and output locations.
"""


def main():
    squish_helpers.launch_nuke()
    squish.setWindowState(
        squish.waitForObject(names.nukeMainWindow_Foundry_UI_DockMainWindow),
        squish.WindowState.Maximize,
    )
    squish_helpers.open_nuke_script(
        "nuke_submitter_v02_nuke_aces_custom_samples", "nukeSubmitter_OCIO_v02_aces_custom.nk"
    )
    squish.snooze(3)
    squish.type(squish.waitForObject(names.nukeMainWindow_DAG_DAG_Window), "<Ctrl+S>")
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.set_job_name("Manual Job Attachments Test")
    squish_helpers.set_job_description(
        "Verify that additional files can be manually added as attachments"
    )
    squish_helpers.configure_storage_profile("<none selected>")
    squish_helpers.configure_aws_profile()
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Job attachments"
    )

    nuke_asset_path = os.environ.get("NUKE_ASSET_ROOT")
    if not nuke_asset_path:
        squish_helpers.test_log("NUKE_ASSET_ROOT environment variable not set.")
        return

    aces_custom_sample_path = "nuke_test_samples/nuke_submitter_v02_nuke_aces_custom_samples"

    manual_attachments = ["manual_asset.exr", "manual_script.nk", "nukeTest_manual_frame.png"]
    for attachment in manual_attachments:
        manual_attachment_path = os.path.join(
            nuke_asset_path, aces_custom_sample_path, "manual", attachment
        )
        squish_helpers.add_input_files(manual_attachment_path)

    squish_helpers.add_output_directory(
        os.path.join(nuke_asset_path, aces_custom_sample_path, "manual")
    )

    squish_helpers.submit_job()
    squish_helpers.close_nuke()
