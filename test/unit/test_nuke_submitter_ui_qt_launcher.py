# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Unlicensed process checks for the in-Nuke Qt driver result channel."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(sys.platform == "win32", reason="Linux Qt launcher and executable stand-in")
@pytest.mark.parametrize("outcome", ["success", "driver_error", "opener_error"])
def test_stops_gui_process_after_driver_result(tmp_path, monkeypatch, outcome):
    suite = Path(__file__).resolve().parents[1] / "nuke_submitter_ui"
    process_module = load_module("_qt_test_process", suite / "_process.py")
    monkeypatch.setitem(sys.modules, "_process", process_module)
    launcher = load_module("_qt_test_launcher", suite / "_qt_launcher.py")
    executable = tmp_path / "stand-in-nuke"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, time\n"
        "result = pathlib.Path(os.environ['NUKE_SUBMITTER_QT_RESULT'])\n"
        f"outcome = {outcome!r}\n"
        "if outcome == 'opener_error':\n"
        "    (result.parent / 'opener_status.txt').write_text('ERROR\\nfailed to open dialog')\n"
        "else:\n"
        "    pending = result.with_suffix('.pending')\n"
        "    pending.write_text(json.dumps({'ok': outcome == 'success', 'error': outcome}))\n"
        "    pending.replace(result)\n"
        "time.sleep(300)\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    launched = []
    original_popen = subprocess.Popen

    def record_process(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr(launcher.subprocess, "Popen", record_process)
    # Protect the unit test against an inherited diagnostic-only setting.
    monkeypatch.delenv("NUKE_SUBMITTER_UI_DIALOG_DUMP", raising=False)
    if outcome == "success":
        launcher.export_with_qt(executable, os.environ.copy(), tmp_path, tmp_path / "configure.py")
    else:
        with pytest.raises(AssertionError, match="driver_error|failed to open dialog"):
            launcher.export_with_qt(
                executable, os.environ.copy(), tmp_path, tmp_path / "configure.py"
            )
    assert len(launched) == 1
    assert launched[0].poll() is not None, "Qt launcher leaked its GUI process"
