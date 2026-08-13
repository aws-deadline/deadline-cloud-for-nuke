# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Launch GUI Nuke with the Deadline Cloud submitter for xa11y-driven tests.

Modeled on ``deadline-cloud`` ``test/blender_submitter_ui``. Launches Nuke
in the foreground with the repo's ``src`` and this suite's ``_opener`` dir
on ``NUKE_PATH``; the opener hook builds a scene and opens the submitter
dialog, which tests then drive through the platform accessibility tree.

Environment notes (verified on macOS 15 / Nuke 16.0v7; see ``pages.py``
for the canonical platform notes on driving the dialog):

* ``build_mock_environment`` redirects the user profile dirs, which
  breaks Foundry licensing — the real ``HOME``/``USERPROFILE`` are
  restored and hermetic isolation relies on ``DEADLINE_CONFIG_FILE_PATH``.
* Inherited credential-sandbox variables (``AWS_SHARED_CREDENTIALS_FILE``
  etc.) cause a login-error popup inside Nuke — they are scrubbed.
* Activation goes through ``NSRunningApplication`` and is verified
  against ``xa11y.App.foreground()``, which is a getter, not an
  activator.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import xa11y
from deadline_test_fixtures.deadline_mock import build_mock_environment
from deadline_test_fixtures.xa11y import find_accessibility_app

from _process import capture_process_group, stop_process_tree

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENER_DIR = Path(__file__).resolve().parent / "_opener"

NUKE_STARTUP_TIMEOUT = 180.0  # GUI Nuke + license acquisition can be slow
OPENER_TIMEOUT = 120.0
ACTIVATE_TIMEOUT = 15.0

# Environment variables consumed by _opener/menu.py inside Nuke.
ENV_STATUS_FILE = "NUKE_SUBMITTER_UI_STATUS_FILE"
ENV_SCENE_FILE = "NUKE_SUBMITTER_UI_SCENE_FILE"
ENV_SCENE_SCRIPT = "NUKE_SUBMITTER_UI_SCENE_SCRIPT"
ENV_OPEN_DELAY_MS = "NUKE_SUBMITTER_UI_OPEN_DELAY_MS"

# Inherited AWS settings that would override the mock credentials or point
# at restricted files (e.g. agent credential sandboxes).
_SCRUBBED_ENV_VARS = ("AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE", "AWS_PROFILE")


def _version_key(path: Path) -> tuple[int, ...]:
    """Numeric sort key for install dirs like ``Nuke16.0v7`` (a plain
    lexical sort would rank Nuke9.5 above Nuke16.0)."""
    return tuple(int(number) for number in re.findall(r"\d+", path.name)) or (0,)


def find_nuke_executable() -> Path:
    """Locate the GUI Nuke executable (``NUKE_EXECUTABLE`` wins)."""
    override = os.environ.get("NUKE_EXECUTABLE")
    if override:
        path = Path(override)
        if path.exists():
            return path
        raise FileNotFoundError(f"NUKE_EXECUTABLE={override} does not exist")
    if sys.platform == "darwin":
        install_dirs = sorted(Path("/Applications").glob("Nuke*"), key=_version_key, reverse=True)
        for install_dir in install_dirs:
            for binary in sorted(install_dir.glob("Nuke*.app/Contents/MacOS/Nuke[0-9]*.[0-9]*")):
                if binary.is_file() and os.access(binary, os.X_OK):
                    return binary
    elif sys.platform.startswith("linux"):
        install_dirs = sorted(Path("/usr/local").glob("Nuke*"), key=_version_key, reverse=True)
        for install_dir in install_dirs:
            for binary in sorted(install_dir.glob("Nuke[0-9]*.[0-9]*")):
                if binary.is_file() and os.access(binary, os.X_OK):
                    return binary
    elif sys.platform == "win32":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        install_dirs = sorted(program_files.glob("Nuke*"), key=_version_key, reverse=True)
        for install_dir in install_dirs:
            for binary in sorted(install_dir.glob("Nuke[0-9]*.[0-9]*.exe")):
                if binary.is_file():
                    return binary
    raise FileNotFoundError(
        "No Nuke installation found. Set NUKE_EXECUTABLE to the GUI Nuke binary."
    )


def build_nuke_environment(
    *,
    deadline_endpoint_url: str,
    config_path: Path,
    work_dir: Path,
    scene_script: Path,
    scene_file: Path,
    open_delay_ms: int = 5000,  # keep in sync with _DELAY_MS fallback in _opener/menu.py
) -> dict[str, str]:
    """Hermetic environment for the Nuke subprocess pointed at the mock."""
    base_env = {k: v for k, v in os.environ.items() if k not in _SCRUBBED_ENV_VARS}
    env = build_mock_environment(
        base_env,
        deadline_endpoint_url=deadline_endpoint_url,
        config_path=config_path,
        home_dir=work_dir / "home",
    )
    # Foundry licensing and Nuke prefs live under the real user profile;
    # hermetic isolation is provided by DEADLINE_CONFIG_FILE_PATH and the
    # scrubbed vars, so undo build_mock_environment's HOME/USERPROFILE
    # redirection: restore each var the real environment defines and drop
    # the mock value otherwise (HOME is typically unset on Windows).
    for profile_var in ("HOME", "USERPROFILE"):
        if profile_var in os.environ:
            env[profile_var] = os.environ[profile_var]
        else:
            env.pop(profile_var, None)

    env["NUKE_PATH"] = f"{REPO_ROOT / 'src'}{os.pathsep}{OPENER_DIR}"
    env[ENV_STATUS_FILE] = str(work_dir / "opener_status.txt")
    env[ENV_SCENE_FILE] = str(scene_file)
    env[ENV_SCENE_SCRIPT] = str(scene_script)
    env[ENV_OPEN_DELAY_MS] = str(open_delay_ms)
    # Required for the AT-SPI bridge on Linux; harmless elsewhere.
    env["QT_ACCESSIBILITY"] = "1"
    env["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"] = "1"
    return env


def _activate_app(pid: int, timeout: float = ACTIVATE_TIMEOUT) -> bool:
    """Bring *pid*'s app to the foreground, verified via the AX bridge."""
    if sys.platform != "darwin":
        return True
    from AppKit import (  # type: ignore[import-not-found]
        NSApplicationActivateIgnoringOtherApps,
        NSRunningApplication,
    )

    try:
        if xa11y.App.foreground().pid == pid:
            return True  # already frontmost — skip the activation loop
    except Exception:
        # "Nothing focused" is transient while apps launch; fall through
        # to explicit activation below.
        pass
    ns_app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if ns_app is None:
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        ns_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        time.sleep(0.5)
        try:
            if xa11y.App.foreground().pid == pid:
                return True
        except Exception:
            # Foreground resolution can fail mid-activation; retry until
            # the deadline, then report failure to the caller.
            pass
    return False


@dataclass
class NukeSession:
    """A running GUI Nuke process with its accessibility handle."""

    process: subprocess.Popen
    app: xa11y.App
    work_dir: Path
    opener_status: str
    # Resolved at launch; see capture_process_group. None on Windows, which
    # has no process groups, and when the lookup failed.
    process_group: Optional[int] = None

    def activate(self) -> bool:
        """(Re-)raise Nuke to the foreground (see pages.py platform notes)."""
        return _activate_app(self.process.pid)

    def close(self) -> None:
        """Stop Nuke and the helper processes it spawned.

        See ``_process.stop_process_tree`` for the teardown sequence and the
        process-group reuse rules it relies on.

        The captured group is dropped afterwards so this is effectively
        one-shot: by the time anything calls ``close()`` again the group is
        empty, and an empty group's id is free to be handed to an unrelated
        process, which must never be signalled.
        """
        stop_process_tree(self.process, self.process_group)
        self.process_group = None

    def tail_logs(self, max_chars: int = 2000) -> str:
        chunks = []
        for stream in ("stdout", "stderr"):
            log = self.work_dir / f"nuke_{stream}.log"
            if log.exists():
                chunks.append(f"--- nuke {stream} (tail) ---\n{log.read_text()[-max_chars:]}")
        return "\n".join(chunks)


def launch_nuke_with_submitter(
    nuke_exe: Path,
    env: Mapping[str, str],
    work_dir: Path,
) -> NukeSession:
    """Start GUI Nuke, wait for the opener to open the submitter dialog.

    Returns an activated :class:`NukeSession`. Raises with Nuke's log tails
    on any startup failure.
    """
    Path(env[ENV_SCENE_FILE]).parent.mkdir(parents=True, exist_ok=True)
    stdout_log = (work_dir / "nuke_stdout.log").open("w")
    stderr_log = (work_dir / "nuke_stderr.log").open("w")
    try:
        process = subprocess.Popen(
            [str(nuke_exe)],
            env=dict(env),
            stdout=stdout_log,
            stderr=stderr_log,
            start_new_session=(sys.platform != "win32"),
        )
    finally:
        # The child holds duplicated descriptors; the parent's handles can
        # (and should) be closed regardless of whether Popen succeeded.
        stdout_log.close()
        stderr_log.close()
    # Resolve the process group now, while the child is known to be alive:
    # see capture_process_group.
    process_group = capture_process_group(process)
    session: Optional[NukeSession] = None
    try:
        app = find_accessibility_app(process.pid, timeout=NUKE_STARTUP_TIMEOUT)
        session = NukeSession(
            process=process,
            app=app,
            work_dir=work_dir,
            opener_status="",
            process_group=process_group,
        )

        status_file = Path(env[ENV_STATUS_FILE])
        deadline = time.monotonic() + OPENER_TIMEOUT
        while time.monotonic() < deadline and not status_file.exists():
            if process.poll() is not None:
                raise RuntimeError(
                    f"Nuke exited early (rc={process.returncode})\n{session.tail_logs()}"
                )
            time.sleep(0.5)
        if not status_file.exists():
            raise TimeoutError(
                f"Opener produced no status within {OPENER_TIMEOUT}s\n{session.tail_logs()}"
            )
        session.opener_status = status_file.read_text()
        if not session.opener_status.startswith("OK"):
            raise RuntimeError(
                f"Opener failed inside Nuke:\n{session.opener_status}\n{session.tail_logs()}"
            )
        session.activate()
        return session
    except BaseException:
        if session is not None:
            session.close()
        else:
            # Failed before the session existed (e.g. the AX bridge never
            # resolved). Nuke's children need stopping here too, or they
            # outlive the failure and break the next launch.
            stop_process_tree(process, process_group)
        raise
