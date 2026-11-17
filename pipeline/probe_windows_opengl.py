# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Probe a selected Windows OpenGL DLL using a hidden WGL window."""

import ctypes
import ctypes.wintypes as wintypes
import re


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
