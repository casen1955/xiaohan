"""把 facts 里用「名字」当 scope 的条目，合并到对应的真 wxid 档案上。"""
import sqlite3, sys

con = sqlite3.connect("data/xiaohan.db")
con.row_factory = sqlite3.Row
pairs = {}
for r in con.execute("SELECT wxid, name FROM contacts"):
    wxid, name = str(r["wxid"] or "").strip(), str(r["name"] or "").strip()
    if wxid and name and wxid != name:
        pairs[name] = wxid

print("名字 → wxid 映射：", pairs)
moved = 0
for name, wxid in pairs.items():
    rows = con.execute("SELECT k, v, updated_at FROM facts WHERE scope = ?", (f"contact:{name}",)).fetchall()
    for row in rows:
        con.execute(
            "INSERT INTO facts(scope, k, v, updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(scope, k) DO UPDATE SET v=excluded.v, updated_at=excluded.updated_at",
            (f"contact:{wxid}", row["k"], row["v"], row["updated_at"]),
        )
        moved += 1
    if rows:
        con.execute("DELETE FROM facts WHERE scope = ?", (f"contact:{name}",))
        print(f"  {name}: 搬了 {len(rows)} 条 → contact:{wxid}")
con.commit()
print("合计搬移:", moved, "条")
print("\n各 scope 现状：")
for r in con.execute("SELECT scope, COUNT(*) c FROM facts GROUP BY scope ORDER BY c DESC"):
    print(f"  {r['scope']:36s} {r['c']}")
