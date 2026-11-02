# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Exercise the real client/HTTP submission contract without requiring Nuke.

This verifies the mock can serve the GUI's client path, including rejection
and retry. It does not substitute for the licensed GUI cases.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from deadline_test_fixtures.deadline_mock import build_mock_environment

from _submission_mock import FAILURE_MESSAGE, JOB_ID
from test_submission_ui import _assert_submission
from test_submitter_ui import _write_case_config

_SUBMIT = """
from botocore.exceptions import ClientError
from deadline.client import api
import runpy
import sys

# Apply the same loopback routing helper that the real GUI opener uses.
runpy.run_path(sys.argv[5])["_patch_botocore_host_prefix"]()

def submit():
    return api.create_job_from_job_bundle(
        sys.argv[1],
        name="Mock submission test",
        priority=73,
        job_parameters=[{"name": "Frames", "value": "7-9"}],
    )

if sys.argv[2] == "True":
    try:
        submit()
    except ClientError as error:
        assert error.response["Error"]["Code"] == "ValidationException"
        assert sys.argv[3] in str(error)
    else:
        raise AssertionError("Expected the first CreateJob to fail")

job_id = submit()
assert job_id == sys.argv[4], job_id
"""


@pytest.mark.parametrize("mock_submission_server", [False, True], indirect=True)
def test_real_client_submission_transport(mock_submission_server, tmp_path: Path, request) -> None:
    scenario, backend = mock_submission_server
    config_path, _ = _write_case_config(tmp_path, scenario)
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    golden = Path(__file__).parent / "test_cases/basic_workflow/expected/job_bundle"
    repo_root = Path(__file__).resolve().parents[2]
    for source in golden.iterdir():
        (bundle / source.name).write_text(
            source.read_text(encoding="utf-8").replace("<REPO_ROOT>", str(repo_root)),
            encoding="utf-8",
        )

    # Strip inherited credential overrides and service-specific endpoints.
    base_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("AWS_ENDPOINT_URL")
        and key not in ("AWS_PROFILE", "AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE")
    }
    env = build_mock_environment(
        base_env,
        deadline_endpoint_url=backend.base_url,
        config_path=config_path,
        home_dir=tmp_path / "home",
    )
    env["AWS_ENDPOINT_URL"] = backend.base_url
    env["AWS_IGNORE_CONFIGURED_ENDPOINT_URLS"] = "false"
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    fail_first = request.node.callspec.params["mock_submission_server"]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _SUBMIT,
            str(bundle),
            str(fail_first),
            FAILURE_MESSAGE,
            JOB_ID,
            str(Path(__file__).parent / "_opener/menu.py"),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    state = backend.snapshot()
    assert state["call_counts"]["GetJob"] == 2
    _assert_submission(backend, attempts=2 if fail_first else 1)
