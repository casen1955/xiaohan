"""本地管理页：改人设、加好友、看日志、试对话。只监听 127.0.0.1。"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import logbus

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


class AdminServer:
    def __init__(self, *, cfg: dict, memory, persona_path: str, brain_factory, host="127.0.0.1", port=8799):
        self.cfg = cfg
        self.memory = memory
        self.persona_path = persona_path
        self.brain_factory = brain_factory
        self.host = host
        self.port = port
        self._httpd: ThreadingHTTPServer | None = None

    def start(self) -> str:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # 静默
                return

            # ---------- 工具 ----------

            def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _json(self, obj, code: int = 200):
                self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

            def _body(self) -> dict:
                n = int(self.headers.get("Content-Length") or 0)
                if not n:
                    return {}
                try:
                    return json.loads(self.rfile.read(n).decode("utf-8"))
                except Exception:  # noqa: BLE001
                    return {}

            # ---------- 路由 ----------

            def do_GET(self):  # noqa: N802
                path = urllib.parse.urlparse(self.path).path
                if path in ("/", "/index.html"):
                    with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as fh:
                        self._send(200, fh.read().encode("utf-8"), "text/html; charset=utf-8")
                    return
                if path == "/api/state":
                    with open(outer.persona_path, encoding="utf-8") as fh:
                        persona = fh.read()
                    self._json({
                        "persona": persona,
                        "contacts": outer.memory.contacts(),
                        "limits": outer.cfg["limits"],
                        "features": outer.cfg.get("features", {}),
                        "log": logbus.tail(120),
                        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    return
                if path == "/api/log":
                    self._json({"log": logbus.tail(150)})
                    return
                self._json({"error": "not found"}, 404)

            def do_POST(self):  # noqa: N802
                path = urllib.parse.urlparse(self.path).path
                data = self._body()

                if path == "/api/persona":
                    text = (data.get("text") or "").strip()
                    if not text:
                        self._json({"error": "人设不能为空"}, 400)
                        return
                    with open(outer.persona_path, "w", encoding="utf-8") as fh:
                        fh.write(text + "\n")
                    logbus.log("人设已更新")
                    self._json({"ok": True})
                    return

                if path == "/api/contact":
                    wxid = (data.get("wxid") or "").strip()
                    if not wxid:
                        self._json({"error": "缺 wxid"}, 400)
                        return
                    outer.memory.upsert_contact(
                        wxid,
                        name=(data.get("name") or "").strip(),
                        relation=(data.get("relation") or "").strip(),
                        note=(data.get("note") or "").strip(),
                        proactive_limit=int(data.get("proactive_limit") or 1),
                        proactive_enabled=1 if data.get("proactive_enabled", True) else 0,
                    )
                    logbus.log(f"好友已保存: {wxid}")
                    self._json({"ok": True, "contacts": outer.memory.contacts()})
                    return

                if path == "/api/test":
                    text = (data.get("text") or "").strip()
                    if not text:
                        self._json({"error": "空消息"}, 400)
                        return
                    try:
                        brain = outer.brain_factory()
                        replies = brain.respond(
                            chat_id="admin:test", chat_name="哥", is_group=False,
                            group_name="", peers=[], contact_wxid=None,
                            user_name="哥", text=text, is_mentioned=False,
                        )
                        self._json({"replies": replies})
                    except Exception as exc:  # noqa: BLE001
                        self._json({"error": str(exc)}, 500)
                    return

                self._json({"error": "not found"}, 404)

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        threading.Thread(target=self._httpd.serve_forever, name="admin", daemon=True).start()
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
