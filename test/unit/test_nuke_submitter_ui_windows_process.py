# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Exercise Job Object teardown on a real Windows orphan, without a DCC."""

from __future__ import annotations

import ctypes
import importlib.util
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Objects")

_MODULE_PATH = Path(__file__).resolve().parents[1] / "nuke_submitter_ui" / "_windows_process.py"


def test_job_close_stops_descendant_after_root_exit(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("nuke_ui_windows_process", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    kernel32 = getattr(ctypes, "WinDLL")("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    gate, child_pid_file = tmp_path / "start", tmp_path / "child.pid"
    # Hold the parent until assignment, then leave a long-lived child behind.
    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess,sys,time; from pathlib import Path\n"
            "while not Path(sys.argv[1]).exists(): time.sleep(0.02)\n"
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
            "Path(sys.argv[2]).write_text(str(child.pid))\n",
            str(gate),
            str(child_pid_file),
        ]
    )
    job = None
    child_handle = None
    try:
        job = module.WindowsProcessJob(parent)
        gate.touch()
        assert parent.wait(timeout=10) == 0
        child_pid = int(child_pid_file.read_text())
        # Keep a handle to this particular child, so even failure cleanup cannot
        # kill an unrelated process that later reuses its PID.
        child_handle = kernel32.OpenProcess(0x100000 | 0x1000 | 0x0001, False, child_pid)
        assert child_handle
        assert kernel32.WaitForSingleObject(child_handle, 0) == 258  # WAIT_TIMEOUT: alive
        job.close()
        assert kernel32.WaitForSingleObject(child_handle, 10000) == 0  # WAIT_OBJECT_0: exited
        job.close()  # Repeated GUI teardown must not close a recycled handle.
    finally:
        if job is not None:
            job.close()
        if child_handle:
            if kernel32.WaitForSingleObject(child_handle, 0) == 258:
                kernel32.TerminateProcess(child_handle, 1)
            kernel32.CloseHandle(child_handle)
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=10)
