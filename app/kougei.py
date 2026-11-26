"""雷霆抽象话。

规则（用户定的，百分百照做）：
碰到由「雷 霆 刚 阴 舒 骚 嫩 爽 塞 猪」里任意两个字组成的词，
就用其中任意两字另组一个新词，套下面两个公式之一：

    「（他说那个词）是啥（新词）词」
    「我了（他说那个词）」

这是纯机械的接梗，不过大脑，所以直接在这层做，保证一次不漏。
"""

from __future__ import annotations

import random

CHARS = "雷霆刚阴舒骚嫩爽塞猪"
CHAR_SET = set(CHARS)

# 这些词本身太容易误伤日常对话（比如"刚"常出现在"刚才"），
# 但规则是百分百，所以只在「两个字都是套装里的字」且长度恰好的词上触发。
MIN_LEN = 2


def find_word(text: str) -> str | None:
    """从一句话里找出第一个「两字都由套装字组成」的词。"""
    s = (text or "").strip()
    if not s:
        return None
    # 先把标点、空白、表情切掉，避免跨标点凑词
    buf: list[str] = []
    best: str | None = None
    for ch in s:
        if ch in CHAR_SET:
            buf.append(ch)
            if len(buf) >= MIN_LEN and best is None:
                best = buf[0] + buf[1]
                # 继续攒，优先取更长的整词起点
                if len(buf) > 2:
                    best = "".join(buf[-2:])
        else:
            buf = []
    return best


def new_word(avoid: str) -> str:
    """另组一个新词（两个字，且不是他说的那个）。"""
    for _ in range(30):
        a, b = random.sample(CHARS, 2)
        cand = a + b
        if cand != avoid:
            return cand
    return "雷霆" if avoid != "雷霆" else "阴雷"


def make_reply(word: str) -> str:
    """按两个公式吐一句。"""
    if random.random() < 0.55:
        return f"{word}是啥{new_word(word)}词"
    return f"我了{word}"
