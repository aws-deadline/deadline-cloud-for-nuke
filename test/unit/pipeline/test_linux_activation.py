# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Test Linux activation without importing optional GUI/runtime dependencies."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def launcher(monkeypatch):
    def stub(name, **attributes):
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    stub("xa11y", XA11yError=RuntimeError, App=Mock(), screenshot=Mock())
    stub("deadline_test_fixtures")
    stub("deadline_test_fixtures.deadline_mock", build_mock_environment=Mock())
    stub("deadline_test_fixtures.xa11y", find_accessibility_app=Mock())
    stub("_process", capture_process_group=Mock(), stop_process_tree=Mock())
    stub("_windows_process", WindowsProcessJob=Mock())
    path = Path(__file__).resolve().parents[2] / "nuke_submitter_ui" / "_launcher.py"
    spec = importlib.util.spec_from_file_location("linux_launcher_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.sys, "platform", "linux")
    monkeypatch.setattr(module.time, "sleep", Mock())
    return module


def test_linux_activates_when_no_foreground_window_exists(launcher):
    window = Mock()
    launcher.xa11y.App.foreground.side_effect = [RuntimeError("no foreground"), Mock(pid=123)]
    launcher.xa11y.App.by_pid.return_value.windows.return_value = [window]
    assert launcher._activate_app(123)
    window.activate.assert_called_once()


def test_linux_foreground_needs_no_activation(launcher):
    launcher.xa11y.App.foreground.return_value.pid = 123
    assert launcher._activate_app(123)
    launcher.xa11y.App.by_pid.assert_not_called()


def test_linux_returns_false_when_focus_never_arrives(launcher, monkeypatch):
    monkeypatch.setattr(launcher.time, "monotonic", Mock(side_effect=[0, 0, 2]))
    launcher.xa11y.App.foreground.side_effect = RuntimeError("no foreground")
    launcher.xa11y.App.by_pid.return_value.windows.return_value = []
    assert not launcher._activate_app(123, timeout=1)


def test_session_captures_diagnostics_before_stopping(launcher, monkeypatch, tmp_path):
    monkeypatch.setenv("NUKE_SUBMITTER_UI_CAPTURE_DIAGNOSTICS", "1")
    app = Mock(dump=lambda **_: "mock accessibility tree")
    process = Mock()
    session = launcher.NukeSession(process, app, tmp_path, "OK", process_group=123)
    session.close()
    assert (tmp_path / "accessibility-tree.txt").read_text() == "mock accessibility tree"
    launcher.xa11y.screenshot.return_value.save_png.assert_called_once_with(
        str(tmp_path / "nuke-screen.png")
    )
    launcher.stop_process_tree.assert_called_once_with(process, 123)


def test_failed_diagnostics_cannot_prevent_cleanup(launcher, monkeypatch, tmp_path):
    monkeypatch.setenv("NUKE_SUBMITTER_UI_CAPTURE_DIAGNOSTICS", "1")
    process = Mock()
    session = launcher.NukeSession(process, Mock(), tmp_path / "missing", "OK", process_group=123)
    session.close()
    launcher.stop_process_tree.assert_called_once_with(process, 123)
