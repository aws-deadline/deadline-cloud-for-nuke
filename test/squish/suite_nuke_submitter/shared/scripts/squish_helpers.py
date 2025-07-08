# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# mypy: disable-error-code="attr-defined"
import squish
import test
import names
import config
import os
from pathlib import Path


def launch_nuke():
    squish.startApplication("Nuke16.0v1")
    test.log("Launched Nuke with Deadline Submitter")


def open_nuke_script(test_sample_name: str, script_name: str):
    squish.activateItem(squish.waitForObjectItem(names.o_QMenuBar, "File"))
    squish.activateItem(squish.waitForObjectItem(names.file_Foundry_UI_Menu, "Open Comp..."))

    file_path_edit = squish.waitForObject(names.script_to_open_FilePathEdit)
    file_path_edit.selectAll()
    nuke_asset_path = os.environ.get("NUKE_ASSET_ROOT")
    if not nuke_asset_path:
        test.fatal("NUKE_ASSET_ROOT environment variable not set")
        return

    script_path = os.path.join(
        nuke_asset_path, "nuke_test_samples", test_sample_name, "scripts", script_name
    )
    test.log(f"Using script path: {script_path}")

    squish.setFocus(file_path_edit)
    squish.type(file_path_edit, script_path)
    squish.type(file_path_edit, "<Backspace>")
    squish.type(file_path_edit, "k")

    # Opens the nuke script file
    squish.clickButton(squish.waitForObject(names.script_to_open_Open_QPushButton))


def submit_job():
    test.log("Starting job submission")

    squish.clickButton(squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_Submit_QPushButton))
    test.log("Clicked submit button")

    squish.setWindowState(squish.waitForObject(names.o_QMessageBox), squish.WindowState.Maximize)
    squish.clickButton(squish.waitForObject(names.oK_QPushButton))

    test.log("Waiting for submission completion")
    success, job_id = check_submission_success()

    if success:
        test.log(f"CHECKED SUBMISSION SUCCESS: TRUE - Job ID: {job_id}")
    else:
        test.log("CHECKED SUBMISSION SUCCESS: FALSE, Submission failed.")
    squish.clickButton(
        squish.waitForObject(names.aWS_Deadline_Cloud_submission_OK_QPushButton, 20000)
    )

    test.log("Completed submission")
    return job_id


def open_nuke_submitter_gui():
    squish.activateItem(squish.waitForObjectItem(names.o_QMenuBar, "AWS Deadline"))
    squish.activateItem(
        squish.waitForObjectItem(names.aWS_Deadline_Foundry_UI_Menu, "Submit to Deadline Cloud")
    )
    test.log("Opened the Nuke Submitter Console")


def add_input_files(input_file_path: Path):
    squish.clickButton(squish.waitForObject(names.attach_input_files_Add_QPushButton))
    input_file_edit = squish.waitForObject(names.fileNameEdit_QLineEdit)
    input_file_edit.selectAll()
    squish.setFocus(input_file_edit)
    squish.type(input_file_edit, input_file_path)
    squish.type(input_file_edit, "<Backspace>")
    last_char = str(input_file_path)[-1]
    squish.type(input_file_edit, last_char)
    squish.clickButton(squish.waitForObject(names.open_QPushButton))


def add_output_directory(output_dir: Path):
    squish.clickButton(squish.waitForObject(names.specify_output_directories_Add_QPushButton))
    output_dir_edit = squish.waitForObject(names.fileNameEdit_QLineEdit)
    output_dir_edit.selectAll()
    squish.setFocus(output_dir_edit)
    squish.type(output_dir_edit, output_dir)
    squish.clickButton(squish.waitForObject(names.choose_QPushButton))


def set_job_name(name: str):
    name_edit = squish.waitForObject(names.name_QLineEdit)
    name_edit.selectAll()
    squish.type(name_edit, name)
    test.log(f"Job name set to {name}")


def set_job_description(description: str):
    description_edit = squish.waitForObject(names.job_Properties_Description_QLineEdit)
    description_edit.selectAll()
    squish.type(description_edit, description)
    test.log(f"Job description set to {description}")


def set_max_retries(retries: int):
    max_retries_edit = squish.waitForObject(names.job_Properties_qt_spinbox_lineedit_QLineEdit_3)
    max_retries_edit.selectAll()
    squish.type(max_retries_edit, str(retries))
    test.log(f"Replaced max retries with {retries}")


def set_max_failed_tasks(failed_tasks: int):
    max_failed_tasks_edit = squish.waitForObject(
        names.job_Properties_qt_spinbox_lineedit_QLineEdit_2
    )
    max_failed_tasks_edit.selectAll()
    squish.type(max_failed_tasks_edit, str(failed_tasks))
    test.log(f"Replaced max failed tasks with {failed_tasks}")


def set_priority(priority: int):
    priority_edit = squish.waitForObject(names.job_Properties_qt_spinbox_lineedit_QLineEdit)
    priority_edit.selectAll()
    squish.type(priority_edit, str(priority))
    test.log(f"Replaced priority with {priority}")


def set_continue_on_error():
    squish.clickTab(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_QTabWidget), "Job-specific settings"
    )
    if squish.waitForObjectExists(names.continue_on_error_QCheckBox).checked:
        test.log("Continue on error is already enabled")
    else:
        squish.clickButton(squish.waitForObject(names.continue_on_error_QCheckBox))
        test.log("Enabled continue on error")


def configure_aws_profile():
    squish.clickButton(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_Settings_QPushButton)
    )
    squish.sendEvent(
        "QMoveEvent",
        squish.waitForObject(
            names.aWS_Deadline_Cloud_workstation_configuration_DeadlineConfigDialog
        ),
        541,
        213,
        810,
        851,
    )

    # Set the AWS profile to profile specified in the AWS_PROFILE environment variable
    squish.mouseClick(
        squish.waitForObject(names.global_settings_AWS_profile_QComboBox),
        118,
        19,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.mouseClick(
        squish.waitForObjectItem(names.global_settings_AWS_profile_QComboBox, config.profile_name),
        117,
        18,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )

    # Set the farm to Nuke Submitter Squish Farm
    squish.mouseClick(
        squish.waitForObject(names.profile_settings_QComboBox),
        54,
        12,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.mouseClick(
        squish.waitForObjectItem(names.profile_settings_QComboBox, "Nuke Submitter Squish Farm"),
        55,
        10,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )

    # Set the farm to Nuke Submitter Squish Automation Queue
    squish.mouseClick(
        squish.waitForObject(names.farm_settings_QComboBox),
        55,
        7,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.mouseClick(
        squish.waitForObjectItem(
            names.farm_settings_QComboBox, "Nuke Submitter Squish Automation Queue"
        ),
        57,
        14,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )

    squish.clickButton(
        squish.waitForObject(names.aWS_Deadline_Cloud_workstation_configuration_OK_QPushButton)
    )


def configure_storage_profile():
    squish.clickButton(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_Settings_QPushButton)
    )
    squish.mouseClick(
        squish.waitForObject(names.farm_settings_QComboBox_2),
        78,
        6,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.mouseClick(
        squish.waitForObjectItem(names.farm_settings_QComboBox_2, "macOS Storage Profile"),
        82,
        8,
        squish.Qt.NoModifier,
        squish.Qt.LeftButton,
    )
    squish.clickButton(
        squish.waitForObject(names.aWS_Deadline_Cloud_workstation_configuration_OK_QPushButton)
    )


def check_submission_success():
    # Wait for the submission dialog to appear
    dialog = squish.waitForObject(names.aWS_Deadline_Cloud_submission_Upload_progress_QTextEdit)

    # Get the text content
    content = dialog.toPlainText()
    content = str(content)

    if "Job creation completed successfully" in content:
        # Split content into lines and find the job ID
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "Job creation completed successfully" in line and i + 1 < len(lines):
                job_id = lines[i + 1].strip()
                test.log(f"Found job ID: {job_id}")
                return True, job_id
    else:
        return False, None


def check_missing_conda_packages():
    conda_package_text = str(
        squish.waitForObject(names.queue_Environment_Conda_Conda_Packages_QLineEdit).text
    )
    if conda_package_text != "nuke=16.* nuke-openjd=0.18.*":
        test.fail("Conda packages are not configured correctly")
    conda_channel_text = str(
        squish.waitForObject(names.queue_Environment_Conda_Conda_Channels_QLineEdit).text
    )
    if conda_channel_text != "deadline-cloud":
        test.fail("Conda channels are not configured correctly")


def close_nuke():
    squish.sendEvent(
        "QCloseEvent", squish.waitForObject(names.nukeMainWindow_Foundry_UI_DockMainWindow)
    )
    test.log("Closed the Nuke application")
