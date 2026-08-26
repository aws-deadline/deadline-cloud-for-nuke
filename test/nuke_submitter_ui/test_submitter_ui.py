# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Parametrized runner for the data-driven cases under ``test_cases/``.

Case layout, contract, and diagnostic env vars: see ``README.md``. Cases
are auto-discovered from ``test_cases/``; a malformed case (no
``input/scene.py``) fails loudly rather than being skipped. One
non-obvious runner behavior: ``NUKE_SUBMITTER_UI_UPDATE_GOLDENS=1``
regenerates a case's goldens and then STILL runs the comparison, proving
the normalization round-trips before you commit the new goldens.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from shutil import rmtree
from typing import Callable, Optional

import pytest
from deadline_test_fixtures.deadline_mock import write_deadline_config
from deadline_test_fixtures.job_bundle import (
    JobBundleCase,
    assert_valid_job_bundle,
    find_complete_job_bundle,
)

from _launcher import build_nuke_environment, launch_nuke_with_submitter
from _utils import (
    assert_bundle_matches_golden,
    copy_bundle_files_flat,
    log,
    write_goldens_from_actual,
)
from pages import NukeSubmitterDialog

# The default scenario's farm display name (deadline-cloud-test-fixtures).
_MOCK_FARM_NAME = "TestFarm"

DialogConfigurator = Callable[[NukeSubmitterDialog], None]

_CASES_ROOT = Path(__file__).resolve().parent / "test_cases"

# Auto-discovered: every directory under test_cases/ is a case (see README).
# No registration list to forget — a malformed case fails in the test.
_CASES = sorted(
    path.name
    for path in _CASES_ROOT.iterdir()
    if path.is_dir() and not path.name.startswith((".", "_"))
)


def _load_configurator(cases_root: Path, case: str) -> Optional[DialogConfigurator]:
    """Load a case's optional input/configure.py.

    A configure.py must define a top-level ``configure(dialog)``. A present
    but broken configurator fails loudly rather than being skipped.
    """
    config_path = cases_root / case / "input" / "configure.py"
    if not config_path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"_configure_{case}", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load configurator at {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    configure = getattr(module, "configure", None)
    if not callable(configure):
        raise AttributeError(f"{config_path} must define a top-level configure(dialog) function")
    return configure


def _write_case_config(tmp_path: Path, scenario) -> tuple[Path, Path]:
    """Write the isolated deadline config; return (config_path, export_dir)."""
    config_path = tmp_path / "deadline_config"
    job_history_dir = tmp_path / "job_history"
    export_dir = tmp_path / "exported_bundles"
    export_dir.mkdir()
    write_deadline_config(
        config_path,
        farm_id=scenario.farm_id,
        queue_id=scenario.queue_id,
        job_history_dir=job_history_dir,
        job_bundle_default_directory=export_dir,
    )
    return config_path, export_dir


def _assert_expected_mock_traffic(mock_backend) -> None:
    """The submitter ran against the mock, not real AWS: prove its calls
    arrived and nothing escaped to an unmocked route."""
    counts = dict(mock_backend.call_counts)
    log(f"mock backend call_counts: {counts}")
    assert (
        mock_backend.unmatched_requests == []
    ), f"submitter hit routes the mock doesn't implement: {mock_backend.unmatched_requests}"
    for operation in ("ListFarms", "ListQueueEnvironments"):
        assert (
            counts.get(operation, 0) >= 1
        ), f"expected the submitter to call {operation}; saw {counts}"
    assert any(
        counts.get(operation, 0) >= 1 for operation in ("GetQueue", "ListQueues")
    ), f"expected a queue lookup; saw {counts}"


@pytest.mark.parametrize("case", _CASES)
def test_submitter_export_bundle(
    nuke_executable: Path,
    mock_deadline_server,
    mock_backend,
    tmp_path: Path,
    case: str,
) -> None:
    """Drive the real submitter dialog for *case* and verify the exported
    bundle against the case's goldens, fully offline against the mock."""
    bundle_case = JobBundleCase(_CASES_ROOT / case)
    case_folder = bundle_case.root
    scene_script = case_folder / "input" / "scene.py"
    if not scene_script.is_file():
        pytest.fail(f"case {case!r} has no input/scene.py — malformed case folder")
    actual_dir = bundle_case.prepare_actual_dir()
    configure = _load_configurator(_CASES_ROOT, case)

    config_path, export_dir = _write_case_config(tmp_path, mock_deadline_server.scenario)
    env = build_nuke_environment(
        deadline_endpoint_url=mock_deadline_server.base_url,
        config_path=config_path,
        work_dir=tmp_path,
        scene_script=scene_script,
        scene_file=actual_dir / f"{case}.nk",
    )

    log(f"case {case}: launching Nuke")
    session = launch_nuke_with_submitter(nuke_executable, env, tmp_path)
    try:
        dialog = NukeSubmitterDialog.wait_for(session.app, ensure_frontmost=session.activate)
        dialog.wait_farm_resolved(_MOCK_FARM_NAME)
        dialog.wait_settled()

        if os.environ.get("NUKE_SUBMITTER_UI_DIALOG_DUMP") == "1":
            dialog.dump_settings_tabs()
            pytest.fail("NUKE_SUBMITTER_UI_DIALOG_DUMP=1: dumped settings tabs, skipping export")

        if configure is not None:
            log(f"case {case}: running configurator")
            configure(dialog)

        log(f"case {case}: saving bundle locally")
        dialog.export_bundle()
    finally:
        session.close()

    exported_bundle = find_complete_job_bundle(export_dir)
    assert exported_bundle is not None, f"no complete bundle found under {export_dir}"
    copy_bundle_files_flat(exported_bundle, actual_dir)

    _assert_expected_mock_traffic(mock_backend)

    assert_valid_job_bundle(actual_dir / "template.yaml")

    expected_bundle_dir = case_folder / "expected" / "job_bundle"
    if os.environ.get("NUKE_SUBMITTER_UI_UPDATE_GOLDENS") == "1":
        log(f"case {case}: UPDATE_GOLDENS — regenerating {expected_bundle_dir}")
        write_goldens_from_actual(actual_dir, expected_bundle_dir)

    assert_bundle_matches_golden(expected_bundle_dir, actual_dir)

    # Keep actual/ around only when something failed above (for inspection).
    rmtree(actual_dir, ignore_errors=True)
