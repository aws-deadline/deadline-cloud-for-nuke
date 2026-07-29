# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Dialog configurator for the basic_workflow case.

Runs after the submitter dialog has settled and before Export bundle is
pressed. Receives the suite's NukeSubmitterDialog page object (see
test/nuke_submitter_ui/pages.py), which encodes the platform workarounds
for combos and spin boxes. Whatever this changes must be reflected in this
case's expected/job_bundle/ goldens — the comparison is exact.

Mirrors the Squish basic_workflow_gui case: job name + description, an
explicit write-node selection, and a non-default chunk size.
"""


def configure(dialog) -> None:
    dialog.set_job_name("Basic Workflow Submission Test")
    dialog.set_job_description("Basic Workflow Test Description")
    dialog.switch_to_job_specific_tab()
    assert dialog.selected_write_node() == "All write nodes"
    dialog.select_write_node("Write1")
    dialog.set_chunk_size(5)
