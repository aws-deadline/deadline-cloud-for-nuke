# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Basic workflow: the xa11y port of the Squish ``basic_workflow_gui`` case.

Where the Squish case submitted to a real farm, this test exports a job
bundle against the hermetic mock backend (which is read-only by design)
and verifies the produced bundle — same GUI interactions, deterministic
and offline. A true submit E2E against a real farm stays a separate,
opt-in concern.
"""

from __future__ import annotations

import yaml
from deadline_test_fixtures.job_bundle import (
    assert_valid_job_bundle,
    find_complete_job_bundle,
)

JOB_NAME = "Basic Workflow Submission Test"
JOB_DESCRIPTION = "Basic Workflow Test Description"
CHUNK_SIZE = 5


def _parameter_values(bundle_dir) -> dict[str, object]:
    data = yaml.safe_load((bundle_dir / "parameter_values.yaml").read_text())
    return {p["name"]: p["value"] for p in data["parameterValues"]}


def test_basic_workflow_export_bundle(submitter_dialog, mock_backend, job_history_dir):
    dialog = submitter_dialog

    # The dialog resolved farm/queue from the mock backend.
    dialog.wait_farm_resolved("TestFarm")
    assert (
        mock_backend.call_counts.get("ListFarms", 0) >= 1
    ), f"Dialog never listed farms: {mock_backend.call_counts}"

    # Shared job settings — same values as the Squish case.
    dialog.set_job_name(JOB_NAME)
    dialog.set_job_description(JOB_DESCRIPTION)

    # Nuke-specific settings.
    dialog.switch_to_job_specific_tab()
    assert dialog.selected_write_node() == "All write nodes"
    dialog.select_write_node("Write1")
    dialog.set_chunk_size(CHUNK_SIZE)

    dialog.export_bundle()

    bundle_dir = find_complete_job_bundle(job_history_dir)
    assert bundle_dir is not None, f"No complete job bundle under {job_history_dir}"

    # Structurally valid OpenJD bundle (runs `openjd check`).
    assert_valid_job_bundle(bundle_dir / "template.yaml")

    template = yaml.safe_load((bundle_dir / "template.yaml").read_text())
    assert template["name"] == JOB_NAME
    assert template["description"] == JOB_DESCRIPTION

    parameters = _parameter_values(bundle_dir)
    assert parameters["WriteNode"] == "Write1"
    assert parameters["ChunkSize"] == CHUNK_SIZE
    assert parameters["Frames"] == "1-100"  # scene default frame range
    assert str(parameters["NukeScriptFile"]).endswith("basic_workflow.nk")

    # The GUI stayed inside the mock sandbox: nothing hit an unknown route.
    assert (
        mock_backend.unmatched_requests == []
    ), f"Unexpected requests escaped the mock: {mock_backend.unmatched_requests}"
