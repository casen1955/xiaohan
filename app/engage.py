"""朋友圈点赞 / 评论。

微信 4.x 的朋友圈整页是自绘的（UIA 里只有一个空壳），所以这条路全靠坐标 + 截图比对：
1. 打开「发现 → 朋友圈」
2. 在右侧留白那一列上下扫，用「悬停前后截图的差异」找出那条动态的「…」按钮
3. 点它 → 弹出一个小窗（赞 / 评论），再按位置点
4. 评论则在内联输入框里打字回车

所有函数都不抛异常，失败只返回 False + 原因，绝不让主线程挂掉。
"""
from __future__ import annotations

import ctypes
import time

from PIL import Image

USER32 = ctypes.windll.user32
try:  # 拿到真实物理像素坐标
    USER32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:  # noqa: BLE001
    pass

POPUP_CLASS = "Qt51514QWindowToolSaveBits"


# ---------- 基础动作 ----------

def _rect(hwnd):
    r = (ctypes.c_long * 4)()
    USER32.GetWindowRect(hwnd, ctypes.byref(r))
    return r[0], r[1], r[2] - r[0], r[3] - r[1]


def _move(x, y):
    USER32.SetCursorPos(int(x), int(y))


def _click(x, y, wait=0.5):
    _move(x, y)
    time.sleep(0.18)
    USER32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.08)
    USER32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(wait)


def _wheel(x, y, times=5, delta=-120):
    _move(x, y)
    time.sleep(0.2)
    for _ in range(times):
        USER32.mouse_event(0x0800, 0, 0, delta, 0)
        time.sleep(0.06)


def _grab(hwnd):
    """抓窗口画面。窗口在前台时用屏幕像素（和点击坐标一一对应），否则用 PrintWindow。"""
    try:
        from PIL import ImageGrab
        if USER32.GetForegroundWindow() == hwnd:
            ox, oy, w, h = _rect(hwnd)
            if w > 200 and h > 200:
                return ImageGrab.grab(bbox=(ox, oy, ox + w, oy + h))
    except Exception as exc:  # noqa: BLE001
        print("[engage] 屏幕抓图失败:", exc, flush=True)
    try:
        import sys
        sys.path.insert(0, "tools")
        from tools.winshot import grab
        return grab(hwnd)
    except Exception as exc:  # noqa: BLE001
        print("[engage] PrintWindow 抓图失败:", exc, flush=True)
        return None


def _scan_dots(hwnd, ox, oy, w, h):
    """在右侧留白那一列里找「…」按钮（三个小点）。

    微信 4.x 那几个点是**蓝灰色**（实测约 rgb(87,107,149)）压在 #F2F2F2 的圆角底上，
    而正文文字是纯黑/深灰（r≈g≈b），所以按「偏蓝的灰」去找，误判率极低。
    """
    img = _grab(hwnd)
    if img is None:
        return []
    px = img.load()
    iw, ih = img.size
    raw = []
    for y in range(100, ih - 40):
        cnt = 0
        sx = 0
        for x in range(iw - 150, iw - 30):
            r, g, b = px[x, y][:3]
            if 55 <= r <= 135 and 70 <= g <= 155 and 130 <= b <= 205 and b - r >= 25:
                cnt += 1
                sx += x
        if cnt >= 4:
            cx = sx // cnt
            if not any(abs(cx - q[0]) < 40 and abs(y - q[1]) < 40 for q in raw):
                raw.append((cx, y))
    return [(ox + q[0], oy + q[1]) for q in raw]


def _green_at(img, fx, fy):
    """按比例取一个像素，看它是不是微信的选中绿（窗口大小变了也不怕）。"""
    w, h = img.size
    if w < 400 or h < 300:      # 最小化/没开好
        return False
    r, g, b = img.load()[int(w * fx), int(h * fy)]
    return g > 140 and r < 90 and b < 130


def _on_discover(hwnd) -> bool:
    """左侧导航「发现」是否被选中（选中的图标是绿色）。"""
    return _green_at(_grab(hwnd), 45 / 1347, 385 / 971)


def _moments_open(hwnd) -> bool:
    """朋友圈打开时左栏「朋友圈」那一行整条变绿。"""
    img = _grab(hwnd)
    return (_green_at(img, 0.10, 0.135) or _green_at(img, 0.30, 0.16))


def _activate(hwnd):
    """把微信拉到前台（前台锁定会让第一次点击被吞掉，所以要多管齐下）。"""
    USER32.ShowWindow(hwnd, 9)
    try:
        USER32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except Exception:  # noqa: BLE001
        pass
    try:
        USER32.SetForegroundWindow(hwnd)
    except Exception:  # noqa: BLE001
        pass
    try:
        USER32.SwitchToThisWindow(hwnd, True)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(0.7)


def open_moments(hwnd):
    """打开朋友圈：先确保在「发现」页，再点「朋友圈」。最多试四次。"""
    _activate(hwnd)          # 必须先还原窗口再取坐标，最小化时 rect 是 -32000
    ox, oy, w, h = _rect(hwnd)
    for _ in range(4):
        if _moments_open(hwnd):
            return True
        _activate(hwnd)
        if not _on_discover(hwnd):
            _click(ox + 45, oy + 385, wait=1.8)   # 左侧「发现」
            time.sleep(0.8)
            if not _on_discover(hwnd):
                continue
        _activate(hwnd)
        _click(ox + 180, oy + 155, wait=2.4)      # 「朋友圈」
        if _moments_open(hwnd):
            return True
        time.sleep(0.6)
    return False


def back_to_chat(hwnd):
    _activate(hwnd)
    ox, oy, _w, _h = _rect(hwnd)
    _click(ox + 45, oy + 168, wait=1.0)  # 左侧「微信」回到聊天


def _find_popup(timeout=2.5, main_hwnd=0):
    """找那个 赞/评论 的小弹窗，返回 (hwnd, rect) 或 (0, None)。

    它是个独立顶层窗口，类名随版本变（见过 Qt51514QWindowToolSaveBits），
    所以按「尺寸像菜单 + 不是主窗口」来认，不认死类名。
    """
    end = time.time() + timeout
    while time.time() < end:
        found = []

        CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(hh, _l):
            if not USER32.IsWindowVisible(hh):
                return True
            if main_hwnd and hh == main_hwnd:
                return True
            cn = ctypes.create_unicode_buffer(128)
            USER32.GetClassNameW(hh, cn, 128)
            cls = cn.value or ""
            if not (cls.startswith("Qt") or cls.startswith("mmui")):
                return True
            rr = _rect(hh)
            if 180 <= rr[2] <= 360 and 30 <= rr[3] <= 100:
                found.append((hh, rr))
            return True

        USER32.EnumWindows(CB(cb), 0)
        if found:
            # 菜单一般紧贴点击位置，取最靠下那个（离点击点最近）
            found.sort(key=lambda t: t[1][1], reverse=True)
            return found[0]
        time.sleep(0.15)
    return 0, None


def _pick_dots(hwnd, ox, oy, w, h):
    """往下滚一点，让别人的动态底栏露出来，再找「…」。"""
    for _ in range(3):
        hits = _scan_dots(hwnd, ox, oy, w, h)
        if hits:
            return hits[-1]
        _wheel(ox + w // 2, oy + h // 2, times=3, delta=-120)
        time.sleep(1.0)
    return None


def _escape():
    _key(0x1B)


def like_latest(hwnd, max_try=3):
    """给朋友圈里最近一条动态点赞。返回 (ok, 说明)。"""
    _activate(hwnd)
    ox, oy, w, h = _rect(hwnd)
    if not _moments_open(hwnd):
        return False, "朋友圈没打开"
    for _ in range(max_try):
        pos = _pick_dots(hwnd, ox, oy, w, h)
        if not pos:
            return False, "没找到可点开的动态"
        _click(pos[0], pos[1], wait=1.0)
        ph, pr = _find_popup(timeout=2.5, main_hwnd=hwnd)
        if not ph:
            _escape()
            time.sleep(0.4)
            continue
        if 230 <= pr[2] <= 320 and 35 <= pr[3] <= 80:
            _click(pr[0] + pr[2] * 0.25, pr[1] + pr[3] * 0.5, wait=1.2)
            return True, "已点赞"
        _escape()          # 不是赞/评论菜单（比如自己那条的删除），退掉
        time.sleep(0.5)
    return False, "没找到能点赞的动态"


def comment_latest(hwnd, text, max_try=3):
    """给最近一条动态留一句评论。"""
    _activate(hwnd)
    ox, oy, w, h = _rect(hwnd)
    if not _moments_open(hwnd):
        return False, "朋友圈没打开"
    for _ in range(max_try):
        pos = _pick_dots(hwnd, ox, oy, w, h)
        if not pos:
            return False, "没找到可点开的动态"
        _click(pos[0], pos[1], wait=1.0)
        ph, pr = _find_popup(timeout=2.5, main_hwnd=hwnd)
        if not ph:
            _escape()
            time.sleep(0.4)
            continue
        if not (230 <= pr[2] <= 320 and 35 <= pr[3] <= 80):
            _escape()
            time.sleep(0.5)
            continue
        _click(pr[0] + pr[2] * 0.75, pr[1] + pr[3] * 0.5, wait=1.2)
        time.sleep(0.6)
        if not _paste_text(text):
            return False, "打不了字"
        time.sleep(0.35)
        _key(0x0D)
        time.sleep(1.2)
        return True, "已评论"
    return False, "没找到能评论的动态"


def _paste_text(text: str) -> bool:
    """把文字塞进剪贴板再 Ctrl+V，比逐字敲可靠（中文也不怕）。"""
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception:  # noqa: BLE001
        return False
    _key(0x11, down=True)     # Ctrl
    _key(0x56)                # V
    _key(0x11, up=True)
    return True


def _key(code: int, down: bool = True, up: bool = True):
    if down:
        USER32.keybd_event(code, 0, 0, 0)
        time.sleep(0.03)
    if up:
        USER32.keybd_event(code, 0, 2, 0)
        time.sleep(0.03)
