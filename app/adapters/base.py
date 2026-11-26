"""微信接入层。每种接入方式一个适配器，大脑不关心是哪一种。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Incoming:
    chat_id: str
    chat_name: str
    is_group: bool
    sender_id: str
    sender_name: str
    content: str
    ts: float = field(default_factory=time.time)
    is_mentioned: bool = False
    raw: dict = field(default_factory=dict)


class Adapter:
    name = "base"

    def send_text(self, chat_id: str, text: str, is_group: bool) -> None:
        raise NotImplementedError

    def is_friend(self, wxid: str) -> bool:
        """只跟已经是好友的人说话。默认 True，具体适配器应覆盖。"""
        return True

    def close(self) -> None:
        return None
