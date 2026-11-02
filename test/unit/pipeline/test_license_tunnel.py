# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Exercise the tunnel lifecycle with local subprocesses and fake AWS responses."""

import importlib.util
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import Mock

import pytest


@pytest.fixture
def tunnel():
    path = Path(__file__).resolve().parents[3] / "pipeline" / "license-tunnel.py"
    spec = importlib.util.spec_from_file_location("license_tunnel", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def configured(tunnel, tmp_path, monkeypatch):
    for name, value in {
        "RUNNER_TEMP": str(tmp_path),
        "AWS_REGION": "test-region",
        "LICENSE_ROLE_ARN": "private-role",
        "BASTION_INSTANCE_TAG": "private-tag",
        "FOUNDRY_LICENSE_PORT": "6101",
    }.items():
        monkeypatch.setenv(name, value)
    # Never probe a real license tunnel on a developer's machine.
    monkeypatch.setattr(
        tunnel.socket, "create_connection", Mock(side_effect=ConnectionRefusedError)
    )
    return tunnel


def test_readiness_rejects_dead_tunnel(tunnel):
    with pytest.raises(RuntimeError, match="exited before"):
        tunnel.wait_for_tunnel(Mock(poll=lambda: 1), 6101)


def test_readiness_connects_on_loopback(tunnel):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        tunnel.wait_for_tunnel(Mock(poll=lambda: None), listener.getsockname()[1], timeout=1)


def test_failed_readiness_terminates_partial_session(configured, tmp_path, monkeypatch):
    calls = []

    def aws(arguments, environment):
        assert (tmp_path / "nuke-license-config").stat().st_mode & 0o777 == 0o600
        calls.append(arguments)
        return b'["i-0123456789abcdef0"]'

    monkeypatch.setattr(configured, "aws", aws)
    process = Mock(pid=99999999)

    # The log gets a session ID even though the local port never becomes ready.
    def popen(*args, **kwargs):
        kwargs["stdout"].write("Starting session with SessionId: test-session\n")
        kwargs["stdout"].flush()
        return process

    monkeypatch.setattr(configured.subprocess, "Popen", popen)
    monkeypatch.setattr(configured, "stop_process", Mock())
    monkeypatch.setattr(
        configured,
        "wait_for_tunnel",
        Mock(side_effect=RuntimeError("readiness failed")),
    )
    with pytest.raises(RuntimeError, match="readiness failed"):
        configured.main(["--", "unused-test-command"])
    configured.stop_process.assert_any_call(process)
    assert calls[-1] == ["ssm", "terminate-session", "--session-id", "test-session"]
    assert not (tmp_path / "nuke-license-config").exists()
    # The fallback step is safe after the finally block has already terminated it.
    assert configured.main(["--cleanup"]) == 0
    assert len(calls) == 2


def test_cleanup_retries_remote_termination(configured, tmp_path, monkeypatch):
    (tmp_path / "nuke-license-config").touch()
    (tmp_path / "nuke-license-ssm.log").write_text("SessionId: test-session\n")
    mock = Mock(return_value=b"")
    monkeypatch.setattr(configured, "aws", mock)
    assert configured.main(["--cleanup"]) == 0
    assert mock.call_args.args[0] == ["ssm", "terminate-session", "--session-id", "test-session"]
    assert not (tmp_path / "nuke-license-ssm.log").exists()


def test_failed_remote_cleanup_preserves_retry_state(configured, tmp_path, monkeypatch):
    (tmp_path / "nuke-license-config").touch()
    (tmp_path / "nuke-license-ssm.log").write_text("SessionId: test-session\n")
    monkeypatch.setattr(configured, "aws", Mock(side_effect=RuntimeError("cleanup failed")))
    with pytest.raises(RuntimeError, match="cleanup failed"):
        configured.main(["--cleanup"])
    assert (tmp_path / "nuke-license-config").exists()
    assert (tmp_path / "nuke-license-ssm.log").exists()


def test_multiple_bastions_fail_before_starting_session(configured, monkeypatch):
    monkeypatch.setattr(configured, "aws", Mock(return_value=b'["i-12345678", "i-87654321"]'))
    start = Mock()
    monkeypatch.setattr(configured.subprocess, "Popen", start)
    with pytest.raises(RuntimeError, match="exactly one"):
        configured.main(["--", "unused-test-command"])
    start.assert_not_called()


@pytest.mark.parametrize("lost_tunnel", [False, True])
def test_test_failure_or_tunnel_loss_stops_both_processes(configured, monkeypatch, lost_tunnel):
    monkeypatch.setattr(configured, "aws", Mock(return_value=b'["i-0123456789abcdef0"]'))
    ssm = Mock(poll=lambda: 1 if lost_tunnel else None)
    tests = Mock(poll=lambda: None if lost_tunnel else 7, returncode=7)
    monkeypatch.setattr(configured.subprocess, "Popen", Mock(side_effect=[ssm, tests]))
    monkeypatch.setattr(configured, "wait_for_tunnel", Mock())
    stop = Mock()
    monkeypatch.setattr(configured, "stop_process", stop)
    if lost_tunnel:
        with pytest.raises(RuntimeError, match="during the GUI test"):
            configured.main(["--", "unused-test-command"])
    else:
        assert configured.main(["--", "unused-test-command"]) == 7
    assert [call.args[0] for call in stop.call_args_list] == [tests, ssm]


def test_stop_process_kills_group(tunnel):
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"],
        start_new_session=True,
    )
    try:
        tunnel.stop_process(process)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_stop_process_does_not_signal_a_recycled_group_id(tunnel, monkeypatch):
    process = Mock(pid=123, returncode=0)
    monkeypatch.setattr(tunnel.os, "kill", Mock())  # another live process owns PID 123
    kill_group = Mock()
    monkeypatch.setattr(tunnel.os, "killpg", kill_group)
    tunnel.stop_process(process)
    kill_group.assert_not_called()
