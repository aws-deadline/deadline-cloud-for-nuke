# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Version-specific golden selection must work with either GUI driver."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("driver", ["qt", "xa11y"])
@pytest.mark.parametrize("major", [16, 17])
def test_export_selects_goldens_from_shared_status(monkeypatch, tmp_path, driver, major):
    def stub(name, **attributes):
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)

    status = tmp_path / "opener_status.txt"
    session = Mock()

    # The Qt branch has no session object; both drivers write this result file.
    def launch(*_args, **_kwargs):
        status.write_text(f"OK\nnuke_version={major}.1v2\n", encoding="utf-8")
        return session

    stub("deadline_test_fixtures")
    stub("deadline_test_fixtures.deadline_mock", write_deadline_config=Mock())
    bundle_case = Mock(root=tmp_path / "cases" / "ocio")
    actual = tmp_path / "actual"
    actual.mkdir()
    bundle_case.prepare_actual_dir.return_value = actual
    stub(
        "deadline_test_fixtures.job_bundle",
        JobBundleCase=Mock(return_value=bundle_case),
        assert_valid_job_bundle=Mock(),
        find_complete_job_bundle=Mock(return_value=tmp_path / "exported"),
    )
    stub(
        "_launcher",
        ENV_STATUS_FILE="status",
        build_nuke_environment=Mock(return_value={"status": str(status)}),
        launch_nuke_with_submitter=launch,
    )
    stub("_qt_launcher", export_with_qt=launch)
    compare = Mock()
    stub(
        "_utils",
        assert_bundle_matches_golden=compare,
        copy_bundle_files_flat=Mock(),
        log=Mock(),
        write_goldens_from_actual=Mock(),
    )
    stub("pages", NukeSubmitterDialog=Mock())
    path = Path(__file__).resolve().parents[1] / "nuke_submitter_ui" / "test_submitter_ui.py"
    spec = importlib.util.spec_from_file_location("golden_selection_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_CASES_ROOT", tmp_path / "cases")
    monkeypatch.setattr(module, "_write_case_config", Mock(return_value=(tmp_path, tmp_path)))
    monkeypatch.setattr(module, "_assert_expected_mock_traffic", Mock())
    monkeypatch.setenv("NUKE_SUBMITTER_UI_DRIVER", driver)
    monkeypatch.delenv("NUKE_SUBMITTER_UI_UPDATE_GOLDENS", raising=False)
    monkeypatch.delenv("NUKE_SUBMITTER_UI_DIALOG_DUMP", raising=False)
    case = bundle_case.root
    (case / "input").mkdir(parents=True)
    (case / "input" / "scene.py").write_text("", encoding="utf-8")
    expected = case / "expected" / "job_bundle"
    expected.mkdir(parents=True)
    (expected / "template.yaml").write_text("shared template", encoding="utf-8")
    (expected / "parameter_values.yaml").write_text("legacy OCIO", encoding="utf-8")
    overrides = case / "expected" / "job_bundle_nuke17"
    overrides.mkdir()
    (overrides / "parameter_values.yaml").write_text("Nuke 17 OCIO", encoding="utf-8")

    module.test_submitter_export_bundle(
        tmp_path=tmp_path,
        nuke_executable=tmp_path / "Nuke",
        mock_deadline_server=Mock(),
        mock_backend=Mock(),
        case="ocio",
    )

    selected, compared_actual = compare.call_args.args
    assert compared_actual == actual
    assert (selected / "template.yaml").read_text() == "shared template"
    assert (selected / "parameter_values.yaml").read_text() == (
        "Nuke 17 OCIO" if major == 17 else "legacy OCIO"
    )
    if driver == "xa11y":
        session.close.assert_called_once()
