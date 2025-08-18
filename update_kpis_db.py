import sqlite3
import os

db_path = "C:\\Users\\Admin\\Documents\\Coding\\dataentryKPI\\databases\\db_kpis.db"

if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Update 'CALC TYPE INCREMENTAL' to 'Incremental'
        cursor.execute("UPDATE kpis SET calculation_type = ? WHERE calculation_type = ?", ('Incremental', 'CALC TYPE INCREMENTAL'))
        print(f"Updated {cursor.rowcount} rows for 'CALC TYPE INCREMENTAL'.")

        # Update 'CALC TYPE AVERAGE' to 'Average'
        cursor.execute("UPDATE kpis SET calculation_type = ? WHERE calculation_type = ?", ('Average', 'CALC TYPE AVERAGE'))
        print(f"Updated {cursor.rowcount} rows for 'CALC TYPE AVERAGE'.")

        conn.commit()
        conn.close()
        print("Database update complete.")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
