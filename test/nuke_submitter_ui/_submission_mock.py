# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Small submission-only extension of the shared HTTP mock.

The queue uses shared storage (no jobAttachmentSettings), so the real client
does not hash/upload to S3. This covers job creation, not attachment transfer.
Serve in a separate process: native accessibility calls can hold pytest's GIL.
"""

from __future__ import annotations

import multiprocessing
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import botocore.session
import yaml
from botocore.exceptions import ClientError
from botocore.validate import validate_parameters
from deadline_test_fixtures.deadline_mock import (
    MockDeadlineBackend,
    MockDeadlineScenario,
    RemoteDeadlineBackend,
    route,
    start_server,
)

JOB_ID = "job-0000000000000000000000000000000c"
FAILURE_MESSAGE = "Mock queue rejected this submission. Please try again."
SUCCESS_MESSAGE = "Job creation completed successfully"


class SubmissionBackend(MockDeadlineBackend):
    def __init__(self, scenario: MockDeadlineScenario, fail_first: bool) -> None:
        super().__init__(scenario)
        self.fail_first = fail_first
        self.attempts: list[dict[str, Any]] = []
        self.jobs: dict[str, dict[str, Any]] = {}
        self.polls = 0
        self.input_shape = (
            botocore.session.get_session()
            .get_service_model("deadline")
            .operation_model("CreateJob")
            .input_shape
        )

    @route("POST", "/farms/{farmId}/queues/{queueId}/jobs", "CreateJob")
    def create_job(self, *, farmId: str, queueId: str, **kwargs: Any) -> dict[str, str]:
        self._queue_key(farmId, queueId, "CreateJob")
        request = {"farmId": farmId, "queueId": queueId, **kwargs}
        validate_parameters(request, self.input_shape)
        # Reject accidentally turning this focused case into an S3 transfer test.
        assert "attachments" not in request, "Submission mock only supports shared storage"
        with self._lock:
            self.attempts.append(request)
            if self.fail_first and len(self.attempts) == 1:
                raise ClientError(
                    {"Error": {"Code": "ValidationException", "Message": FAILURE_MESSAGE}},
                    "CreateJob",
                )
            assert not self.jobs, "Expected a single successfully created job per test"
            self.jobs[JOB_ID] = request
        return {"jobId": JOB_ID}

    @route("GET", "/farms/{farmId}/queues/{queueId}/jobs/{jobId}", "GetJob")
    def get_job(self, *, farmId: str, queueId: str, jobId: str) -> dict[str, Any]:
        self._queue_key(farmId, queueId, "GetJob")
        with self._lock:
            if jobId not in self.jobs:
                raise ClientError(
                    {"Error": {"Code": "ResourceNotFoundException", "Message": "Unknown job"}},
                    "GetJob",
                )
            self.polls += 1
            request = self.jobs[jobId]
            return {
                "jobId": jobId,
                "name": yaml.safe_load(request["template"])["name"],
                "priority": request["priority"],
                "createdAt": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "createdBy": "mock-test-user",
                "lifecycleStatus": "CREATE_IN_PROGRESS" if self.polls == 1 else "CREATE_COMPLETE",
                "lifecycleStatusMessage": "" if self.polls == 1 else SUCCESS_MESSAGE,
            }

    def snapshot(self) -> dict[str, Any]:
        state = super().snapshot()
        with self._lock:
            state["submission_attempts"] = list(self.attempts)
            state["created_job_ids"] = list(self.jobs)
        return state


def _serve(scenario_data: dict[str, Any], fail_first: bool, connection) -> None:
    backend = SubmissionBackend(MockDeadlineScenario.from_dict(scenario_data), fail_first)
    server, base_url, thread = start_server(backend)
    connection.send(base_url)
    connection.close()
    try:
        thread.join()
    finally:
        server.server_close()


@contextmanager
def submission_server(
    *,
    fail_first: bool = False,
) -> Iterator[tuple[MockDeadlineScenario, RemoteDeadlineBackend]]:
    default = MockDeadlineScenario()
    queue = dict(default.queue)
    queue.pop("jobAttachmentSettings")
    scenario = MockDeadlineScenario(
        queue=queue,
        response_delay_s=0.3,
    )
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_serve, args=(scenario.to_dict(), fail_first, sender))
    process.start()
    sender.close()
    try:
        if not receiver.poll(60):
            raise TimeoutError("Submission mock did not start within 60s")
        base_url = receiver.recv()
        backend = RemoteDeadlineBackend(
            base_url, {"farm_id": scenario.farm_id, "queue_id": scenario.queue_id}
        )
        backend.snapshot()  # readiness check
        yield scenario, backend
    finally:
        receiver.close()
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
        process.close()
