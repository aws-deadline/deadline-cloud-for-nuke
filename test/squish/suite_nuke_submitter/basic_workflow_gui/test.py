# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# mypy: disable-error-code="attr-defined"
import names
import squish_helpers
import squish
import sys


# This file is a Squish test script for testing the basic workflow of submitting a Nuke job to Deadline Cloud.
# It automates the process of launching Nuke, opening a script file, configuring AWS profile settings,
# submitting a job to Deadline Cloud, and then closing Nuke.
#
# This script is executed by the Squish test runner when the "basic_workflow_gui" test case is selected.
# It is triggered using the run_squish_command function in run_squish_test.py in the test_basic_workflow test.
#
# The main() function is the entry point that Squish automatically calls when executing this test script.


def main():
    squish_helpers.launch_nuke()
    squish.setWindowState(
        squish.waitForObject(names.nukeMainWindow_Foundry_UI_DockMainWindow),
        squish.WindowState.Maximize,
    )
    squish_helpers.open_nuke_script(
        "nuke_submitter_v02_nuke_default_test_samples",
        "nukeSubmitter_v02_nuke_default_one_write_node.nk",
    )
    squish.type(squish.waitForObject(names.nukeMainWindow_DAG_DAG_Window), "<Ctrl+S>")
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.configure_aws_profile()
    squish.snooze(5)
    squish_helpers.set_conda_package_channel()
    if sys.platform == "darwin":
        squish_helpers.configure_storage_profile("macOS Storage Profile")
    if sys.platform == "win32":
        squish_helpers.configure_storage_profile("Windows Storage Profile")
    squish_helpers.set_job_name("Basic Workflow Submission Test")
    squish_helpers.set_job_description("Basic Workflow Test Description")
    squish_helpers.submit_job()
    squish_helpers.close_nuke()
