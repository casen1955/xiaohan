"""DeepSeek 客户端。纯标准库，不装任何包。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class ModelError(RuntimeError):
    pass


class LLM:
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat", timeout: int = 120, retries: int = 3):
        if not api_key:
            raise ModelError("没有 API key")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def chat(self, messages, temperature: float = 1.1, max_tokens: int = 800) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        last: Exception | None = None
        for attempt in range(self.retries):
            req = urllib.request.Request(
                self.base_url + "/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + self.api_key,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return (data["choices"][0]["message"]["content"] or "").strip()
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                last = ModelError(f"HTTP {exc.code}: {detail}")
                if exc.code in (400, 401, 402, 422):
                    break
            except Exception as exc:  # noqa: BLE001
                last = ModelError(f"{type(exc).__name__}: {exc}")
            time.sleep(1.5 ** attempt)
        raise last or ModelError("未知错误")
