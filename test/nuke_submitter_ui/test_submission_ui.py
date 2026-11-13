# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Real Submit-button coverage against a loopback-only shared-storage queue."""

import pytest
import yaml

from _submission_mock import FAILURE_MESSAGE, JOB_ID


def _assert_submission(backend, *, attempts: int) -> None:
    state = backend.snapshot()
    assert state["unmatched_requests"] == []
    assert state["call_counts"]["CreateJob"] == attempts
    assert state["call_counts"]["GetJob"] >= 2  # wait through CREATE_IN_PROGRESS
    assert state["created_job_ids"] == [JOB_ID]
    requests = state["submission_attempts"]
    assert len(requests) == attempts
    for request in requests:
        assert request["farmId"] == backend.farm_id
        assert request["queueId"] == backend.queue_id
        assert request["priority"] == 73
        assert request["templateType"] == "YAML"
        assert yaml.safe_load(request["template"])["name"] == "Mock submission test"
        assert request["parameters"]["Frames"] == {"string": "7-9"}
        assert "attachments" not in request


def _configure(dialog) -> None:
    dialog.set_job_name("Mock submission test")
    dialog.set_priority(73)
    dialog.switch_to_job_specific_tab()
    dialog.set_frame_range("7-9")


def test_submission_success(submission_submitter) -> None:
    dialog, backend = submission_submitter
    _configure(dialog)
    dialog.submit()
    dialog.finish_submission(JOB_ID)
    _assert_submission(backend, attempts=1)


@pytest.mark.parametrize("mock_submission_server", [True], indirect=True)
def test_submission_api_failure_and_retry(submission_submitter) -> None:
    dialog, backend = submission_submitter
    _configure(dialog)
    dialog.submit()
    dialog.dismiss_submission_error(FAILURE_MESSAGE)
    failed = backend.snapshot()
    assert failed["call_counts"]["CreateJob"] == 1
    assert failed["created_job_ids"] == []
    assert failed["call_counts"].get("GetJob", 0) == 0

    dialog.submit()
    dialog.finish_submission(JOB_ID)
    _assert_submission(backend, attempts=2)
