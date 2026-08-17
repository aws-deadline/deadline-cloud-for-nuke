# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for test/nuke_submitter_ui/_process.py, the GUI suite's teardown.

A /bin/sh process that backgrounds a child stands in for Nuke and its frame
server: a leader with a descendant that outlives it, in its own process group.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Tuple, cast

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "nuke_submitter_ui" / "_process.py"


def _load_process_module():
    """Load the suite's _process module by path.

    By path rather than sys.path: the GUI suite's directory is not a package,
    and its siblings import xa11y, which this environment does not install.
    """
    spec = importlib.util.spec_from_file_location("nuke_submitter_ui_process", _MODULE_PATH)
    assert spec is not None and spec.loader is not None, f"cannot load {_MODULE_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


process_module = _load_process_module()

# Per test, not module-wide: the no-process-group case must also run on
# Windows, where it is real behaviour rather than a simulation.
posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX process groups; on Windows the teardown is a plain terminate()",
)


# For tests that deliberately spend the window; /bin/sh needs no grace.
SHORT_DRAIN = 0.5


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
    """Yields (process, group, child_pid) for a leader with a live descendant.

    Teardown goes through stop_process_tree rather than killing the recorded
    pids, which by then may have been reassigned.
    """
    child_pid_file = tmp_path / "child.pid"
    process = subprocess.Popen(
        ["/bin/sh", "-c", f"{child_command} & echo $! > '{child_pid_file}'; sleep 300"],
        start_new_session=True,
    )
    group: Optional[int] = None
    try:
        # Before anything that can fail: teardown needs the group to reach
        # the backgrounded child, so a failed assertion below would leak it.
        group = process_module.capture_process_group(process)
        assert _wait_until(
            lambda: child_pid_file.is_file() and child_pid_file.read_text().strip().isdigit()
        ), "stand-in process never reported its child"
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
        # A short window keeps this quick: the production default is sized for
        # a frame server releasing a license seat, not for /bin/sh.
        process_module.stop_process_tree(process, group, drain_timeout=SHORT_DRAIN)

        assert _wait_until(
            lambda: not _alive(child_pid)
        ), "a SIGTERM-ignoring descendant was never escalated to SIGKILL"


@posix_only
def test_survivors_get_a_chance_to_exit_cleanly(tmp_path: Path) -> None:
    """The sweep asks the group to stop before it kills it.

    Driven through the exited-leader path on purpose: there the sweep is the
    only thing that signals the group, so the child's SIGTERM handler running
    can only be the sweep's doing. (On the live-leader path the child would
    receive SIGTERM before the leader is even terminated, which would prove
    nothing about the sweep.)

    It matters for the frame server specifically: shutting down releases its
    license seat, whereas being killed leaves the seat held until the license
    server's heartbeat expires.
    """
    farewell = tmp_path / "farewell"
    graceful_child = f"/bin/sh -c 'trap \"echo bye > {farewell}; exit 0\" TERM; sleep 300'"
    with _stand_in_for_nuke(tmp_path, graceful_child) as (process, group, child_pid):
        # Stop the leader alone, so nothing has signalled the group yet.
        process.terminate()
        process.wait(timeout=10)
        assert _alive(child_pid), "precondition: the descendant outlives its leader"
        assert not farewell.exists(), "precondition: the descendant has not been signalled"

        process_module.stop_process_tree(process, group)

        assert _wait_until(lambda: not _alive(child_pid)), "descendant outlived the teardown"
        assert farewell.is_file(), "descendant was killed without being asked to stop first"


@posix_only
def test_sweep_leaves_a_group_alone_when_the_id_may_be_reassigned(leader_with_child) -> None:
    """With a live pid owning the group id, the sweep must not signal.

    Standing in for the case it exists to prevent: our leader was reaped and
    the id has since been handed to an unrelated process. That cannot be
    staged directly, since pid reuse is not controllable, so this uses the
    same input the check sees, a live process owning the id.
    """
    process, group, child_pid = leader_with_child

    process_module.sweep_process_group(group, drain_timeout=SHORT_DRAIN)

    assert _alive(child_pid), "the sweep signalled a group whose id might not be ours"


@posix_only
def test_sweep_runs_when_the_caller_knows_the_group_is_ours(leader_with_child) -> None:
    """An unreaped leader is proof the id was not reassigned.

    Without ``group_is_ours`` this is indistinguishable from a recycled id,
    so the sweep would skip and leave the group running. That is the state
    teardown is in when the leader survives its own SIGKILL.
    """
    process, group, child_pid = leader_with_child

    process_module.sweep_process_group(group, drain_timeout=SHORT_DRAIN, group_is_ours=True)

    assert _wait_until(lambda: not _alive(child_pid)), "descendant survived a sanctioned sweep"


class _NeverReaps:
    """A process whose wait() always times out, standing in for a wedged Nuke.

    Real uninterruptible sleep cannot be staged on demand, and this is the
    input that matters: teardown cannot reap the leader, so the group id is
    still ours and the sweep must go ahead anyway.
    """

    def __init__(self, process: subprocess.Popen) -> None:
        self._process = process

    def poll(self) -> None:
        return None

    def terminate(self) -> None:
        self._process.terminate()

    def kill(self) -> None:
        self._process.kill()

    def wait(self, timeout: Optional[float] = None) -> int:
        raise subprocess.TimeoutExpired(cmd="stand-in", timeout=timeout or 0)


@posix_only
def test_stops_descendant_when_the_leader_cannot_be_reaped(tmp_path: Path) -> None:
    stubborn_child = "/bin/sh -c 'trap \"\" TERM; sleep 300'"
    with _stand_in_for_nuke(tmp_path, stubborn_child) as (process, group, child_pid):
        wedged = cast(subprocess.Popen, _NeverReaps(process))

        process_module.stop_process_tree(wedged, group, drain_timeout=SHORT_DRAIN)

        assert _wait_until(
            lambda: not _alive(child_pid)
        ), "descendant survived a leader that could not be reaped"


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
