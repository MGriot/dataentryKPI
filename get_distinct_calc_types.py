import sqlite3
import os

db_path = "C:\\Users\\Admin\\Documents\\Coding\\dataentryKPI\\databases\\db_kpis.db"

if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT calculation_type FROM kpis")
        calculation_types = cursor.fetchall()
        
        if calculation_types:
            print("Distinct calculation_types in kpis table:")
            for calc_type in calculation_types:
                print(f"- {calc_type[0]}")
        else:
            print("No calculation_types found in kpis table.")

        conn.close()
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
