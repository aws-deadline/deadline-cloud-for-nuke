# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Nuke-side opener hook for the xa11y submitter UI tests.

DO NOT CHANGE THIS FILE's NAME — Nuke executes ``menu.py`` from every
directory on ``NUKE_PATH`` at GUI startup. The test launcher puts this
suite's ``_opener`` directory on ``NUKE_PATH`` alongside the repo's
``src`` (which registers the real submitter menu).

Responsibilities (driven by NUKE_SUBMITTER_UI_* env vars; inert without
them, so a developer launching Nuke by hand is unaffected):

1. Patch ``botocore.awsrequest._urljoin`` to drop the ``management.``
   host prefix so Deadline API calls reach the loopback mock server
   (mirrors ``deadline-cloud`` ``test/ui`` sitecustomize).
2. After the Qt event loop starts: execute the per-case scene script
   (NUKE_SUBMITTER_UI_SCENE_SCRIPT), which builds the case's scene and
   saves it to NUKE_SUBMITTER_UI_SCENE_FILE (the submitter refuses
   unsaved scripts), suppress the update-available dialog, and open the
   render submitter — the same code path as the AWS Deadline menu item.
3. Report success/failure to a status file polled by the launcher.
"""

# Deliberately no type hints or typing imports: this file executes inside
# whichever Python ships with the Nuke on NUKE_PATH, so it stays as plain
# and dependency-free as the repo's own src/menu.py.
import os
import traceback

_STATUS_FILE = os.environ.get("NUKE_SUBMITTER_UI_STATUS_FILE", "")
_SCENE_FILE = os.environ.get("NUKE_SUBMITTER_UI_SCENE_FILE", "")
_SCENE_SCRIPT = os.environ.get("NUKE_SUBMITTER_UI_SCENE_SCRIPT", "")
try:
    _DELAY_MS = int(os.environ.get("NUKE_SUBMITTER_UI_OPEN_DELAY_MS", "5000"))
except ValueError:
    # Never break Nuke startup over a malformed env var (module contract).
    _DELAY_MS = 5000  # keep in sync with open_delay_ms default in _launcher.py


def _write_status(text):
    if _STATUS_FILE:
        with open(_STATUS_FILE, "w") as f:
            f.write(text)


def _patch_botocore_host_prefix():
    """Route ``management.``-prefixed Deadline calls straight to the
    configured (loopback) endpoint."""
    import botocore.awsrequest as awsrequest

    original_urljoin = awsrequest._urljoin

    def _urljoin(endpoint_url, url_path, _host_prefix):
        # _host_prefix is deliberately dropped: that's the whole patch.
        return original_urljoin(endpoint_url, url_path, None)

    awsrequest._urljoin = _urljoin


def _open_submitter():
    try:
        import nuke

        # Execute the case's scene script inside this GUI session (no extra
        # license seat, unlike a separate `nuke -t` build step). Contract:
        # the script reads NUKE_SUBMITTER_UI_SCENE_FILE from the environment,
        # builds the scene, and saves it there via nuke.scriptSaveAs.
        with open(_SCENE_SCRIPT) as script_file:
            code = compile(script_file.read(), _SCENE_SCRIPT, "exec")
        exec(code, {"__name__": "__main__", "__file__": _SCENE_SCRIPT})
        if not os.path.isfile(_SCENE_FILE):
            raise RuntimeError(
                "scene script %r did not save a scene at %r" % (_SCENE_SCRIPT, _SCENE_FILE)
            )

        # The update-available dialog would block the submitter dialog.
        # Private API: if _session_state/update_dismissed is renamed this
        # raises AttributeError, which surfaces loudly via the status file.
        from deadline.nuke_submitter import update_utils

        update_utils._session_state.update_dismissed = True

        from deadline.nuke_submitter import JobType, show_nuke_render_submitter
        from PySide6.QtCore import qVersion

        dialog = show_nuke_render_submitter(JobType.RENDER)
        _write_status(
            "OK\n"
            f"qt_runtime={qVersion()}\n"
            f"nuke_version={nuke.env.get('NukeVersionString')}\n"
            f"dialog={'opened' if dialog is not None else 'None'}\n"
        )
    except Exception:
        # Report the failure to the launcher instead of leaving it to time
        # out; the status file is the only channel out of the Nuke process.
        _write_status("ERROR\n" + traceback.format_exc())


try:
    import nuke

    if nuke.env.get("gui") and _STATUS_FILE and _SCENE_FILE and _SCENE_SCRIPT:
        _patch_botocore_host_prefix()

        from PySide6.QtCore import QTimer

        QTimer.singleShot(_DELAY_MS, _open_submitter)
except BaseException:
    # Broad by design, mirroring this repo's src/menu.py: a menu.py hook
    # must never break Nuke's startup, and any failure still needs to be
    # reported to the launcher through the status file.
    _write_status("ERROR (menu.py top level)\n" + traceback.format_exc())
