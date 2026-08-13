# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Process-tree teardown for the launched DCC, independent of the GUI stack.

Kept free of the accessibility and Deadline test dependencies (stdlib only)
so the teardown rules can be unit tested on every build, rather than only
where a licensed Nuke is installed. See
``test/unit/test_nuke_submitter_ui_process.py``.

Why a process *group* is involved at all: Nuke starts children that outlive a
plain ``terminate()`` of the process the suite launched — the crash handler,
the frame server worker and its render workers. Left behind, they accumulate
across a multi-case run and interfere with later launches, because the frame
server binds a fixed port and holds a license. The launcher therefore starts
Nuke with ``start_new_session=True``, making it a process-group leader so the
whole tree can be stopped by group.

Process-group ids and reuse, since the safety of all of this turns on it
(POSIX XBD 4.17, "Process ID Reuse"):

* A process group id is the pid of its leader, and is NOT reused while any
  process remains in the group. So a group that still exists is still ours,
  even after its leader has exited — which is what makes cleanup safe in the
  case that matters most, a Nuke that crashed while its frame server kept
  running.
* The leader's *pid*, by contrast, becomes reusable once the leader has been
  reaped. A live process owning that pid therefore means the id has been
  recycled and the group is somebody else's; it must be left alone.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import Optional

TERMINATE_TIMEOUT = 15.0
KILL_TIMEOUT = 5.0
# How long the group's survivors get to exit after SIGTERM before they are
# killed. Matched to TERMINATE_TIMEOUT because the frame server needs the
# same kind of grace Nuke does: releasing its license seat means a round trip
# to the license server before the process can exit, and killing it mid
# handshake leaves the seat held, which is the residue this module exists to
# clear. The window is spent on anything that has not finished exiting,
# whether it ignores SIGTERM or is merely slow, but a longer one is close to
# free: the poll ends the moment the group empties, measured at 0.00s for a
# group whose children exit on SIGTERM.
DRAIN_TIMEOUT = 15.0
DRAIN_POLL_INTERVAL = 0.1


def capture_process_group(process: subprocess.Popen) -> Optional[int]:
    """The child's process group, resolved while it is known to be alive.

    Captured once at launch rather than per signal: after the child has been
    reaped, ``os.getpgid`` on its pid either fails or, if the pid has been
    recycled, reports an unrelated process's group.
    """
    if sys.platform == "win32":
        return None
    try:
        return os.getpgid(process.pid)
    except (ProcessLookupError, PermissionError):
        # Raced with an immediate exit, or not ours to inspect. Cleanup falls
        # back to signalling the process directly.
        return None


def signal_process_group(group: Optional[int], *, force: bool = False) -> None:
    """Best-effort signal to a captured process group (POSIX only).

    The signal is resolved inside the platform guard because Windows has no
    ``SIGKILL`` at all, so naming it in a caller would not type-check there —
    and, worse, would raise ``AttributeError`` at the call site before the
    guard could run.
    """
    if sys.platform == "win32" or group is None:
        return
    if group == os.getpgrp():
        # Never signal our own group: that would take down pytest. This means
        # start_new_session did not take effect, so leave the children to the
        # direct terminate/kill instead.
        return
    try:
        os.killpg(group, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        # Nothing left in the group — the expected outcome of a final sweep
        # when the earlier signal already stopped every child.
        pass
    except PermissionError:
        # Not ours to signal. Cleanup is best-effort and must never mask the
        # test's own failure.
        pass


def group_id_was_recycled(group: Optional[int]) -> bool:
    """Whether *group*'s id now belongs to an unrelated process.

    Only meaningful once our leader has been reaped. A live process owning
    the id means it was handed out again, so the group must not be signalled;
    the id being free means any group still using it is ours (see the module
    docstring on POSIX reuse rules).
    """
    if sys.platform == "win32" or group is None:
        return False
    try:
        os.kill(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The pid exists and belongs to another user, so it is certainly not
        # our reaped leader.
        return True
    return True


def group_has_members(group: Optional[int]) -> bool:
    """Whether any process is still in *group* and signallable by us."""
    if sys.platform == "win32" or group is None:
        return False
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # It exists but is not ours to signal, so as far as cleanup is
        # concerned there is nothing here to act on.
        return False
    return True


def sweep_process_group(
    group: Optional[int],
    *,
    drain_timeout: float = DRAIN_TIMEOUT,
    group_is_ours: bool = False,
) -> None:
    """Stop whatever is left in *group*, asking before insisting.

    SIGTERM first, because a frame server that shuts down releases its
    license seat, while one that is killed outright leaves the seat held
    until the license server's heartbeat expires — which is the residue that
    breaks the next launch, the whole reason this module exists. Anything
    still there when the drain window closes is killed.

    The reuse check runs twice: once before signalling, and again after the
    wait, because the window is long enough for a freed group id to be handed
    to somebody else while we are draining.

    Pass *group_is_ours* to skip those checks, which callers may do only with
    independent proof that the id cannot have been handed out. There is
    exactly one such proof: a leader that has not been reaped still occupies
    the pid the group is named after. That case has to be spelled out,
    because the check reads it backwards on its own — a live pid normally
    means the id was reassigned, but an unreaped leader is the one situation
    where a live pid means the opposite.
    """
    if not group_is_ours and group_id_was_recycled(group):
        return
    signal_process_group(group)
    deadline = time.monotonic() + drain_timeout
    while time.monotonic() < deadline:
        if not group_has_members(group):
            return
        time.sleep(DRAIN_POLL_INTERVAL)
    if not group_is_ours and group_id_was_recycled(group):
        return
    signal_process_group(group, force=True)


def stop_process_tree(
    process: subprocess.Popen,
    group: Optional[int],
    *,
    drain_timeout: float = DRAIN_TIMEOUT,
) -> None:
    """Stop *process* and every remaining process in its *group*.

    Handles both shapes of teardown:

    * The process is still running: signal the group, terminate, wait (which
      also reaps it, so no zombie accumulates per launch), escalating to
      ``SIGKILL`` if it does not go quietly.
    * The process has already exited — it crashed, or the launcher's startup
      loop observed an early exit. ``Popen.poll`` has reaped it already.

    Both paths finish by sweeping the group for children that outlived the
    leader. Whether that sweep may signal depends on the leader having been
    reaped, which is what makes its pid, and therefore the group id,
    reusable; the one case where the leader survives its own SIGKILL is
    called out below.

    The two signals sent while the leader is still alive are deliberately not
    guarded that way. ``group_id_was_recycled`` asks whether a live process
    owns the id, and before the leader is reaped that process is our own
    leader — so the guard would report every live session as recycled and
    suppress the very signals that stop it.
    """
    leader_reaped = True
    if process.poll() is None:
        signal_process_group(group)
        process.terminate()
        try:
            process.wait(timeout=TERMINATE_TIMEOUT)
        except subprocess.TimeoutExpired:
            signal_process_group(group, force=True)
            process.kill()
            try:
                process.wait(timeout=KILL_TIMEOUT)
            except subprocess.TimeoutExpired:
                # Already SIGKILLed, so reaching this means the process is
                # wedged in the kernel — an uninterruptible read against a
                # hung license server or file server, say. Nothing further
                # can be done about it, and raising from teardown would
                # replace whatever failure asked for the teardown: on the
                # launcher's failure path that diagnostic is the point (it
                # carries Nuke's log tails), and in a fixture it would turn
                # a real assertion failure into a teardown error. The cost
                # is one leaked zombie in a case that is already lost.
                leader_reaped = False
    # An unreaped leader still holds the pid the group is named after, which
    # is proof the id cannot have been reassigned, so the sweep is told to
    # skip its reuse checks: they read a live pid as evidence of reassignment
    # and would otherwise suppress the sweep in the one case it is certainly
    # safe. Where the leader was reaped, the id is free the moment the group
    # empties, and the checks are exactly what keeps us off a stranger's
    # group.
    sweep_process_group(group, drain_timeout=drain_timeout, group_is_ours=not leader_reaped)
