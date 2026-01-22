import sqlite3
import os

db_path = "C:\\Users\\Admin\\Documents\\Coding\\dataentryKPI\\databases\\db_plants.db"

if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
else:
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
