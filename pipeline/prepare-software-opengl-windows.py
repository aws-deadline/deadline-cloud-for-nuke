# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Prepare and probe a pinned Qt software OpenGL DLL in CI temporary storage.

Extract only opengl32sw.dll; do not install PySide or overwrite Nuke libraries.
The package/hash are from the official PySide6 6.5.3 PyPI release, matching
Nuke 17.1v2's verified Qt runtime. Qt's dynamic OpenGL loader accepts this
absolute path through QT_OPENGL_DLL.
"""

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request
import zipfile

WHEEL_URL = (
    "https://files.pythonhosted.org/packages/06/25/"
    "24216f5b7cf59bb2a768a63586b4a49553ace48c3e9f18441eff55d2d658/"
    "PySide6_Essentials-6.5.3-cp37-abi3-win_amd64.whl"
)
WHEEL_SHA256 = "f928b98ec349c87f9ccc63a482917779f59fa646893722c53c2fe2a1e4f335e0"
DLL_SHA256 = "c122715b191421e6c32d79309bdc07386680129e3aa7354c7f31c46bc85baab7"


def probe(dll_path):
    """Create a hidden WGL window and report the selected DLL's GL implementation."""
    user = ctypes.WinDLL("user32", use_last_error=True)
    gl = ctypes.WinDLL(str(dll_path), use_last_error=True)
    user.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        ctypes.c_void_p,
    ]
    user.CreateWindowExW.restype = wintypes.HWND
    user.GetDC.argtypes = [wintypes.HWND]
    user.GetDC.restype = wintypes.HDC
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user.DestroyWindow.argtypes = [wintypes.HWND]
    gl.wglChoosePixelFormat.argtypes = [wintypes.HDC, ctypes.c_void_p]
    gl.wglChoosePixelFormat.restype = ctypes.c_int
    gl.wglSetPixelFormat.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_void_p]
    gl.wglSetPixelFormat.restype = wintypes.BOOL
    gl.wglCreateContext.argtypes = [wintypes.HDC]
    gl.wglCreateContext.restype = wintypes.HANDLE
    gl.wglMakeCurrent.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gl.wglMakeCurrent.restype = wintypes.BOOL
    gl.wglDeleteContext.argtypes = [wintypes.HANDLE]
    gl.glGetString.argtypes = [ctypes.c_uint]
    gl.glGetString.restype = ctypes.c_char_p
    # PIXELFORMATDESCRIPTOR is 40 bytes: size/version, flags, RGBA/color bits,
    # depth/stencil bits. The rest are zero-initialized (main layer).
    descriptor = ctypes.create_string_buffer(40)
    import struct

    struct.pack_into("<HHI", descriptor, 0, 40, 1, 0x25)
    descriptor[8] = bytes([0])  # PFD_TYPE_RGBA
    descriptor[9] = bytes([32])
    descriptor[23] = bytes([24])  # depth bits
    descriptor[24] = bytes([8])  # stencil bits
    window = user.CreateWindowExW(
        0,
        "STATIC",
        "Nuke software OpenGL probe",
        0x80000000,
        0,
        0,
        1,
        1,
        None,
        None,
        None,
        None,
    )
    dc = context = None
    try:
        if not window:
            raise ctypes.WinError(ctypes.get_last_error())
        dc = user.GetDC(window)
        if not dc:
            raise RuntimeError("The hidden probe window has no device context")
        pixel_format = gl.wglChoosePixelFormat(dc, descriptor)
        if not pixel_format or not gl.wglSetPixelFormat(dc, pixel_format, descriptor):
            raise RuntimeError("Software OpenGL pixel format setup failed")
        context = gl.wglCreateContext(dc)
        if not context or not gl.wglMakeCurrent(dc, context):
            raise RuntimeError("Software OpenGL context creation failed")
        result = {}
        for name, enum in (("vendor", 0x1F00), ("renderer", 0x1F01), ("version", 0x1F02)):
            result[name] = (gl.glGetString(enum) or b"").decode("utf-8", "replace")
        version = re.match(r"(\d+)\.(\d+)", result["version"])
        if not version or tuple(map(int, version.groups())) < (2, 1):
            raise RuntimeError(f"Software OpenGL version is insufficient: {result}")
        return result
    finally:
        if context:
            gl.wglMakeCurrent(None, None)
            gl.wglDeleteContext(context)
        if dc:
            user.ReleaseDC(window, dc)
        if window:
            user.DestroyWindow(window)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--github-env", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("This trial requires 64-bit Windows Python")
    root = args.directory.resolve()
    root.mkdir(exist_ok=False, parents=True)
    manifest = {"wheel_url": WHEEL_URL, "wheel_sha256": WHEEL_SHA256, "dll_sha256": DLL_SHA256}
    try:
        wheel = root / "qt-software-opengl.whl"
        urllib.request.urlretrieve(WHEEL_URL, wheel)
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != WHEEL_SHA256:
            raise RuntimeError("Qt wheel SHA-256 mismatch")
        with zipfile.ZipFile(wheel) as archive:
            data = archive.read("PySide6/opengl32sw.dll")
        if hashlib.sha256(data).hexdigest() != DLL_SHA256:
            raise RuntimeError("Software OpenGL DLL SHA-256 mismatch")
        dll_path = root / "opengl32sw.dll"
        dll_path.write_bytes(data)
        wheel.unlink()
        manifest["dll_path"] = str(dll_path)
        manifest["opengl"] = probe(dll_path)
        with args.github_env.open("a", encoding="utf-8") as env:
            env.write(
                f"QT_OPENGL=software\nQT_OPENGL_DLL={dll_path}\nQT_LOGGING_RULES=qt.qpa.gl=true\n"
            )
    except Exception as error:
        manifest["error"] = str(error)
        raise
    finally:
        (root / "probe.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
