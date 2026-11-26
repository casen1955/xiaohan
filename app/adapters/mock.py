"""mock 适配器：不开微信，直接在终端里跟她聊。用于调人设。"""

from __future__ import annotations

import sys
import time

from .base import Adapter, Incoming


class MockAdapter(Adapter):
    name = "mock"

    def __init__(self, self_name: str = "具小涵"):
        self.self_name = self_name

    def send_text(self, chat_id: str, text: str, is_group: bool) -> None:
        print(f"\n{self.self_name}：{text}\n")

    def read_line(self) -> str:
        try:
            line = input("你：").strip()
        except EOFError:
            return "/quit"
        return line


def run_mock(brain, memory, *, contact_name: str = "哥", contact_id: str = "mock-ge"):
    """终端里跟她说说话。输入 /quit 退出，/group 切群聊。"""
    adapter = MockAdapter()
    is_group = False
    group_name = "测试群"
    peers = ["阿泽", "小鹿"]
    chat_id = "mock:private" if not is_group else "mock:group:1"

    print("=" * 46)
    print("  mock 模式：只有她的大脑在跑，不连微信")
    print("  /quit 退出   /group 切群聊   /private 切私聊")
    print("=" * 46)

    while True:
        line = adapter.read_line()
        if not line:
            continue
        if line == "/quit":
            break
        if line == "/group":
            is_group, group_name = True, "测试群"
            chat_id = "mock:group:1"
            print("[已切到群聊，直接说话会被当成群里有人发言]")
            continue
        if line == "/private":
            is_group, group_name = False, ""
            chat_id = "mock:private"
            print("[已切回私聊]")
            continue

        now = time.time()
        sender_name = contact_name
        is_mentioned = False
        text = line
        if is_group and "：" in line:
            sender_name, text = line.split("：", 1)
        if is_group and ("@" + "小涵" in text):
            is_mentioned = True

        memory.add_message(chat_id, chat_name=contact_name if not is_group else group_name,
                           is_group=is_group, sender_id="mock", sender_name=sender_name,
                           role="user", content=text, ts=now)
        replies = brain.respond(
            chat_id=chat_id,
            chat_name=contact_name if not is_group else group_name,
            is_group=is_group, group_name=group_name,
            peers=peers if is_group else [],
            contact_wxid=None if is_group else contact_id,
            user_name=sender_name, text=text, is_mentioned=is_mentioned, now=now,
        )
        if not replies:
            print("（她没说话）")
            continue
        for i, part in enumerate(replies):
            if i:
                time.sleep(0.6)
            adapter.send_text(chat_id, part, is_group)
            memory.add_message(chat_id, chat_name=contact_name if not is_group else group_name,
                               is_group=is_group, sender_id="self", sender_name="具小涵",
                               role="assistant", content=part, ts=time.time())
