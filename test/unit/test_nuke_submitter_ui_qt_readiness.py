# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Keep Qt export from racing queue refresh or hiding a backend failure."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def readiness():
    path = Path(__file__).resolve().parents[1] / "nuke_submitter_ui/_opener/qt_readiness.py"
    spec = importlib.util.spec_from_file_location("qt_readiness", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ready_for_configuration


@pytest.mark.parametrize(
    "enabled,state,farm,expected",
    [
        (True, "Loading Queue Environments...", True, False),
        (True, "Reloading Queue Environments...", True, False),
        (True, "", False, False),
        (False, "", True, False),
        (True, "", True, True),
    ],
)
def test_export_waits_for_resolved_farm_and_settled_queue(
    readiness, enabled, state, farm, expected
):
    assert readiness(enabled, state, farm) is expected


def test_queue_failure_is_reported_even_when_submit_is_disabled(readiness):
    with pytest.raises(RuntimeError, match="Error loading queue environments"):
        readiness(False, "Error loading queue environments: backend failed", True)
