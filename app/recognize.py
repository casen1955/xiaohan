"""看懂图：先找文字去网上搜，搜不到再让视觉模型硬看。

表情包和图片大多带字（"笑死我了""这波啊"），带字就有梗可查；
纯粹一张画、搜不到词，那才交给 Qwen3-VL 描述画面。
"""

from __future__ import annotations

from . import vision, websearch

MIN_TEXT_LEN = 2
MAX_RESULTS = 3


def _tidy(text: str) -> str:
    text = (text or "").strip().strip("「」\"'`")
    text = text.replace("\n", " ")
    return text[:60]


def read_text(path: str, key: str) -> str:
    """让视觉模型只念字。念不出东西就返回空串。"""
    prompt = (
        "只做一件事：把图片里的文字原样念出来，不要描述画面、不要评论。"
        "如果图里没有文字，就只输出 NONE。"
    )
    try:
        return vision.describe(path, key, prompt=prompt, timeout=45) or ""
    except Exception:  # noqa: BLE001
        return ""


def understand(path: str, key: str, kind: str = "image") -> str:
    """返回一句给她看的描述。顺序：文字 → 联网 → 视觉模型。"""
    raw = read_text(path, key)
    text = _tidy(raw)
    looks_like_none = (not text) or text.upper().startswith("NONE") or text in {
        "无", "没有文字", "无文字", "图片中没有文字",
    }
    if not looks_like_none and len(text) >= MIN_TEXT_LEN:
        try:
            hits = websearch.search(text, n=MAX_RESULTS)
        except Exception:  # noqa: BLE001
            hits = []
        if hits:
            titles = "；".join(_tidy(h.get("title", "")) for h in hits[:2] if h.get("title"))
            if titles:
                head = "表情包上的字" if kind == "emoji" else "图里的字"
                return f"{head}是「{text}」，网上相关的说法有：{titles}"
    desc = ""
    try:
        desc = vision.describe(path, key) or ""
    except Exception:  # noqa: BLE001
        desc = ""
    if desc:
        return desc
    return f"{text}" if text else ""
