# -*- coding: utf-8 -*-
"""她自己在网上逛：B 站热门/搜索、抖音热榜、百度热搜。

不注入浏览器，只用公开接口拿「标题」，够她在聊天里随口提一句了。
"""
from __future__ import annotations

import json
import random
import time
import urllib.parse
import urllib.request

UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*",
}

# 她的兴趣，用来搜 B 站（隔一阵换一个）
INTERESTS = [
    "邦多利", "MyGO", "世界计划 pjsk", "少女乐队", "新番 动画",
    "火影忍者手游", "钢铁雄心4", "鬼畜", "地偶 livehouse", "A股",
]

SEEN_KEY = "browse_seen"
TS_KEY = "browse_ts"
DAY_KEY = "browse_day"
COUNT_KEY = "browse_count"


def _get_json(url: str, timeout: float = 12.0) -> dict | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"[browse] 请求失败 {url[:60]}: {exc}", flush=True)
        return None


def bilibili_popular(n: int = 20) -> list[dict]:
    data = _get_json(f"https://api.bilibili.com/x/web-interface/popular?ps={n}&pn=1")
    if not data or data.get("code") != 0:
        return []
    out = []
    for v in (data.get("data") or {}).get("list") or []:
        out.append({
            "title": v.get("title", ""),
            "tag": v.get("tname", ""),
            "up": (v.get("owner") or {}).get("name", ""),
            "url": f"https://www.bilibili.com/video/{v.get('bvid', '')}",
            "source": "b站热门",
        })
    return out


def bilibili_search(keyword: str, n: int = 8) -> list[dict]:
    kw = urllib.parse.quote(keyword)
    data = _get_json(
        f"https://api.bilibili.com/x/web-interface/search/type"
        f"?search_type=video&keyword={kw}&page=1"
    )
    if not data or data.get("code") != 0:
        return []
    out = []
    for v in ((data.get("data") or {}).get("result") or [])[:n]:
        title = (v.get("title") or "").replace('<em class="keyword">', "").replace("</em>", "")
        bvid = v.get("bvid", "")
        out.append({
            "title": title,
            "tag": keyword,
            "up": v.get("author", ""),
            "url": f"https://www.bilibili.com/video/{bvid}" if bvid else "",
            "source": "b站",
        })
    return out


def douyin_hot(n: int = 15) -> list[dict]:
    data = _get_json("https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/")
    if not data or data.get("status_code") != 0:
        return []
    out = []
    for w in (data.get("word_list") or [])[:n]:
        word = w.get("word") or ""
        if word:
            out.append({"title": word, "tag": "抖音热榜", "up": "",
                        "url": "", "source": "抖音热榜"})
    return out


def pick(memory, now: float | None = None, rng: random.Random | None = None) -> dict | None:
    """挑一条她「刚刷到」的内容，避开已经发过的。"""
    now = now or time.time()
    rng = rng or random
    seen = memory.kv_get(SEEN_KEY) or []
    if isinstance(seen, str):
        try:
            seen = json.loads(seen)
        except Exception:  # noqa: BLE001
            seen = []
    seen_set = set(seen[-200:])

    pool: list[dict] = []
    roll = rng.random()
    if roll < 0.45:
        pool = bilibili_search(rng.choice(INTERESTS), 8)
    elif roll < 0.8:
        pool = bilibili_popular(20)
    else:
        pool = douyin_hot(15)

    fresh = [x for x in pool if x.get("title") and x["title"] not in seen_set]
    if not fresh:
        fresh = [x for x in pool if x.get("title")]
    if not fresh:
        return None

    item = rng.choice(fresh)
    seen.append(item["title"])
    memory.kv_set(SEEN_KEY, json.dumps(seen[-200:], ensure_ascii=False))
    memory.kv_set(TS_KEY, int(now))
    return item


def note(item: dict) -> str:
    """把一条内容说成她能随口提的句子素材。"""
    title = (item.get("title") or "").strip()
    src = item.get("source") or ""
    up = item.get("up") or ""
    if src == "抖音热榜":
        return f"抖音热榜上#{title}"
    tail = f"，{up}" if up else ""
    return f"{src}上刷到「{title}」{tail}"
