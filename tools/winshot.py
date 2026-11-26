"""按窗口抓图（PrintWindow），不依赖窗口是否在最前面。

被别的窗口挡住也能抓到自己的画面，这是判断「朋友圈有没有打开」的前提。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_u = ctypes.windll.user32
_g = ctypes.windll.gdi32

_u.GetWindowDC.restype = wintypes.HDC
_u.GetWindowDC.argtypes = [wintypes.HWND]
_u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
_u.PrintWindow.restype = wintypes.BOOL
_u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]

_g.CreateCompatibleDC.argtypes = [wintypes.HDC]
_g.CreateCompatibleDC.restype = wintypes.HDC
_g.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
_g.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_g.SelectObject.argtypes = [wintypes.HDC, wintypes.HBITMAP]
_g.SelectObject.restype = wintypes.HGDIOBJ
_g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_g.DeleteDC.argtypes = [wintypes.HDC]


class _BMPHDR(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


_g.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
]


def grab(hwnd: int):
    """返回 PIL.Image；失败返回 None。"""
    from PIL import Image

    r = wintypes.RECT()
    _u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return None

    hdc = _u.GetWindowDC(hwnd)
    mem = _g.CreateCompatibleDC(hdc)
    bmp = _g.CreateCompatibleBitmap(hdc, w, h)
    _g.SelectObject(mem, bmp)

    _u.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT

    bi = _BMPHDR()
    bi.biSize = ctypes.sizeof(_BMPHDR)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0

    buf = ctypes.create_string_buffer(w * h * 4)
    _g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)

    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")

    _g.DeleteObject(bmp)
    _g.DeleteDC(mem)
    _u.ReleaseDC(hwnd, hdc)
    return img
