import sqlite3
import sys

db_path = sys.argv[1]
table_name = sys.argv[2]
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute(f"PRAGMA table_info({table_name});")
print(f"Columns in {table_name} ({db_path}):")
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")
conn.close()
