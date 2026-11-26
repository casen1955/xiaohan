"""wxhelper 适配器（微信 3.9.5.81 等，DLL 注入后本地 HTTP 服务，默认 127.0.0.1:19088）。

接口路径随 wxhelper 版本变化，先跑 probe() 看哪些能用，再改 API_PATH。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .base import Adapter, Incoming


class WxHelperAdapter(Adapter):
    name = "wxhelper"

    # 如果某个版本路径不同，只改这里
    PATHS = {
        "pop": "/api/msg/pop",
        "send_text": "/api/sendTextMsg",
        "contacts": "/api/getContactList",
    }

    def __init__(self, base: str = "http://127.0.0.1:19088", self_wxid: str = ""):
        self.base = base.rstrip("/")
        self.self_wxid = self_wxid
        self._friends: dict[str, str] = {}

    # ---------- HTTP ----------

    def _post(self, path: str, payload: dict | None = None, timeout: float = 15.0):
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.base + path, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def probe(self) -> dict:
        out = {}
        for name, path in self.PATHS.items():
            try:
                payload = {"wxid": self.self_wxid, "msg": "probe"} if name == "send_text" else {}
                out[name] = self._post(path, payload, timeout=5)
            except urllib.error.HTTPError as exc:
                out[name] = f"HTTP {exc.code}"
            except Exception as exc:  # noqa: BLE001
                out[name] = f"{type(exc).__name__}: {exc}"
        return out

    # ---------- 发送 ----------

    def send_text(self, chat_id: str, text: str, is_group: bool) -> None:
        self._post(self.PATHS["send_text"], {"wxid": chat_id, "msg": text})

    def is_friend(self, wxid: str) -> bool:
        return wxid in self._friends

    def friend_name(self, wxid: str) -> str:
        return self._friends.get(wxid, wxid)

    def reload_contacts(self) -> None:
        try:
            data = self._post(self.PATHS["contacts"], {})
            for c in data.get("data", []) or []:
                wxid = c.get("wxid") or c.get("userName") or ""
                if wxid:
                    self._friends[wxid] = c.get("remark") or c.get("nickName") or wxid
        except Exception:  # noqa: BLE001
            pass

    # ---------- 接收 ----------

    def recv_loop(self, on_message, should_stop=lambda: False):
        while not should_stop():
            try:
                data = self._post(self.PATHS["pop"], {})
            except Exception:  # noqa: BLE001
                time.sleep(1.0)
                continue
            for item in (data.get("data") or []):
                msg = self._to_incoming(item)
                if msg is not None:
                    on_message(msg)
            time.sleep(0.4)

    def _to_incoming(self, item: dict) -> Incoming | None:
        if item.get("msgType") not in (1, "1"):
            return None
        content = (item.get("msg") or "").strip()
        if not content:
            return None
        roomid = item.get("roomId") or item.get("roomid") or ""
        is_group = bool(roomid)
        sender = item.get("sender") or item.get("wxid") or ""
        if is_group and ":\n" in content:
            _, content = content.split(":\n", 1)
        mentioned = ("@" + "小涵") in content
        return Incoming(
            chat_id=roomid or sender,
            chat_name=roomid or self.friend_name(sender),
            is_group=is_group,
            sender_id=sender,
            sender_name=self.friend_name(sender),
            content=content.replace("@小涵", "").strip(),
            ts=float(item.get("msgTime") or time.time()),
            is_mentioned=mentioned,
            raw=item,
        )
