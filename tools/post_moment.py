"""在微信 4.x 上发一条朋友圈（4.x PC 才有这个功能，3.9 没有）。

这是台「状态机」：每一轮先判断现在停在哪一步，再决定下一步做什么；
不对就 Esc 退回去重来，最多 MAX_ROUNDS 轮。

坐标证据（记下来免得下次再摸）：
- 左侧「发现」图标：窗口左上角偏移 (45, 385)；被选中时变微信绿。
- 发现页「朋友圈」那一行：(180, 155)；被选中时整行微信绿。
- 右上角相机：离窗口右边 130、离顶 84。
- 选完图后弹出的是**独立窗口** `mmui::SnsPublishPanel`（标题「朋友圈」），
  UIA 树可读：`mmui::ReplyTextView` 是输入框，`发表` / `取消` 是
  `mmui::XOutlineButton`。

用法：
    python tools/post_moment.py --image stickers/png/Mygo__探头.png --text "今天也在偷偷画画" --dry
    去掉 --dry 就真的发出去。
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time

import uiautomation as auto

sys.path.insert(0, ".")
sys.path.insert(0, "tools")

from app.adapters.wx4 import _find_wechat_hwnd  # noqa: E402

u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass

RAIL_DISCOVER = (45, 385)
RAIL_CHAT = (45, 168)
ROW_MOMENTS = (180, 155)
CAMERA_FROM_RIGHT = (130, 84)
MAX_ROUNDS = 4
PUBLISH_CLASS = "mmui::SnsPublishPanel"


def log(*a):
    print("[moment]", *a, flush=True)


def win_rect(hwnd):
    r = (ctypes.c_long * 4)()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return r[0], r[1], r[2], r[3]


def click(x, y, wait=0.45):
    u.SetCursorPos(int(x), int(y))
    time.sleep(0.18)
    u.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.07)
    u.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(wait)


def press(vk, up=False):
    u.keybd_event(vk, 0, 2 if up else 0, 0)


def tap(vk, wait=0.15):
    press(vk)
    time.sleep(0.06)
    press(vk, up=True)
    time.sleep(wait)


def top_windows():
    out = []
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        if u.IsWindowVisible(h):
            cn = ctypes.create_unicode_buffer(256)
            u.GetClassNameW(h, cn, 256)
            t = ctypes.create_unicode_buffer(256)
            u.GetWindowTextW(h, t, 256)
            out.append((h, cn.value, t.value, win_rect(h)))
        return True

    u.EnumWindows(CB(cb), 0)
    return out


def find_publish_panel(timeout=15.0, main_hwnd=0):
    """发表面板是独立顶层窗口：Win32 类名仍是 Qt51514QWindowIcon，
    但标题是「朋友圈」，UIA ClassName 才是 mmui::SnsPublishPanel。"""
    end = time.time() + timeout
    while time.time() < end:
        for h, cls, title, _r in top_windows():
            if h == main_hwnd:
                continue
            if cls.startswith("Qt") and title == "朋友圈":
                return h
        time.sleep(0.4)
    return 0


def find_dialog(timeout=12.0):
    end = time.time() + timeout
    while time.time() < end:
        for h, cls, title, _r in top_windows():
            if cls == "#32770" and ("选择" in title or "打开" in title):
                return h
        time.sleep(0.3)
    return 0


def set_clipboard(text: str) -> None:
    k32 = ctypes.windll.kernel32
    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13
    u.OpenClipboard(0)
    u.EmptyClipboard()
    buf = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(buf)
    h = k32.GlobalAlloc(GMEM_MOVEABLE, size)
    p = k32.GlobalLock(ctypes.c_void_p(h))
    ctypes.memmove(p, buf, size)
    k32.GlobalUnlock(ctypes.c_void_p(h))
    u.SetClipboardData(CF_UNICODETEXT, ctypes.c_void_p(h))
    u.CloseClipboard()


def paste(text: str) -> None:
    set_clipboard(text)
    time.sleep(0.25)
    press(0x11)
    press(0x56)
    time.sleep(0.06)
    press(0x56, up=True)
    press(0x11, up=True)
    time.sleep(0.3)


def is_green(rgb) -> bool:
    r, g, b = rgb
    return g > 140 and r < 130 and b < 160


def grab_main(hwnd):
    from winshot import grab

    return grab(hwnd)


def in_discover(img) -> bool:
    return is_green(img.getpixel(RAIL_DISCOVER))


def moments_open(hwnd) -> bool:
    img = grab_main(hwnd)
    if img is None:
        return False
    return in_discover(img) and is_green(img.getpixel(ROW_MOMENTS))


def bring_wechat_forward(hwnd) -> bool:
    u.ShowWindow(hwnd, 9)
    u.SetForegroundWindow(hwnd)
    try:
        u.SwitchToThisWindow(hwnd, True)
    except Exception:
        pass
    time.sleep(0.7)
    return u.GetForegroundWindow() == hwnd


def click_camera(hwnd, x1, y1, w) -> bool:
    cx, cy = x1 + w - CAMERA_FROM_RIGHT[0], y1 + CAMERA_FROM_RIGHT[1]
    for _ in range(3):
        click(cx, cy, wait=1.0)
        if find_dialog(timeout=4.0):
            return True
    return False


def pick_file(path: str) -> bool:
    dlg_h = find_dialog(timeout=8.0)
    if not dlg_h:
        log("没等到文件对话框")
        return False
    u.SetForegroundWindow(dlg_h)
    time.sleep(0.5)
    dlg = auto.ControlFromHandle(dlg_h)
    ed = None
    try:
        ed = dlg.ComboBoxControl().EditControl(searchDepth=4)
    except Exception:
        try:
            ed = dlg.EditControl(searchDepth=8)
        except Exception:
            ed = None
    filled = False
    if ed is not None:
        try:
            u.SendMessageW(ctypes.c_void_p(ed.NativeWindowHandle), 0x000C, 0,
                           ctypes.c_wchar_p(path))
            time.sleep(0.4)
            filled = True
        except Exception as exc:
            log("WM_SETTEXT 失败:", exc)
    if not filled:
        r = ed.BoundingRectangle
        click((r.left + r.right) // 2, (r.top + r.bottom) // 2, wait=0.4)
        paste(path)
        time.sleep(0.6)
    try:
        btn = dlg.SplitButtonControl(Name="打开(O)", searchDepth=4)
        r = btn.BoundingRectangle
        click((r.left + r.right) // 2, (r.top + r.bottom) // 2, wait=1.0)
        log("已点打开(O)")
        return True
    except Exception as exc:
        log("找不到打开按钮，用回车:", exc)
    u.SetForegroundWindow(dlg_h)
    tap(0x0D)
    return True


def fill_text(panel, text: str) -> bool:
    if not text:
        return True
    try:
        box = panel.GroupControl(ClassName="mmui::ReplyTextView", searchDepth=8)
        r = box.BoundingRectangle
    except Exception:
        return False
    click((r.left + r.right) // 2, (r.top + r.bottom) // 3, wait=0.5)
    paste(text)
    time.sleep(0.6)
    return True


def publish(panel) -> bool:
    for name in ("发表", "发表 "):
        try:
            btn = panel.ButtonControl(Name=name, searchDepth=6)
            if btn.Exists(1.0):
                r = btn.BoundingRectangle
                click((r.left + r.right) // 2, (r.top + r.bottom) // 2, wait=1.5)
                log("已点发表")
                return True
        except Exception:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    hwnd = _find_wechat_hwnd()
    if not hwnd:
        log("找不到微信窗口")
        return 1
    bring_wechat_forward(hwnd)
    x1, y1, x2, y2 = win_rect(hwnd)
    w, h = x2 - x1, y2 - y1
    log("窗口", (x1, y1, w, h))

    panel_h = 0
    for rnd in range(1, MAX_ROUNDS + 1):
        log(f"--- 第 {rnd} 轮 ---")
        bring_wechat_forward(hwnd)
        if not moments_open(hwnd):
            click(x1 + RAIL_DISCOVER[0], y1 + RAIL_DISCOVER[1], wait=1.8)
            for _ in range(3):
                if moments_open(hwnd):
                    break
                click(x1 + ROW_MOMENTS[0], y1 + ROW_MOMENTS[1], wait=0.8)
                time.sleep(0.6)
            if not moments_open(hwnd):
                log("朋友圈视图没打开，退回聊天重来")
                click(x1 + RAIL_CHAT[0], y1 + RAIL_CHAT[1], wait=0.8)
                continue
        log("朋友圈视图已打开")
        if click_camera(hwnd, x1, y1, w):
            pick_file(args.image)
            panel_h = find_publish_panel(timeout=15.0, main_hwnd=hwnd)
            if panel_h:
                break
            log("选完没看到发表面板")
        tap(0x1B)
        time.sleep(1.0)
    if not panel_h:
        log("没走到发表面板")
        return 2

    panel = auto.ControlFromHandle(panel_h)
    log("发表面板", panel_h, panel.BoundingRectangle)
    fill_text(panel, args.text)
    from winshot import grab

    shot = grab(panel_h)
    if shot is not None:
        shot.save("tools/moment_compose.png")
    if args.dry:
        log("--dry：只到编辑窗，不发表")
        return 0
    if not publish(panel):
        log("没找到发表按钮")
        return 3
    time.sleep(3.0)
    if find_publish_panel(timeout=2.0, main_hwnd=hwnd):
        log("面板还在，可能没发出去")
        return 4
    log("发表完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
