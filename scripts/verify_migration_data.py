import sqlite3
import sys
from src.config import settings as app_config

db_path = app_config.get_database_path("db_kpi_targets.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM kpi_annual_target_values")
count = cursor.fetchone()[0]
print(f"Total rows in kpi_annual_target_values: {count}")

cursor.execute("SELECT * FROM kpi_annual_target_values LIMIT 5")
for row in cursor.fetchall():
    print(row)
conn.close()
