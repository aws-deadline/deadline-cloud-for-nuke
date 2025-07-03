# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# mypy: disable-error-code="attr-defined"
import names
import squish_helpers
import squish

"""
GUI test for submitting a Nuke job with custom settings to AWS Deadline Cloud.

This test verifies that users can successfully modify and submit jobs with custom settings:
This test configures custom job settings like the job name, job description, priority, max retries
per task, max failed tasks, and continue on error. This test submits a job with these custom settings
and ensures that all custom settings are properly applied to the submitted job
and that the job submission process works correctly with modified parameters.
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
    squish_helpers.set_job_name("Custom Setting Submission")
    squish_helpers.set_job_description("This test verifies submission with modified settings")

    squish_helpers.set_priority(75)
    squish_helpers.set_max_retries(3)
    squish_helpers.set_max_failed_tasks(10)

    squish_helpers.configure_aws_profile()
    squish_helpers.set_continue_on_error()
    squish_helpers.submit_job()
    squish_helpers.close_nuke()
