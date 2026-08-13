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
from typing import Optional

TERMINATE_TIMEOUT = 15.0
KILL_TIMEOUT = 5.0


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


def stop_process_tree(process: subprocess.Popen, group: Optional[int]) -> None:
    """Stop *process* and every remaining process in its *group*.

    Handles both shapes of teardown:

    * The process is still running: signal the group, terminate, wait (which
      also reaps it, so no zombie accumulates per launch), escalating to
      ``SIGKILL`` if it does not go quietly.
    * The process has already exited — it crashed, or the launcher's startup
      loop observed an early exit. ``Popen.poll`` has reaped it already.

    Either way the leader ends up reaped, so both paths finish the same way:
    sweep the group for children that outlived it, unless the group id has
    since been handed to somebody else.

    The two signals sent while the leader is still alive are deliberately not
    guarded that way. ``group_id_was_recycled`` asks whether a live process
    owns the id, and before the leader is reaped that process is our own
    leader — so the guard would report every live session as recycled and
    suppress the very signals that stop it.
    """
    if process.poll() is None:
        signal_process_group(group)
        process.terminate()
        try:
            process.wait(timeout=TERMINATE_TIMEOUT)
        except subprocess.TimeoutExpired:
            signal_process_group(group, force=True)
            process.kill()
            process.wait(timeout=KILL_TIMEOUT)
    # The leader is reaped now, so the group id — which is its pid — is free
    # for reuse the moment the group empties. Children still in the group
    # keep the id ours (see the module docstring); a live process owning it
    # means it was reassigned, and signalling it would hit a stranger.
    if not group_id_was_recycled(group):
        signal_process_group(group, force=True)
