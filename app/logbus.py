"""日志：内存环（给管理页看）+ 落盘（给无人值守时排查用）。"""

from __future__ import annotations

import collections
import os
import threading
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE, "data")
LOG_FILE = os.path.join(LOG_DIR, "xiaohan.log")
MAX_BYTES = 5 * 1024 * 1024

_BUFFER: collections.deque = collections.deque(maxlen=500)
_LOCK = threading.Lock()


def _write_file(line: str) -> None:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_BYTES:
            os.replace(LOG_FILE, LOG_FILE + ".1")
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def log(msg: str) -> None:
    line = f"{time.strftime('%m-%d %H:%M:%S')} {msg}"
    with _LOCK:
        _BUFFER.append(line)
    _write_file(line)
    try:
        print(line, flush=True)
    except Exception:  # noqa: BLE001  pythonw 下没有 stdout
        pass


def tail(n: int = 100) -> list[str]:
    with _LOCK:
        return list(_BUFFER)[-n:]
