# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the GUI test suite's process-tree teardown.

The module under test is ``test/nuke_submitter_ui/_process.py``, which the
xa11y submitter UI suite uses to stop Nuke and the helper processes it
spawns. It is deliberately free of the GUI suite's dependencies so these
tests run in the normal unit suite on every platform, instead of only where a
licensed Nuke is installed — the teardown rules are subtle enough that they
should not go unverified on machines that cannot run the GUI suite.

A ``/bin/sh`` process that backgrounds a child stands in for Nuke and its
frame server: a leader with a descendant that outlives it, in its own process
group, which is the shape that makes teardown non-trivial.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Tuple

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "nuke_submitter_ui" / "_process.py"


def _load_process_module():
    """Load the suite's _process module by path.

    Imported this way rather than via ``sys.path`` because the GUI suite's
    directory is not a package and importing its siblings would pull in xa11y
    and the Deadline test fixtures, which the unit test environment does not
    install.
    """
    spec = importlib.util.spec_from_file_location("nuke_submitter_ui_process", _MODULE_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {_MODULE_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


process_module = _load_process_module()

# Applied per test rather than to the module: the last test covers the
# no-process-group path and must run everywhere, including on Windows, where
# it is the real behaviour rather than a simulation.
posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX process groups; on Windows the teardown is a plain terminate()",
)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists, owned by somebody else.
        return True
    return True


def _wait_until(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@contextmanager
def _stand_in_for_nuke(tmp_path: Path, child_command: str):
    """A process group holding a leader and a descendant that outlives it.

    Yields ``(process, group, child_pid)``. Teardown goes through
    ``stop_process_tree`` rather than killing the recorded pids directly: by
    then the leader has usually been reaped and its descendant collected by
    init, so signalling those raw pids would risk hitting whatever has since
    been given them — the very hazard this module exists to avoid. A test
    that leaves the group alive is therefore cleaned up by the same guarded
    path it exercises, and a test that already stopped it costs nothing.
    """
    child_pid_file = tmp_path / "child.pid"
    process = subprocess.Popen(
        ["/bin/sh", "-c", f"{child_command} & echo $! > {child_pid_file}; sleep 300"],
        start_new_session=True,
    )
    group: Optional[int] = None
    try:
        assert _wait_until(
            lambda: child_pid_file.is_file() and child_pid_file.read_text().strip().isdigit()
        ), "stand-in process never reported its child"
        group = process_module.capture_process_group(process)
        child_pid = int(child_pid_file.read_text().strip())
        assert group == process.pid, "start_new_session should make the process a group leader"
        assert _alive(child_pid)
        yield process, group, child_pid
    finally:
        process_module.stop_process_tree(process, group)


@pytest.fixture
def leader_with_child(tmp_path: Path) -> Iterator[Tuple[subprocess.Popen, Optional[int], int]]:
    with _stand_in_for_nuke(tmp_path, "sleep 300") as stand_in:
        yield stand_in


@posix_only
def test_stops_descendant_when_leader_is_running(leader_with_child) -> None:
    process, group, child_pid = leader_with_child

    process_module.stop_process_tree(process, group)

    assert _wait_until(lambda: not _alive(child_pid)), "descendant outlived the teardown"
    assert process.returncode is not None, "leader was not reaped, leaving a zombie"


@posix_only
def test_stops_descendant_when_leader_already_exited(leader_with_child) -> None:
    """The case that leaks if teardown gives up on an already-exited leader.

    Nuke crashing, or exiting early enough for the launcher's startup loop to
    notice, leaves the frame server running and holding its port and license.
    """
    process, group, child_pid = leader_with_child
    process.terminate()
    process.wait(timeout=10)
    assert _alive(child_pid), "precondition: the descendant outlives its leader"

    process_module.stop_process_tree(process, group)

    assert _wait_until(lambda: not _alive(child_pid)), "descendant survived an exited leader"


@posix_only
def test_stops_descendant_that_ignores_sigterm(tmp_path: Path) -> None:
    """The final sweep has to escalate for a child that refuses SIGTERM.

    This is the path that reaches the sweep with the group still populated:
    the leader is gone and reaped, so its id is free, yet the group is still
    ours because the stubborn child remains in it.
    """
    stubborn_child = "/bin/sh -c 'trap \"\" TERM; sleep 300'"
    with _stand_in_for_nuke(tmp_path, stubborn_child) as (process, group, child_pid):
        process_module.stop_process_tree(process, group)

        assert _wait_until(
            lambda: not _alive(child_pid)
        ), "a SIGTERM-ignoring descendant was never escalated to SIGKILL"


@posix_only
def test_group_id_is_not_signalled_once_recycled(leader_with_child) -> None:
    """A group id taken over by a live process must be left alone."""
    process, group, child_pid = leader_with_child

    # The current process stands in for whatever took the id over; its pid is
    # certainly live, which is the only signal the check has to go on.
    assert process_module.group_id_was_recycled(os.getpid()) is True
    # Our leader is alive here, so its id is genuinely still ours.
    assert process_module.group_id_was_recycled(group) is True

    process.terminate()
    process.wait(timeout=10)
    # Reaped, so the id is free: the surviving group must still be swept.
    assert process_module.group_id_was_recycled(group) is False


@posix_only
def test_teardown_is_inert_for_an_already_stopped_group(leader_with_child) -> None:
    process, group, child_pid = leader_with_child

    process_module.stop_process_tree(process, group)
    assert _wait_until(lambda: not _alive(child_pid))

    # Nothing left to signal; a second call must not raise.
    process_module.stop_process_tree(process, group)


def test_capture_returns_none_without_process_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_module.sys, "platform", "win32")
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert process_module.capture_process_group(process) is None
        # Signalling a group is a no-op there rather than an error.
        process_module.signal_process_group(None, force=True)
    finally:
        process.kill()
        process.wait(timeout=5)
