# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Check version-specific export comparison through the Linux Qt runner."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("major", [16, 17])
def test_qt_export_uses_opener_version_without_accessibility_session(monkeypatch, tmp_path, major):
    def stub(name, **attributes):
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    stub("deadline_test_fixtures")
    stub("deadline_test_fixtures.deadline_mock", write_deadline_config=Mock())
    bundle_case = Mock()
    stub(
        "deadline_test_fixtures.job_bundle",
        JobBundleCase=bundle_case,
        assert_valid_job_bundle=Mock(),
        find_complete_job_bundle=Mock(return_value=tmp_path / "exported"),
    )
    launch = Mock()
    stub(
        "_launcher", build_nuke_environment=Mock(return_value={}), launch_nuke_with_submitter=launch
    )

    def export(*_):
        (tmp_path / "opener_status.txt").write_text(f"OK\nnuke_version={major}.1v2\n")

    stub("_qt_launcher", export_with_qt=export)
    comparison = Mock()
    stub(
        "_utils",
        assert_bundle_matches_golden=comparison,
        copy_bundle_files_flat=Mock(),
        log=Mock(),
        write_goldens_from_actual=Mock(),
    )
    stub("pages", NukeSubmitterDialog=Mock())
    path = Path(__file__).resolve().parents[2] / "nuke_submitter_ui" / "test_submitter_ui.py"
    spec = importlib.util.spec_from_file_location("qt_version_runner_test", path)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    case = runner._CASES_ROOT / "ocio_stock_write1"
    actual = tmp_path / "actual"
    actual.mkdir()
    bundle_case.return_value = SimpleNamespace(root=case, prepare_actual_dir=lambda: actual)
    monkeypatch.setattr(runner, "_write_case_config", Mock(return_value=(tmp_path, tmp_path)))
    monkeypatch.setattr(runner, "_assert_expected_mock_traffic", Mock())
    monkeypatch.setenv("NUKE_SUBMITTER_UI_DRIVER", "qt")
    monkeypatch.delenv("NUKE_SUBMITTER_UI_UPDATE_GOLDENS", raising=False)

    runner.test_submitter_export_bundle(
        Path("Nuke"), SimpleNamespace(scenario=Mock(), base_url="mock"), Mock(), tmp_path, case.name
    )

    launch.assert_not_called()
    expected = tmp_path / "expected_bundle" if major == 17 else case / "expected" / "job_bundle"
    comparison.assert_called_once_with(expected, actual)
    if major == 17:
        assert (expected / "parameter_values.yaml").read_bytes() == (
            case / "expected" / "job_bundle_nuke17" / "parameter_values.yaml"
        ).read_bytes()
        assert (expected / "template.yaml").read_bytes() == (
            case / "expected" / "job_bundle" / "template.yaml"
        ).read_bytes()
