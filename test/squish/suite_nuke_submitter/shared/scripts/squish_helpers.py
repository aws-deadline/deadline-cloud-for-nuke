# -*- coding: utf-8 -*-
# mypy: disable-error-code="attr-defined"
import squish
import test
import names
import config


def launch_nuke():
    squish.startApplication("Nuke16.0v1")
    test.log("Launched Nuke with Deadline Submitter")


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


def close_nuke():
    squish.sendEvent(
        "QCloseEvent", squish.waitForObject(names.nukeMainWindow_Foundry_UI_DockMainWindow)
    )
    test.log("Closed the Nuke application")
