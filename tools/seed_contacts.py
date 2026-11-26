"""登记好友：会话名 → 她该怎么称呼 + 能不能主动找。

用会话备注名当 wxid（UIA 拿不到 wxid，会话名就是唯一标识，稳定够用）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.memory import Memory  # noqa: E402

DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "xiaohan.db"
)

# (会话名, 该叫对方什么, 关系, 能否主动)
PEOPLE = [
    ("哥哥", "哥", "亲哥，唯一知道她全部的人", 1),
    ("爸爸", "爸爸", "父亲，保守传统，不能让他知道二次元的爱好", 1),
    ("妈妈", "妈妈", "母亲，同父亲", 1),
    ("韩硕", "函数哥哥", "哥的朋友", 1),
    ("郑博", "整波哥哥", "哥的朋友", 1),
    ("刘轩呈", "轩呈哥哥", "哥的朋友", 1),
    ("刘俊铭", "俊铭哥哥", "哥的朋友", 1),
    ("胥岩", "xy哥哥", "哥的朋友，不太熟", 0),
    ("李若嘉", "若嘉哥哥", "哥的朋友，不太熟", 0),
]


def main() -> None:
    memory = Memory(DB)
    for chat_name, how, relation, proactive in PEOPLE:
        memory.upsert_contact(
            chat_name,
            name=chat_name,
            relation=relation,
            note=f"当面称呼：「{how}」",
            proactive_enabled=proactive,
        )
    for row in memory.contacts():
        print(f"{row['name']:<6} 称呼={row['note']}  主动={row['proactive_enabled']}")


if __name__ == "__main__":
    main()
