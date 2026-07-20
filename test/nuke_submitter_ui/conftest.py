# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Fixtures for the xa11y-driven Nuke submitter UI tests.

Run explicitly (not part of the default unit-test run)::

    python -m pytest test/nuke_submitter_ui -p no:cacheprovider --no-cov -s

Requirements:

* GUI Nuke installed (``NUKE_EXECUTABLE`` overrides discovery) with this
  repo installed into Nuke's Python (see ``DEVELOPMENT.md``) — the same
  setup used for manual submitter development.
* ``deadline-cloud-test-fixtures``, ``xa11y`` and ``openjd-cli`` installed
  in the test environment.
* macOS: the terminal running pytest needs Accessibility permission
  (System Settings > Privacy & Security > Accessibility).

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
    MockDeadlineServerProcess,
    write_deadline_config,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _launcher import (  # noqa: E402
    NukeSession,
    build_nuke_environment,
    find_nuke_executable,
    launch_nuke_with_submitter,
)
from pages import NukeSubmitterDialog  # noqa: E402


def pytest_collection_modifyitems(config, items):
    """These tests launch a licensed GUI Nuke — never run them in parallel."""
    if config.pluginmanager.hasplugin("xdist") and config.getoption("numprocesses", 0):
        for item in items:
            item.add_marker(pytest.mark.xdist_group("nuke_gui"))


@pytest.fixture(scope="session", autouse=True)
def _venv_bin_on_path() -> None:
    """``assert_valid_job_bundle`` shells out to ``openjd``; make sure the
    interpreter's script dir is on PATH even when pytest is invoked via an
    absolute path without activating the venv."""
    scripts = Path(sys.executable).parent
    os.environ["PATH"] = f"{scripts}{os.pathsep}{os.environ.get('PATH', '')}"


@pytest.fixture(scope="session")
def nuke_executable() -> Path:
    try:
        return find_nuke_executable()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))
        raise  # unreachable: skip() always raises; keeps returns explicit


@pytest.fixture(scope="session")
def mock_deadline_server() -> Iterator[MockDeadlineServerProcess]:
    server = MockDeadlineServerProcess().start()
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
def nuke_env(tmp_path: Path, mock_deadline_server, mock_backend) -> dict[str, str]:
    """Hermetic env for the Nuke subprocess: mock endpoint, isolated
    deadline config preselecting the scenario farm/queue, temp history."""
    scenario = mock_deadline_server.scenario
    config_path = tmp_path / "deadline_config"
    write_deadline_config(
        config_path,
        farm_id=scenario.farm_id,
        queue_id=scenario.queue_id,
        job_history_dir=tmp_path / "job_history",
    )
    return build_nuke_environment(
        deadline_endpoint_url=mock_deadline_server.base_url,
        config_path=config_path,
        work_dir=tmp_path,
    )


@pytest.fixture
def job_history_dir(tmp_path: Path) -> Path:
    return tmp_path / "job_history"


@pytest.fixture
def nuke_session(nuke_executable: Path, nuke_env: dict[str, str], tmp_path: Path):
    session: NukeSession = launch_nuke_with_submitter(nuke_executable, nuke_env, tmp_path)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def submitter_dialog(nuke_session: NukeSession) -> NukeSubmitterDialog:
    return NukeSubmitterDialog.wait_for(nuke_session.app, ensure_frontmost=nuke_session.activate)
