import sqlite3
db = sqlite3.connect("data/xiaohan.db")
cur = db.cursor()
real = "wxid_01kbksr4g3mf12"
# 1) 把占位档「姐姐」并到真 wxid 上，名字跟微信备注一致
cur.execute("update facts set scope=? where scope=?", (f"contact:{real}", "contact:姐姐"))
cur.execute("""update contacts set name=?, relation=?, proactive_enabled=?, note=?
               where wxid=?""",
            ("姐姐", "姐姐", 0,
             "当面称呼：姐姐；哈工大建筑学研究生，比哥大六岁；先被动，她来找再热络", real))
cur.execute("delete from contacts where wxid='姐姐'")
db.commit()
print("已合并「姐姐」→", real)
print()
for r in cur.execute("select name, wxid, relation, proactive_enabled from contacts order by name"):
    print(f"  {r[0]:<8} {r[1][:22]:<24} 关系={r[2] or '-':<6} 主动={r[3]}")
db.close()
