"""看看她脑子里存了什么：python tools/show_memory.py [名字]"""
import sqlite3
import sys

con = sqlite3.connect("data/xiaohan.db")
con.row_factory = sqlite3.Row
who = sys.argv[1] if len(sys.argv) > 1 else ""

contacts = {r["wxid"]: r["name"] for r in con.execute("SELECT wxid, name FROM contacts")}

def scope_name(scope: str) -> str:
    kind, _, val = scope.partition(":")
    if kind == "contact":
        return contacts.get(val, val)
    if kind == "chat":
        return contacts.get(val) or val
    return scope

rows = con.execute(
    "SELECT scope, k, v, updated_at FROM facts ORDER BY scope, updated_at DESC"
).fetchall()
grouped: dict[str, list] = {}
for r in rows:
    label = scope_name(r["scope"])
    if who and who not in label and who not in (r["v"] or ""):
        continue
    grouped.setdefault(label, []).append(r)

if not grouped:
    print("还没有存下任何东西。跟她多聊几句，15 分钟会自动整理一次。")
    sys.exit(0)

for label, items in grouped.items():
    print(f"\n=== {label}（{len(items)} 条）===")
    for it in items:
        print(f"  {it['k']}：{it['v']}")

total = sum(len(v) for v in grouped.values())
print(f"\n合计 {total} 条记忆，涉及 {len(grouped)} 个人/群。")
