# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Stops the launched DCC and the helper processes it spawns.

Stdlib only, so these rules are unit tested on every build instead of only
where a licensed Nuke exists (``test/unit/test_nuke_submitter_ui_process.py``).

Nuke's crash handler, frame server and render workers outlive a plain
``terminate()`` of the process the suite launched, and left running they break
later launches: the frame server binds a fixed port and holds a license. The
launcher therefore starts Nuke with ``start_new_session=True`` so teardown can
work by process group.

Group ids and reuse (POSIX XBD 4.17) are what make that safe. A group id is
its leader's pid and is not reused while any member remains, so a group that
still exists is still ours even after the leader has gone. The leader's pid
becomes reusable once reaped, so a live process owning it means the id was
reassigned and the group is somebody else's.

Windows has no process groups, so teardown there stops the launched process
only and leaves whatever it spawned. The suite does not run on Windows yet; a
Job Object or ``taskkill /T`` would be the fix when it does.
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
# Grace for the group's survivors, matched to the leader's: releasing a
# license seat means a round trip to the license server, and killing the frame
# server mid handshake leaves the seat held. A long window is nearly free
# because the poll ends as soon as the group empties (measured 0.00s when
# children exit on SIGTERM).
DRAIN_TIMEOUT = 15.0
DRAIN_POLL_INTERVAL = 0.1


def capture_process_group(process: subprocess.Popen) -> Optional[int]:
    """The process's group, resolved while it is known to be alive.

    Captured once at launch: after the process is reaped its pid, and so the
    group id, may belong to somebody else.
    """
    if sys.platform == "win32":
        return None
    try:
        return os.getpgid(process.pid)
    except (ProcessLookupError, PermissionError):
        # Raced with an immediate exit, or not ours to inspect.
        return None


def signal_process_group(group: Optional[int], *, force: bool = False) -> None:
    """SIGTERM (or SIGKILL) *group*, best effort.

    The signal is named inside the platform guard because Windows has no
    ``SIGKILL``: naming it in a caller would raise ``AttributeError`` there.
    """
    if sys.platform == "win32" or group is None:
        return
    if group == os.getpgrp():
        # Signalling our own group would take down pytest.
        return
    try:
        os.killpg(group, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        # Group already empty, the usual outcome of a second pass.
        pass
    except PermissionError:
        # Not ours. Cleanup must never mask the test's own failure.
        pass


def group_id_was_recycled(group: Optional[int]) -> bool:
    """Whether a live process now owns *group*'s id.

    Only meaningful once our leader has been reaped, since before that the
    live process owning the id is the leader itself.
    """
    if sys.platform == "win32" or group is None:
        return False
    try:
        os.kill(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, and owned by someone else
    # This gates the sweep's SIGKILL, so a zombie answering the probe is the
    # expensive direction: an unrelated short-lived process can take the freed
    # pid and exit unwaited, and reading it as a new owner would abandon the
    # escalation while our frame server still holds the group.
    return not process_is_zombie(group)


def zombie_from_stat(content: bytes) -> bool:
    """Whether /proc/<pid>/stat *content* describes a process left to be waited for.

    comm is field 2 and may itself contain spaces and parens, so the fields
    after it are located from the last ')' rather than by splitting the line.

    State 'Z' alone is not enough. A thread-group leader whose main thread
    exited while its siblings keep running is held in EXIT_ZOMBIE by the kernel
    (delay_group_leader) and reports 'Z' here for as long as the process is
    alive and working -- ps shows it as defunct. Reading that as finished would
    skip the SIGKILL escalation on a live Nuke or frame server, both of which
    are heavily threaded. num_threads (field 20) tells the two apart without a
    second open(): a real zombie has exactly one.
    """
    fields = content.rpartition(b")")[2].split()
    return fields[0] == b"Z" and fields[17] == b"1"


def _read_is_zombie(pid: int) -> bool:
    """Whether *pid* is a zombie, per procfs.

    Raises FileNotFoundError if the process is gone, other OSError if its stat
    is present but unreadable, and IndexError if the content does not parse.
    """
    with open(f"/proc/{pid}/stat", "rb") as stat:
        return zombie_from_stat(stat.read())


def process_is_zombie(pid: int) -> bool:
    """Whether *pid* has exited but not yet been waited for.

    Needs procfs, so this answers False on macOS. That costs nothing there:
    launchd reaps an orphan before the first poll, so a zombie is never
    observed in the first place. Anything unreadable also answers False, which
    keeps the caller's reading of "still alive" for a process it cannot judge.
    """
    try:
        return _read_is_zombie(pid)
    except (OSError, IndexError):
        return False


def _group_is_only_zombies(group: int) -> bool:
    """Whether every member of *group* was positively read as a zombie.

    Membership comes from getpgid rather than from whether procfs could be
    read, so doubt is scoped to actual members: an unreadable pid elsewhere on
    the system cannot veto the answer, and only members cost an open().

    False on any doubt about a member -- and when no member is found at all --
    because the only cost of leaving the group considered populated is one
    extra SIGKILL to a group we already believe is ours, while the cost of
    wrongly calling it drained is skipping that escalation and stranding the
    survivor this module exists to kill. A member can be unreadable while
    killpg still succeeds: signal permission and procfs visibility are
    separate checks.
    """
    if sys.platform == "win32":
        # Unreachable via group_has_members, which returns earlier, but the
        # guard is what lets a type check for Windows prune getpgid below.
        return False
    try:
        entries = os.listdir("/proc")
    except OSError:
        return False
    found_member = False
    for name in entries:
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            if os.getpgid(pid) != group:
                continue
        except ProcessLookupError:
            continue  # exited before we asked, so not a member
        except OSError:
            return False  # may be a member we cannot judge
        found_member = True
        try:
            is_zombie = _read_is_zombie(pid)
        except FileNotFoundError:
            continue  # gone since getpgid, so not a survivor
        except (OSError, IndexError):
            return False  # confirmed member, unreadable state
        if not is_zombie:
            return False
    return found_member


def group_has_members(group: Optional[int]) -> bool:
    """Whether *group* still holds a process we may signal."""
    if sys.platform == "win32" or group is None:
        return False
    try:
        os.killpg(group, 0)
    except (ProcessLookupError, PermissionError):
        # Empty, or not ours to act on.
        return False
    # killpg cannot tell a running member from an unreaped zombie, and an
    # orphan stays a zombie for as long as its reaper ignores it -- which pid 1
    # does in a container. Counting one as a member would make the drain below
    # always spend its full timeout on a group that is already finished.
    return not _group_is_only_zombies(group)


def sweep_process_group(
    group: Optional[int],
    *,
    drain_timeout: float = DRAIN_TIMEOUT,
    group_is_ours: bool = False,
) -> None:
    """Wait for *group* to drain after SIGTERM, then SIGKILL what is left.

    The reuse check guards the SIGKILL, since by then the leader is reaped and
    its pid, which is the group id, may have been handed out. *group_is_ours*
    skips it, and is only sound with proof the id cannot have been reassigned:
    an unreaped leader still occupies it. That case needs stating because the
    check reads a live pid as reassignment, which is backwards for a leader
    that never died.
    """
    deadline = time.monotonic() + drain_timeout
    while time.monotonic() < deadline:
        if not group_has_members(group):
            return
        time.sleep(DRAIN_POLL_INTERVAL)
    if not group_is_ours and group_id_was_recycled(group):
        return
    signal_process_group(group, force=True)


def _reap(process: subprocess.Popen) -> bool:
    """Wait for *process*, killing it if it ignored SIGTERM.

    False if it survived even SIGKILL, which means it is wedged in the kernel.
    Raising instead would replace the failure that asked for teardown, so the
    zombie is accepted.
    """
    if process.poll() is not None:
        return True
    try:
        process.wait(timeout=TERMINATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=KILL_TIMEOUT)
        except subprocess.TimeoutExpired:
            return False
    return True


def _stop_process(process: subprocess.Popen) -> bool:
    """Stop *process* alone, for when there is no group to signal."""
    if process.poll() is None:
        process.terminate()
    return _reap(process)


def stop_process_tree(
    process: subprocess.Popen,
    group: Optional[int],
    *,
    drain_timeout: float = DRAIN_TIMEOUT,
) -> None:
    """Stop *process*, then anything left in its *group*.

    The group is what catches children, which do not exit with their parent.
    """
    if sys.platform == "win32":
        # No process groups: helpers Nuke spawned are unreachable.
        _stop_process(process)
        return
    if group is None or group == os.getpgrp():
        # Capture failed, or start_new_session did not take effect and the
        # group is our own, which must never be signalled.
        _stop_process(process)
        return
    # A leader belongs to its own group, so this asks it and its children to
    # exit together and no separate terminate() is needed.
    signal_process_group(group)
    reaped = _reap(process)
    # The leader must be reaped before draining: until then it is a member of
    # its own group, so the poll could never see the group empty. An unreaped
    # leader still holds the group id, which proves it was not reassigned.
    sweep_process_group(group, drain_timeout=drain_timeout, group_is_ours=not reaped)
