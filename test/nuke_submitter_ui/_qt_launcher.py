# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Run a case's configurator and export through Qt events inside GUI Nuke."""

import json
import os
import subprocess
import time

from _process import capture_process_group, stop_process_tree


def export_with_qt(nuke_executable, environment, work_dir, configurator):
    if os.environ.get("NUKE_SUBMITTER_UI_DIALOG_DUMP") == "1":
        raise ValueError("NUKE_SUBMITTER_UI_DIALOG_DUMP requires the xa11y driver")
    result = work_dir / "qt-result.json"
    environment = dict(environment)
    environment["NUKE_SUBMITTER_QT_RESULT"] = str(result)
    environment["NUKE_SUBMITTER_QT_CONFIGURATOR"] = str(configurator)
    with (
        (work_dir / "nuke_stdout.log").open("w") as stdout,
        (work_dir / "nuke_stderr.log").open("w") as stderr,
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
            status = work_dir / "opener_status.txt"
            if status.exists():
                text = status.read_text()
                if text.startswith("ERROR"):
                    raise AssertionError(text)
            assert process.poll() is None, "Nuke exited; inspect nuke_stdout/stderr.log"
            time.sleep(0.25)
        assert result.exists(), "Qt driver produced no result; inspect Nuke logs"
        report = json.loads(result.read_text())
        assert report["ok"], report
    finally:
        stop_process_tree(process, group)
