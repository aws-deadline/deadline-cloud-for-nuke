# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Explicitly invoked experiment: pytest test/nuke_submitter_ui/qt_probe.py.

The filename intentionally excludes this case from the normal xa11y suite.
"""

import json
from pathlib import Path
import subprocess
import time

import yaml
from deadline_test_fixtures.job_bundle import assert_valid_job_bundle, find_complete_job_bundle

from _launcher import build_nuke_environment
from _process import capture_process_group, stop_process_tree
from test_submitter_ui import _assert_expected_mock_traffic, _write_case_config


def test_qt_frame_range_export(nuke_executable, mock_deadline_server, mock_backend, tmp_path):
    config, exports = _write_case_config(tmp_path, mock_deadline_server.scenario)
    scene = tmp_path / "scene" / "custom_frame_range.nk"
    scene.parent.mkdir()
    result = tmp_path / "qt-probe-result.json"
    environment = build_nuke_environment(
        deadline_endpoint_url=mock_deadline_server.base_url,
        config_path=config,
        work_dir=tmp_path,
        scene_script=Path(__file__).parent / "test_cases/custom_frame_range/input/scene.py",
        scene_file=scene,
    )
    environment["NUKE_SUBMITTER_QT_RESULT"] = str(result)
    with (
        (tmp_path / "nuke_stdout.log").open("w") as stdout,
        (tmp_path / "nuke_stderr.log").open("w") as stderr,
    ):
        process = subprocess.Popen(
            [str(nuke_executable)],
            env=environment,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
    group = capture_process_group(process)
    try:
        deadline = time.monotonic() + 240
        while not result.exists() and time.monotonic() < deadline:
            status = tmp_path / "opener_status.txt"
            if status.exists():
                assert status.read_text().startswith("OK"), status.read_text()
            assert process.poll() is None, "Nuke exited; inspect nuke_stdout/stderr.log"
            time.sleep(0.25)
        assert result.exists(), "Qt probe produced no result; inspect Nuke logs"
        report = json.loads(result.read_text())
        assert report["ok"], report
        bundle = find_complete_job_bundle(exports)
        assert bundle is not None, "The UI did not export a complete bundle"
        assert_valid_job_bundle(bundle / "template.yaml")
        parameters = yaml.safe_load((bundle / "parameter_values.yaml").read_text())
        values = {item["name"]: item["value"] for item in parameters["parameterValues"]}
        assert values["Frames"] == "1-10", values
        assert values["WriteNode"] == "Write1", values
        assert Path(values["NukeScriptFile"]) == scene, values
        _assert_expected_mock_traffic(mock_backend)
        print("Qt-driven Nuke export passed: frame override 1-10, Write1, valid bundle")
    finally:
        stop_process_tree(process, group)
