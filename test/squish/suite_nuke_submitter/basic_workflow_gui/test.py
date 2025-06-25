# -*- coding: utf-8 -*-
# mypy: disable-error-code="attr-defined"
import names
import squish_helpers
import os
import test
import squish


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

    # Open the nuke script file that is being tested
    squish.activateItem(squish.waitForObjectItem(names.o_QMenuBar, "File"))
    squish.activateItem(squish.waitForObjectItem(names.file_Foundry_UI_Menu, "Open Comp..."))

    file_path_edit = squish.waitForObject(names.script_to_open_FilePathEdit)
    file_path_edit.selectAll()
    nuke_asset_path = os.environ.get("NUKE_ASSET_ROOT")
    if not nuke_asset_path:
        test.fatal("NUKE_ASSET_ROOT environment variable not set")
        return

    NUKE_TEST_SCRIPT_PATH = "nuke_test_samples/nuke_submitter_v02_nuke_default_test_samples/scripts/nukeSubmitter_v02_nuke_default_one_write_node.nk"
    script_path = os.path.join(nuke_asset_path, NUKE_TEST_SCRIPT_PATH)

    squish.setFocus(file_path_edit)
    squish.type(file_path_edit, script_path)

    # Opens the nuke script file
    squish.clickButton(squish.waitForObject(names.script_to_open_Open_QPushButton))

    squish.type(squish.waitForObject(names.nukeMainWindow_DAG_DAG_Window), "<Ctrl+S>")
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.configure_storage_profile()
    squish_helpers.set_job_name("Basic Workflow Submission Test")
    squish_helpers.set_job_description("Basic Workflow Test Description")
    squish_helpers.configure_aws_profile()
    squish_helpers.submit_job()
    squish_helpers.close_nuke()
