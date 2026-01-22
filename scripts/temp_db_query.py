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
        db_path = app_config.get_database_path("db_plants.db")
    except Exception as e:
        print(f"Configuration Error: {e}")
        return

    if not db_path.exists():
        print(f"Error: Database file not found at {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, visible, color FROM plants")
        plants = cursor.fetchall()
        if plants:
            print("Existing plants:")
            for plant in plants:
                print(f"  Name: {plant[0]}, Description: {plant[1]}, Visible: {bool(plant[2])}, Color: {plant[3]}")
        else:
            print("No plants found in the database.")
        conn.close()
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()