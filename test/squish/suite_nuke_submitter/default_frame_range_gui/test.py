# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import names
import squish_helpers
import squish

"""
GUI test for submitting a Nuke job using the default frame range from AWS Deadline Cloud.

This test verifies that users can successfully submit jobs using the frame range specified in their Nuke script:
The test opens a Nuke script that has a predefined frame range set within it, submits the job without modifying 
the frame range settings, and ensures that the job submission process correctly uses these default frame range 
values from the Nuke script. This verifies that when users don't explicitly set frame ranges in the submitter, 
the system properly inherits and uses the frame range values already configured in their Nuke scripts.
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
    squish_helpers.set_job_name("Default Frame Range Job")
    squish_helpers.set_job_description(
        "This test verifies that the default frame range specified in the Nuke Script is used"
    )
    squish_helpers.configure_aws_profile()
    squish_helpers.submit_job()
    squish_helpers.close_nuke()
