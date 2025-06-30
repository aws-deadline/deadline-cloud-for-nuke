import names
import squish_helpers
import squish

"""
GUI test for validating Conda package validation in AWS Deadline Cloud submitter.

This test verifies the submitter's error handling for invalid Conda configurations by 
attempting to use non-existent packages and channels.
"""


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
    conda_package_edit = squish.waitForObject(
        names.queue_Environment_Conda_Conda_Packages_QLineEdit
    )
    conda_package_edit.selectAll()
    squish.type(conda_package_edit, "invalid-package=1.0")
    conda_channel_edit = squish.waitForObject(
        names.queue_Environment_Conda_Conda_Channels_QLineEdit
    )
    conda_channel_edit.selectAll()
    squish.type(conda_channel_edit, "invalid-channel")
    squish_helpers.check_missing_conda_packages()
    squish_helpers.close_nuke()
