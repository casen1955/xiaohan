# -*- coding: utf-8 -*-
"""把占位联系人（wxid == 名字）并到真 wxid 上，避免同一个人出现两行、主动消息打两遍。"""
import sqlite3, sys

db = sqlite3.connect("data/xiaohan.db")
db.row_factory = sqlite3.Row
cur = db.cursor()
rows = [dict(r) for r in cur.execute("select * from contacts").fetchall()]
real = {}
for r in rows:
    if r["wxid"] != r["name"]:
        real.setdefault(r["name"], r)

merged = 0
for r in rows:
    if r["wxid"] != r["name"]:
        continue
    target = real.get(r["name"])
    if not target:
        continue
    # 事实搬过去
    cur.execute("update facts set scope=? where scope=?",
                (f"contact:{target['wxid']}", f"contact:{r['name']}"))
    # 权限取「或」：任何一边允许就允许
    enabled = max(int(r.get("proactive_enabled") or 0), int(target.get("proactive_enabled") or 0))
    note = target.get("note") or r.get("note") or ""
    cur.execute("update contacts set proactive_enabled=?, note=?, relation=coalesce(nullif(relation,''),?) where wxid=?",
                (enabled, note, r.get("relation") or "", target["wxid"]))
    cur.execute("delete from contacts where wxid=?", (r["name"],))
    merged += 1
    print(f"合并 {r['name']} → {target['wxid']}")
db.commit()
print("共合并", merged, "条占位档")
print()
print("现在联系人：")
for c in cur.execute("select name, wxid, relation, proactive_enabled from contacts order by name"):
    print(f"  {c['name']:<10} {c['wxid'][:24]:<26} 关系={c['relation'] or '-':<6} 主动={c['proactive_enabled']}")
db.close()
