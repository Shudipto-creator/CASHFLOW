import sqlite3
c = sqlite3.connect("data/cashflow.db")
for row in c.execute("SELECT name, sql FROM sqlite_master WHERE type='table'"):
    if row[0] == "users":
        print(row[1])
print("TABLES:", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()])
