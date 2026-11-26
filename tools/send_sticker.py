"""手动发一张表情包（调试用）。

  python tools/send_sticker.py 哥哥 叹气
  python tools/send_sticker.py 哥哥            # 随一张
"""

from __future__ import annotations

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from app.adapters.uia import UiaAdapter  # noqa: E402
from app.stickers import StickerBook  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    chat = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else None
    book = StickerBook()
    if not book:
        print("stickers/manifest.json 里没有可用表情")
        return 2
    item = book.pick(label)
    print(f"发：{item.get('band')} / {item.get('caption')}")
    adapter = UiaAdapter(self_name="小涵", poll_interval=1.0, chat_whitelist=[chat])
    adapter.send_sticker(chat, item["path"])
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
