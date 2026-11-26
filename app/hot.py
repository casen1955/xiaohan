"""网上现在在聊什么 —— 给她一点"我刷到过"的底气。

数据源用百度热搜榜（不需要 key，也不用登录），两小时刷新一次，
结果缓存在 kv 里，断网也不会崩，只是拿不到新梗。
"""

from __future__ import annotations

import json
import time
import urllib.request

BAIDU = "https://top.baidu.com/api/board?platform=wise&tab=realtime"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFRESH_SEC = 2 * 3600
MAX_ITEMS = 18
BLOCK_WORDS = ("习近平", "共产党", "国务院", "外交部", "政治局", "中央")


def _fetch() -> list[str]:
    req = urllib.request.Request(BAIDU, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8", "ignore"))
    cards = data.get("data", {}).get("cards") or []
    words: list[str] = []
    for card in cards:
        for block in card.get("content") or []:
            for item in block.get("content") or []:
                word = (item.get("word") or "").strip()
                if not word:
                    continue
                if any(bad in word for bad in BLOCK_WORDS):
                    continue
                if item.get("isTop"):
                    continue
                if word not in words:
                    words.append(word)
    return words[:MAX_ITEMS]


def topics(memory, now: float | None = None, force: bool = False) -> list[str]:
    """拿一份热搜词条。缓存过期才真去请求，失败就退回旧缓存。"""
    now = now or time.time()
    try:
        stamp = float(memory.kv_get("hot_ts") or 0)
    except Exception:  # noqa: BLE001
        stamp = 0.0
    cached = memory.kv_get("hot_words")
    words = []
    if cached:
        try:
            words = json.loads(cached)
        except Exception:  # noqa: BLE001
            words = []
    if words and not force and now - stamp < REFRESH_SEC:
        return words
    try:
        fresh = _fetch()
    except Exception as exc:  # noqa: BLE001
        print(f"[hot] 热搜拉取失败：{exc}", flush=True)
        return words
    if fresh:
        memory.kv_set("hot_words", json.dumps(fresh, ensure_ascii=False))
        memory.kv_set("hot_ts", str(now))
        return fresh
    return words


def note(memory, now: float | None = None) -> str:
    """拼成一小段给她看的文字。"""
    words = topics(memory, now)
    if not words:
        return ""
    joined = "、".join(words)
    return (
        "【这会儿网上在聊】"
        + joined
        + "\n（这些是你刷到过的热搜。聊天里有人提到相关的可以自然接一句，"
          "别硬往话题里塞，也别像播报新闻一样念标题。）"
    )
