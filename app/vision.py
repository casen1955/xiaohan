"""识图：把聊天里收到的图片喂给 Qwen3-VL，让她真的「看见」。

只依赖标准库：图片读成 base64 data URI，走 OpenAI 兼容的 /chat/completions。
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

API = "https://api.siliconflow.cn/v1/chat/completions"
DEFAULT_MODEL = "Qwen/Qwen3-VL-8B-Instruct"

PROMPT = (
    "这是一张别人发到微信聊天里的图片。用中文说清楚图片里有什么："
    "主体是什么、画面里有没有文字（原样抄下来）、是什么类型（照片/截图/表情包/画）。"
    "两三句话，不要评论、不要加前缀。"
)


def _mime_of(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(ext, "image/png")


def describe(path: str, key: str, model: str = DEFAULT_MODEL, timeout: int = 60,
             prompt: str = "") -> str:
    """返回一句中文描述；失败返回空串。prompt 可覆盖默认提示词。"""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except Exception as exc:  # noqa: BLE001
        print(f"[vision] 读图失败: {exc}", flush=True)
        return ""
    if not raw:
        return ""
    if len(raw) > 6 * 1024 * 1024:          # 太大就别传了
        return ""
    data_uri = f"data:{_mime_of(path)};base64,{base64.b64encode(raw).decode()}"
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": prompt or PROMPT},
            ],
        }],
        "max_tokens": 300,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        print(f"[vision] HTTP {exc.code}: {body}", flush=True)
        return ""
    except Exception as exc:  # noqa: BLE001
        print(f"[vision] 请求失败: {exc}", flush=True)
        return ""
    try:
        return (data["choices"][0]["message"]["content"] or "").strip().replace("\n", " ")
    except Exception:
        return ""
