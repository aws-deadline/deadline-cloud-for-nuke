# -*- coding: utf-8 -*-
# mypy: disable-error-code="attr-defined"
import names
import squish_helpers
import os
import test
import squish


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

    nuke_asset_path = os.environ.get("NUKE_ASSET_ROOT")
    if not nuke_asset_path:
        test.fatal("NUKE_ASSET_ROOT environment variable not set")
        return

    script_path = os.path.join(
        nuke_asset_path,
        "nuke_test_samples/nuke_submitter_v02_nuke_default_test_samples/scripts/nukeSubmitter_v02_nuke_default_one_write_node.nk",
    )
    test.log(f"Using script path: {script_path}")

    squish.setFocus(file_path_edit)
    squish.type(file_path_edit, script_path)

    # Opens the nuke script file
    squish.clickButton(squish.waitForObject(names.script_to_open_Open_QPushButton))

    squish.type(squish.waitForObject(names.nukeMainWindow_DAG_DAG_Window), "<Ctrl+S>")
    squish_helpers.open_nuke_submitter_gui()
    squish_helpers.configure_aws_profile()
    squish_helpers.submit_job()
    squish_helpers.close_nuke()
