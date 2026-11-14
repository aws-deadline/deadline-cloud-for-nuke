# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Fixtures for the xa11y-driven Nuke submitter UI tests.

Requirements, setup, case layout, and platform notes: see ``README.md`` in
this directory. Canonical invocation (the suite is not part of the default
unit-test run)::

    hatch run integ-xa11y:test

Tests run fully offline against the out-of-process mock Deadline backend
from ``deadline-cloud-test-fixtures``; no farm and no AWS credentials.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest
from deadline_test_fixtures.deadline_mock import (
    MockDeadlineScenario,
    MockDeadlineServerProcess,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _launcher import find_nuke_executable  # noqa: E402


def pytest_collection_modifyitems(config, items):
    """Refuse to run under pytest-xdist parallelism.

    These tests launch a licensed GUI Nuke and drive it with real synthetic
    input; parallel workers would type into each other's windows. The
    xdist_group marker only serializes under --dist loadgroup, which the
    repo's default addopts (-n auto) do not set, so fail fast instead.
    """
    if items and config.pluginmanager.hasplugin("xdist") and config.getoption("numprocesses", 0):
        raise pytest.UsageError(
            "test/nuke_submitter_ui cannot run under pytest-xdist; use the "
            "canonical command: hatch run integ-xa11y:test"
        )


@pytest.fixture(scope="session", autouse=True)
def _venv_bin_on_path() -> Iterator[None]:
    """``assert_valid_job_bundle`` shells out to ``openjd``; make sure the
    interpreter's script dir is on PATH even when pytest is invoked via an
    absolute path without activating the venv."""
    original = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{original}"
    try:
        yield
    finally:
        os.environ["PATH"] = original


@pytest.fixture(scope="session")
def nuke_executable() -> Path:
    try:
        return find_nuke_executable()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="session")
def mock_deadline_server() -> Iterator[MockDeadlineServerProcess]:
    """Out-of-process mock Deadline backend for the whole session.

    Responses carry an artificial per-request delay approximating the real
    service's observed 200-600 ms, so timing races that a zero-latency mock
    would hide still surface. Override via MOCK_DEADLINE_RESPONSE_DELAY_S.
    """
    delay = float(os.environ.get("MOCK_DEADLINE_RESPONSE_DELAY_S", "0.3"))
    server = MockDeadlineServerProcess(MockDeadlineScenario(response_delay_s=delay)).start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def mock_backend(mock_deadline_server):
    """Per-test view of the remote mock backend, state reset."""
    backend = mock_deadline_server.backend
    backend.reset()
    return backend


@pytest.fixture
def interactive_submitter(nuke_executable, mock_deadline_server, mock_backend, tmp_path):
    """Fresh dialog for interaction cases that assert actual bundle contents.

    Reuse the proven basic scene and launch/config helpers, but keep output
    in pytest's temporary directory: these cases do not compare goldens.
    """
    from _launcher import build_nuke_environment, launch_nuke_with_submitter
    from pages import NukeSubmitterDialog
    from test_submitter_ui import _assert_expected_mock_traffic, _write_case_config

    scene_script = Path(__file__).parent / "test_cases/basic_workflow/input/scene.py"
    scene_file = tmp_path / "interaction.nk"
    config_path, export_dir = _write_case_config(tmp_path, mock_deadline_server.scenario)
    env = build_nuke_environment(
        deadline_endpoint_url=mock_deadline_server.base_url,
        config_path=config_path,
        work_dir=tmp_path,
        scene_script=scene_script,
        scene_file=scene_file,
    )
    session = launch_nuke_with_submitter(nuke_executable, env, tmp_path)
    try:
        dialog = NukeSubmitterDialog.wait_for(session.app, ensure_frontmost=session.activate)
        dialog.wait_farm_resolved("TestFarm")
        dialog.wait_settled()
        if os.environ.get("NUKE_SUBMITTER_UI_DIALOG_DUMP") == "1":
            dialog.dump_settings_tabs()
            pytest.fail("NUKE_SUBMITTER_UI_DIALOG_DUMP=1: dumped settings tabs, skipping actions")
        yield dialog, export_dir, scene_file
    finally:
        session.close()
        _assert_expected_mock_traffic(mock_backend)


@pytest.fixture
def mock_submission_server(request):
    from _submission_mock import submission_server

    with submission_server(fail_first=getattr(request, "param", False)) as server:
        yield server


@pytest.fixture
def submission_submitter(nuke_executable, mock_submission_server, tmp_path):
    """Real Nuke + client submission to a shared-storage mock queue."""
    from _launcher import build_nuke_environment, launch_nuke_with_submitter
    from pages import NukeSubmitterDialog
    from test_submitter_ui import _assert_expected_mock_traffic, _write_case_config

    scenario, backend = mock_submission_server
    config_path, _ = _write_case_config(tmp_path, scenario)
    env = build_nuke_environment(
        deadline_endpoint_url=backend.base_url,
        config_path=config_path,
        work_dir=tmp_path,
        scene_script=Path(__file__).parent / "test_cases/basic_workflow/input/scene.py",
        scene_file=tmp_path / "submission.nk",
    )
    # Any unexpected AWS service requests must also hit loopback and fail.
    for key in list(env):
        if key.startswith("AWS_ENDPOINT_URL_"):
            del env[key]
    env["AWS_ENDPOINT_URL"] = backend.base_url
    env["AWS_IGNORE_CONFIGURED_ENDPOINT_URLS"] = "false"
    session = launch_nuke_with_submitter(nuke_executable, env, tmp_path)
    try:
        dialog = NukeSubmitterDialog.wait_for(session.app, ensure_frontmost=session.activate)
        dialog.wait_farm_resolved("TestFarm")
        dialog.wait_settled()
        yield dialog, backend
    finally:
        session.close()
        _assert_expected_mock_traffic(backend)
