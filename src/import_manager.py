import csv
from pathlib import Path
import traceback
import sqlite3
from target_management.annual import save_annual_targets

def import_data_from_csv(file_path: Path, table_name: str, db_path: Path, year: int, stabilimento_id: int):
    """Imports data from a CSV file into a specified table in the database."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data = [row for row in reader]

        if not data:
            return "File is empty, nothing to import."

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for row in data:
                columns = ', '.join(row.keys())
                placeholders = ', '.join('?' * len(row))
                sql = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, list(row.values()))
            conn.commit()

        if table_name == 'annual_targets':
            targets_data_map = {row['kpi_id']: row for row in data}
            save_annual_targets(year, stabilimento_id, targets_data_map)

        return f"Successfully imported {len(data)} rows into {table_name}."

    except Exception as e:
        return f"Error importing data into {table_name}: {e}\n{traceback.format_exc()}"