# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Dialog configurator for the custom_settings case.

Port of the Squish custom_settings_gui case: override the job properties
(priority, max failed tasks, max retries per task) and enable continue-on
-error, then let the golden bundle prove each value reached the submission.

The values are deliberately not multiples of the spin boxes' AX step: the
platform's increment/decrement jumps by 10% of a widget's range, so a
stepping implementation could not produce 75 or 3 at all (see the spin-box
note in pages.py). Typed entry is what makes these values reachable.
"""

PRIORITY = 75
MAX_RETRIES_PER_TASK = 3
MAX_FAILED_TASKS = 10


def configure(dialog) -> None:
    dialog.set_job_name("Custom Setting Submission")
    dialog.set_job_description("This test verifies submission with modified settings")
    dialog.set_priority(PRIORITY)
    dialog.set_max_failed_tasks(MAX_FAILED_TASKS)
    dialog.set_max_retries(MAX_RETRIES_PER_TASK)
    dialog.switch_to_job_specific_tab()
    dialog.select_write_node("Write1")
    dialog.set_continue_on_error(True)
