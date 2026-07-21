# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Fixtures for the xa11y-driven Nuke submitter UI tests.

Requirements, setup, case layout, and platform notes: see ``README.md`` in
this directory. Canonical invocation (the suite is not part of the default
unit-test run)::

    python -m pytest test/nuke_submitter_ui -o addopts= -q

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
    """These tests launch a licensed GUI Nuke — never run them in parallel."""
    if config.pluginmanager.hasplugin("xdist") and config.getoption("numprocesses", 0):
        for item in items:
            item.add_marker(pytest.mark.xdist_group("nuke_gui"))


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
def test_cases_root() -> Path:
    return Path(__file__).resolve().parent / "test_cases"
