"""WeChatFerry 适配器（微信 3.9.12.17）。

依赖：pip install wcferry
风险：微信版本不匹配会注入失败；登录必须扫码。
"""

from __future__ import annotations

import time

from .base import Adapter, Incoming


class WcfAdapter(Adapter):
    name = "wcf"

    def __init__(self, self_name: str = "具小涵"):
        from wcferry import Wcf  # 延迟导入，mock 模式不需要

        self.self_name = self_name
        self.wcf = Wcf()
        self.self_wxid = self.wcf.get_self_wxid()
        self._friends: dict[str, str] = {}
        try:
            for c in self.wcf.get_contacts():
                self._friends[c.get("wxid", "")] = c.get("remark") or c.get("name") or ""
        except Exception:  # noqa: BLE001
            pass
        self.wcf.enable_receiving_msg()

    # ---------- 发送 ----------

    def send_text(self, chat_id: str, text: str, is_group: bool) -> None:
        self.wcf.send_text(text, chat_id)

    def is_friend(self, wxid: str) -> bool:
        # 联系人还没同步到时先放行私聊回复（她只回别人发来的，不会主动找人）
        if not self._friends:
            return True
        return wxid in self._friends or wxid in {"filehelper", "weixin"}

    def friend_name(self, wxid: str) -> str:
        return self._friends.get(wxid, wxid)

    # ---------- 接收 ----------

    def recv_loop(self, on_message, should_stop=lambda: False):
        while not should_stop() and self.wcf.is_receiving_msg():
            try:
                msg = self.wcf.get_msg()
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
                continue
            if msg is None:
                continue
            if getattr(msg, "is_self", None) and msg.is_self():
                continue
            if not (getattr(msg, "is_text", None) and msg.is_text()):
                continue
            content = (msg.content or "").strip()
            if not content:
                continue

            is_group = bool(getattr(msg, "roomid", ""))
            chat_id = msg.roomid if is_group else msg.sender
            if is_group:
                # 群消息内容形如 "wxid_xxx:\n正文"
                if ":\n" in content:
                    _, content = content.split(":\n", 1)
                elif "\n" in content:
                    content = content.split("\n", 1)[1]
            mentioned = ("@" + self.self_name) in content or (
                getattr(msg, "is_at", None) and msg.is_at(self.self_wxid)
            )
            content = content.replace("@" + self.self_name, "").strip()

            sender_name = self.friend_name(msg.sender)
            chat_name = sender_name
            if is_group:
                try:
                    chat_name = self.wcf.get_room_name(chat_id) or chat_id
                except Exception:  # noqa: BLE001
                    chat_name = chat_id

            on_message(Incoming(
                chat_id=chat_id, chat_name=chat_name or chat_id, is_group=is_group,
                sender_id=msg.sender, sender_name=sender_name,
                content=content, ts=time.time(), is_mentioned=bool(mentioned),
                raw={"id": msg.id, "type": msg.type},
            ))

    def close(self) -> None:
        try:
            self.wcf.cleanup()
        except Exception:  # noqa: BLE001
            pass
