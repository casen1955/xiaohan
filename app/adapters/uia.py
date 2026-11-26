"""UI 自动化适配器（不注入微信，只靠 Windows 无障碍接口读写窗口）。

为什么用这个：
- WeChatFerry 的 spy 在这个微信版本上只开了命令通道，消息通道不工作；
- 注入 DLL 本身也有封号风险。

代价：发消息时需要把微信窗口提到前台（会短暂抢焦点），并且微信必须保持登录。

依赖：pip install uiautomation
"""

from __future__ import annotations

import ctypes
import re
import time

from .base import Adapter, Incoming

TIME_RE = re.compile(r"^(?:昨天|星期[一二三四五六日]|\d{1,2}月\d{1,2}日)?\s*\d{1,2}:\d{2}$")
UNREAD_RE = re.compile(r"(\d+)\s*条新消息$")
GROUP_UNREAD_RE = re.compile(r"[（(]\s*(\d+)\s*[）)]$")
SW_RESTORE = 9


class UiaAdapter(Adapter):
    name = "uia"

    def __init__(self, self_name: str = "小涵", poll_interval: float = 2.0,
                 chat_whitelist: list[str] | None = None):
        import uiautomation as auto

        self.auto = auto
        self.self_name = self_name
        self.poll_interval = poll_interval
        self.chat_whitelist = [w for w in (chat_whitelist or []) if w]
        self._last_text: dict[str, str] = {}
        self._win = None
        self._describe()

    # ---------- 窗口 ----------

    def _describe(self) -> None:
        auto = self.auto
        win = auto.WindowControl(searchDepth=1, ClassName="WeChatMainWndForPC")
        if not win.Exists(3, 1):
            raise RuntimeError(
                "没找到微信窗口（WeChatMainWndForPC）。请确认微信 3.9.x 已登录。"
            )
        if not win.Name:
            raise RuntimeError("微信窗口没标题，可能还没登录完")
        self._win = win

    def _win_fresh(self):
        auto = self.auto
        return auto.WindowControl(searchDepth=1, ClassName="WeChatMainWndForPC")

    def _activate(self) -> None:
        win = self._win
        try:
            ctypes.windll.user32.ShowWindow(win.NativeWindowHandle, SW_RESTORE)
        except Exception:  # noqa: BLE001
            pass
        try:
            win.SetActive()
        except Exception:  # noqa: BLE001
            try:
                win.SetFocus()
            except Exception:  # noqa: BLE001
                pass

    # ---------- 会话列表 ----------

    def _conversation_items(self):
        win = self._win_fresh()
        conv = win.ListControl(Name="会话")
        if not conv.Exists(2, 1):
            return []
        return conv.GetChildren()

    @staticmethod
    def _base_name(name: str) -> str:
        return GROUP_UNREAD_RE.sub("", UNREAD_RE.sub("", name or "")).strip()

    def _open_chat(self, chat_name: str) -> bool:
        win = self._win_fresh()
        conv = win.ListControl(Name="会话")
        if not conv.Exists(2, 1):
            return False
        for item in conv.GetChildren():
            if self._base_name(item.Name) == chat_name:
                try:
                    item.Click(simulateMove=False)
                except Exception:  # noqa: BLE001
                    return False
                time.sleep(0.6)
                return True
        return False

    # ---------- 消息读取 ----------

    def _message_items(self, chat_name: str):
        win = self._win_fresh()
        lst = win.ListControl(Name="消息")
        if not lst.Exists(2, 1):
            return []
        return lst.GetChildren()

    def _item_kind(self, item) -> tuple[str, str]:
        """返回 (kind, sender)。kind: in / out / time / other"""
        name = (item.Name or "").strip()
        sender = ""
        has_button = False
        for child in item.GetChildren():
            for sub in child.GetChildren():
                try:
                    if sub.ControlTypeName != "ButtonControl":
                        continue
                except Exception:  # noqa: BLE001
                    continue
                has_button = True
                sender = sender or (sub.Name or "")
        if has_button:
            if sender == self.self_name:
                return "out", self.self_name
            return "in", sender
        if TIME_RE.match(name):
            return "time", ""
        return "other", ""

    def _read_tail(self, chat_name: str) -> tuple[str, str, bool]:
        """读“最后一条自己发的消息之后的对方消息”。

        返回 (合并后的文本, 发送者名, 是否群聊)
        """
        items = self._message_items(chat_name)
        parsed = []
        for it in items:
            kind, sender = self._item_kind(it)
            parsed.append((kind, sender, (it.Name or "").strip()))

        last_out = -1
        for idx, (kind, _s, _t) in enumerate(parsed):
            if kind == "out":
                last_out = idx

        inbound = [(s, t) for kind, s, t in parsed[last_out + 1:] if kind == "in" and t]
        if not inbound:
            return "", "", False

        sender = inbound[-1][0]
        text = "\n".join(t for _s, t in inbound)
        is_group = bool(sender) and sender != chat_name
        return text, sender or chat_name, is_group

    # ---------- 收消息主循环 ----------

    def recv_loop(self, on_message, should_stop=lambda: False) -> None:
        self._activate()
        while not should_stop():
            try:
                handled = self._poll_once(on_message)
                if not handled:
                    time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                raise
            except Exception:  # noqa: BLE001
                time.sleep(self.poll_interval)

    def _poll_once(self, on_message) -> bool:
        items = self._conversation_items()
        target = None
        for item in items:
            name = item.Name or ""
            if not (UNREAD_RE.search(name) or GROUP_UNREAD_RE.search(name)):
                continue
            base = self._base_name(name)
            if self.chat_whitelist and base not in self.chat_whitelist:
                continue
            target = base
            break
        if not target:
            return False

        if not self._open_chat(target):
            return False
        text, sender, is_group = self._read_tail(target)
        if not text:
            return True
        if self._last_text.get(target) == text:
            return True
        self._last_text[target] = text

        on_message(Incoming(
            chat_id=target,
            chat_name=target,
            is_group=is_group,
            sender_id=sender,
            sender_name=sender,
            content=text,
            ts=time.time(),
            is_mentioned=is_group and (self.self_name in text),
            raw={},
        ))
        return True

    # ---------- 发送 ----------

    def _input_box(self, chat_name: str):
        win = self._win_fresh()
        best = None
        stack = [win]
        while stack:
            node = stack.pop()
            try:
                children = node.GetChildren()
            except Exception:  # noqa: BLE001
                continue
            for child in children:
                try:
                    if child.ControlTypeName == "EditControl" and child.Name != "搜索":
                        if child.Name == chat_name:
                            return child
                        if best is None:
                            best = child
                except Exception:  # noqa: BLE001
                    pass
                stack.append(child)
        return best

    def send_text(self, chat_id: str, text: str, is_group: bool) -> None:
        self._activate()
        if not self._open_chat(chat_id):
            raise RuntimeError(f"找不到会话：{chat_id}")
        edit = self._input_box(chat_id)
        if edit is None:
            raise RuntimeError("找不到输入框")
        edit.Click(simulateMove=False)
        time.sleep(0.15)
        self.auto.SetClipboardText(text)
        self.auto.SendKeys("{Ctrl}v", waitTime=0.05)
        time.sleep(0.15)
        self.auto.SendKeys("{Enter}", waitTime=0.05)
        time.sleep(0.2)

    def send_sticker(self, chat_id: str, bmp_path: str) -> None:
        """把 BMP 塞进剪贴板，切到会话里 Ctrl+V，再回车发出去。"""
        from ..stickers import set_clipboard_dib

        self._activate()
        if not self._open_chat(chat_id):
            raise RuntimeError(f"找不到会话：{chat_id}")
        edit = self._input_box(chat_id)
        if edit is not None:
            try:
                edit.Click(simulateMove=False)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.15)
        if not set_clipboard_dib(bmp_path):
            raise RuntimeError("写剪贴板失败")
        time.sleep(0.1)
        self.auto.SendKeys("{Ctrl}v", waitTime=0.05)
        time.sleep(1.0)
        self.auto.SendKeys("{Enter}", waitTime=0.05)
        time.sleep(0.4)

    def is_friend(self, wxid: str) -> bool:
        # 只回已经有会话的人；UIA 拿不到 wxid，用会话名当 id
        return True

    def close(self) -> None:
        return None
