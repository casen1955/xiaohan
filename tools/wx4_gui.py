"""4.x 微信窗口的截图/按图点击小工具（DPI 安全版）。
用法：
    python tools/wx4_gui.py shot out.png
    python tools/wx4_gui.py click 230 155      # 用截图里的坐标点
"""
import ctypes, sys, time

u = ctypes.windll.user32
try:
    u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

from app.adapters.wx4 import _find_wechat_hwnd

def rect(hwnd):
    r = (ctypes.c_long * 4)()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    return (r[0], r[1], r[2], r[3])

def shot(hwnd, path):
    from PIL import ImageGrab
    x1, y1, x2, y2 = rect(hwnd)
    u.ShowWindow(hwnd, 9)
    u.SetForegroundWindow(hwnd)
    time.sleep(0.35)
    img = ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
    img.save(path)
    return img.size

def click(x, y):
    u.SetCursorPos(int(x), int(y)); time.sleep(0.18)
    u.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.06)
    u.mouse_event(0x0004, 0, 0, 0, 0)

if __name__ == "__main__":
    hwnd = _find_wechat_hwnd()
    if not hwnd:
        print("找不到微信窗口"); sys.exit(1)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "shot"
    if cmd == "shot":
        out = sys.argv[2] if len(sys.argv) > 2 else "tools/wx4_shot.png"
        print("hwnd", hwnd, "rect", rect(hwnd), "size", shot(hwnd, out))
    elif cmd == "click":
        x, y = int(sys.argv[2]), int(sys.argv[3])
        x1, y1, _, _ = rect(hwnd)
        click(x1 + x, y1 + y)
        print("clicked", x1 + x, y1 + y)
