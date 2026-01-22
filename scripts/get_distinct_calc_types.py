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

if __name__ == "__main__":
    main()