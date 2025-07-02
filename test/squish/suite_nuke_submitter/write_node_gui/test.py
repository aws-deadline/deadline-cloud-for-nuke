# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import names
import squish_helpers
import squish

"""
GUI test for verifying write node selection functionality in AWS Deadline Cloud submitter.

This test executes two submission scenarios using the Deadline Cloud submitter GUI. First, it launches 
Nuke with a multi-write-node script and submits a job targeting a single write node ("Write1"), 
configuring necessary storage and AWS profiles. Then, it performs a second submission using the same 
script but selecting all write nodes for processing. The test validates that the submitter can 
correctly handle both individual and batch write node selections, ensuring proper job submission and 
processing for different write node configurations.
"""


def main():
    squish_helpers.launch_nuke()
    squish.setWindowState(
        squish.waitForObject(names.nukeMainWindow_Foundry_UI_DockMainWindow),
        squish.WindowState.Maximize,
    )
    squish_helpers.open_nuke_script(
        "nuke_submitter_v02_nuke_modified_test_samples", "nukeSubmitter_v02_nuke_modified.nk"
    )
    squish.type(squish.waitForObject(names.nukeMainWindow_DAG_DAG_Window), "<Ctrl+S>")
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.configure_storage_profile()

    # Select Single Write Node
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Job-specific settings"
    )
    squish.mouseClick(
        squish.waitForObject(names.write_nodes_QComboBox),
        16,
        11,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.mouseClick(
        squish.waitForObjectItem(names.write_nodes_QComboBox, "Write1"),
        13,
        10,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Shared job settings"
    )

    squish_helpers.set_job_name("Single Write Node Submission Test")
    squish_helpers.set_job_description("Selected single write node for submission")
    squish_helpers.configure_aws_profile()
    squish_helpers.submit_job()

    # Select Multiple Write Nodes
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.configure_storage_profile()
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Job-specific settings"
    )
    squish.mouseClick(
        squish.waitForObject(names.write_nodes_QComboBox),
        16,
        11,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.mouseClick(
        squish.waitForObjectItem(names.write_nodes_QComboBox, "All write nodes"),
        69,
        12,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Shared job settings"
    )

    squish_helpers.set_job_name("Multiple Write Node Submission Test")
    squish_helpers.set_job_description("All write nodes option selected for submission")
    squish_helpers.configure_aws_profile()
    squish_helpers.submit_job()

    squish_helpers.close_nuke()
