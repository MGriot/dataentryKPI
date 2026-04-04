import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from src
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import settings as app_config

def main():
    try:
        db_path = app_config.get_database_path("db_kpis.db")
    except Exception as e:
        print(f"Configuration Error: {e}")
        return

    if not db_path.exists():
        print(f"Error: Database file not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Update 'CALC TYPE INCREMENTAL' to 'Incremental'
        cursor.execute("UPDATE kpis SET calculation_type = ? WHERE calculation_type = ?", ('Incremental', 'CALC TYPE INCREMENTAL'))
        if cursor.rowcount > 0:
            print(f"Updated {cursor.rowcount} rows for 'CALC TYPE INCREMENTAL'.")

        # Update 'CALC TYPE AVERAGE' to 'Average'
        cursor.execute("UPDATE kpis SET calculation_type = ? WHERE calculation_type = ?", ('Average', 'CALC TYPE AVERAGE'))
        if cursor.rowcount > 0:
            print(f"Updated {cursor.rowcount} rows for 'CALC TYPE AVERAGE'.")

        conn.commit()
        conn.close()
        print("Database update check complete.")
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()