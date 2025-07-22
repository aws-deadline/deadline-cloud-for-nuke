# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# mypy: disable-error-code="attr-defined"
import squish
import test
import names
import config
import os
import sys
from pathlib import Path


def launch_nuke():
    if sys.platform in ["win32", "linux"]:
        squish.startApplication("Nuke16.0")
    if sys.platform == "darwin":
        squish.startApplication("Nuke16.0v1")
    test.log("Launched Nuke with Deadline Submitter")


def test_log(log_message: str):
    test.log(log_message)


def open_nuke_script(test_sample_name: str, script_name: str):
    squish.activateItem(squish.waitForObjectItem(names.o_QMenuBar, "File"))
    squish.activateItem(squish.waitForObjectItem(names.file_Foundry_UI_Menu, "Open Comp..."))

    file_path_edit = squish.waitForObject(names.script_to_open_FilePathEdit)
    file_path_edit.selectAll()
    deadline_nuke_path = os.environ.get("DEADLINE_NUKE_PATH")
    if not deadline_nuke_path:
        test.fatal("DEADLINE_NUKE_PATH environment variable not set")
        return

    script_path = os.path.join(
        deadline_nuke_path,
        "test",
        "squish",
        "nuke-assets",
        "nuke_test_samples",
        test_sample_name,
        "scripts",
        script_name,
    )
    test.log(f"Using script path: {script_path}")

    squish.setFocus(file_path_edit)
    squish.type(file_path_edit, script_path)
    squish.type(file_path_edit, "<Backspace>")
    squish.type(file_path_edit, "k")

    file_table = squish.waitForObject(names.script_to_open_QTreeView)
    index = file_table.model().index(0, 0)
    file_table.setCurrentIndex(index)

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


def set_conda_package_channel():
    squish.snooze(1)
    conda_package_edit = squish.waitForObject(
        names.queue_Environment_Conda_Conda_Packages_QLineEdit
    )

    conda_package_text = str(
        squish.waitForObject(names.queue_Environment_Conda_Conda_Packages_QLineEdit).text
    )

    if conda_package_text != "nuke=16.* nuke-openjd=0.18.*":
        conda_package_edit.selectAll()
        squish.type(conda_package_edit, "<Delete>")
        squish.type(conda_package_edit, "nuke=16.* nuke-openjd=0.18.*")
        squish.snooze(2)

    conda_channel_edit = squish.waitForObject(
        names.queue_Environment_Conda_Conda_Channels_QLineEdit
    )

    conda_channel_text = str(
        squish.waitForObject(names.queue_Environment_Conda_Conda_Channels_QLineEdit).text
    )
    if conda_channel_text != "deadline-cloud":
        conda_channel_edit.selectAll()
        squish.type(conda_channel_edit, "deadline-cloud")


def configure_aws_profile():
    squish.clickButton(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_Settings_QPushButton)
    )
    squish.snooze(3)

    # Set the AWS profile to profile specified in the AWS_PROFILE environment variable
    aws_profile_combo_box = squish.waitForObject(names.global_settings_AWS_profile_QComboBox)
    squish.mouseClick(aws_profile_combo_box)
    aws_profile_combo_box.setCurrentText(config.profile_name)

    # Set the farm to Nuke Submitter Squish Farm
    squish.clickButton(squish.waitForObject(names.profile_settings_QPushButton))
    farm_combo_box = squish.waitForObject(names.profile_settings_QComboBox)
    squish.mouseClick(farm_combo_box)
    farm_combo_box.setCurrentText("Nuke Submitter Squish Farm")

    # Set the farm to Nuke Submitter Squish Automation Queue
    squish.clickButton(squish.waitForObject(names.farm_settings_QPushButton_2))
    queue_combo_box = squish.waitForObject(names.farm_settings_QComboBox)
    squish.mouseClick(queue_combo_box)
    queue_combo_box.setCurrentText("Nuke Submitter Squish Automation Queue")

    squish.clickButton(
        squish.waitForObject(names.aWS_Deadline_Cloud_workstation_configuration_OK_QPushButton)
    )


def configure_storage_profile(profile_name: str):
    squish.clickButton(
        squish.waitForObject(names.submit_to_AWS_Deadline_Cloud_Settings_QPushButton)
    )
    squish.snooze(3)
    squish.clickButton(squish.waitForObject(names.farm_settings_QPushButton))
    combo_box = squish.waitForObject(names.farm_settings_QComboBox_2)
    squish.mouseClick(combo_box)
    combo_box.setCurrentText(profile_name)
    squish.clickButton(
        squish.waitForObject(names.aWS_Deadline_Cloud_workstation_configuration_OK_QPushButton)
    )
    test.log(f"Configured storage profile to {profile_name}")


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
