# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Launch GUI Nuke with the Deadline Cloud submitter for xa11y-driven tests.

Modeled on ``deadline-cloud`` ``test/blender_submitter_ui``. Launches Nuke
in the foreground with the repo's ``src`` and this suite's ``_opener`` dir
on ``NUKE_PATH``; the opener hook builds a scene and opens the submitter
dialog, which tests then drive through the platform accessibility tree.

Platform notes baked in from the macOS spike (2026-07-20):

* ``build_mock_environment`` redirects ``HOME``, which breaks Foundry
  licensing — the real ``HOME`` is restored and hermetic isolation relies
  on ``DEADLINE_CONFIG_FILE_PATH`` instead.
* Credential-sandbox variables (``AWS_SHARED_CREDENTIALS_FILE`` etc.) leak
  into Nuke and cause a login-error popup — they are scrubbed.
* The submitter is a ``Qt.Tool`` window: macOS drops it from the AX tree
  whenever Nuke is not the frontmost application, so activation is
  performed via ``NSRunningApplication`` and verified against
  ``xa11y.App.foreground()`` (which is a getter, not an activator).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import xa11y
from deadline_test_fixtures.deadline_mock import build_mock_environment
from deadline_test_fixtures.xa11y import find_accessibility_app

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENER_DIR = Path(__file__).resolve().parent / "_opener"

NUKE_STARTUP_TIMEOUT = 180.0  # GUI Nuke + license acquisition can be slow
OPENER_TIMEOUT = 120.0
ACTIVATE_TIMEOUT = 15.0

# Environment variables consumed by _opener/menu.py inside Nuke.
ENV_STATUS_FILE = "NUKE_SUBMITTER_UI_STATUS_FILE"
ENV_SCENE_FILE = "NUKE_SUBMITTER_UI_SCENE_FILE"
ENV_OPEN_DELAY_MS = "NUKE_SUBMITTER_UI_OPEN_DELAY_MS"

# Inherited AWS settings that would override the mock credentials or point
# at restricted files (e.g. agent credential sandboxes).
_SCRUBBED_ENV_VARS = ("AWS_CONFIG_FILE", "AWS_SHARED_CREDENTIALS_FILE", "AWS_PROFILE")


def find_nuke_executable() -> Path:
    """Locate the GUI Nuke executable (``NUKE_EXECUTABLE`` wins)."""
    override = os.environ.get("NUKE_EXECUTABLE")
    if override:
        path = Path(override)
        if path.exists():
            return path
        raise FileNotFoundError(f"NUKE_EXECUTABLE={override} does not exist")
    if sys.platform == "darwin":
        candidates = sorted(Path("/Applications").glob("Nuke*"), reverse=True)
        for install_dir in candidates:
            for binary in sorted(install_dir.glob("Nuke*.app/Contents/MacOS/Nuke[0-9]*.[0-9]*")):
                if binary.is_file() and os.access(binary, os.X_OK):
                    return binary
    elif sys.platform.startswith("linux"):
        for install_dir in sorted(Path("/usr/local").glob("Nuke*"), reverse=True):
            binary = install_dir / install_dir.name.replace("v", ".").split(".", 2)[0]
            matches = sorted(install_dir.glob("Nuke[0-9]*.[0-9]*"))
            if matches:
                return matches[0]
            if binary.exists():
                return binary
    raise FileNotFoundError(
        "No Nuke installation found. Set NUKE_EXECUTABLE to the GUI Nuke binary."
    )


def build_nuke_environment(
    *,
    deadline_endpoint_url: str,
    config_path: Path,
    work_dir: Path,
    open_delay_ms: int = 5000,
) -> dict[str, str]:
    """Hermetic environment for the Nuke subprocess pointed at the mock."""
    base_env = {k: v for k, v in os.environ.items() if k not in _SCRUBBED_ENV_VARS}
    env = build_mock_environment(
        base_env,
        deadline_endpoint_url=deadline_endpoint_url,
        config_path=config_path,
        home_dir=work_dir / "home",
    )
    # Foundry licensing and Nuke prefs live under the real HOME; hermetic
    # isolation is provided by DEADLINE_CONFIG_FILE_PATH + scrubbed vars.
    env["HOME"] = os.environ["HOME"]
    if "USERPROFILE" in os.environ:
        env["USERPROFILE"] = os.environ["USERPROFILE"]

    env["NUKE_PATH"] = f"{REPO_ROOT / 'src'}{os.pathsep}{OPENER_DIR}"
    env[ENV_STATUS_FILE] = str(work_dir / "opener_status.txt")
    env[ENV_SCENE_FILE] = str(work_dir / "scene" / "basic_workflow.nk")
    env[ENV_OPEN_DELAY_MS] = str(open_delay_ms)
    # Required for the AT-SPI bridge on Linux; harmless elsewhere.
    env["QT_ACCESSIBILITY"] = "1"
    env["QT_LINUX_ACCESSIBILITY_ALWAYS_ON"] = "1"
    (work_dir / "scene").mkdir(parents=True, exist_ok=True)
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

    def activate(self) -> bool:
        """(Re-)raise Nuke to the foreground; required before AX queries
        on macOS because Qt.Tool windows drop out of the tree otherwise."""
        return _activate_app(self.process.pid)

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

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
    process = subprocess.Popen(
        [str(nuke_exe)],
        env=dict(env),
        stdout=(work_dir / "nuke_stdout.log").open("w"),
        stderr=(work_dir / "nuke_stderr.log").open("w"),
        start_new_session=(sys.platform != "win32"),
    )
    session: Optional[NukeSession] = None
    try:
        app = find_accessibility_app(process.pid, timeout=NUKE_STARTUP_TIMEOUT)
        session = NukeSession(process=process, app=app, work_dir=work_dir, opener_status="")

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
        elif process.poll() is None:
            process.terminate()
        raise
