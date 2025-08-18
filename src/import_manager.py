import csv
import sqlite3
import zipfile
import io
import traceback
from pathlib import Path
from app_config import get_database_path

def get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> list[str]:
    """Fetches the column names for a given table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

def import_from_zip(zip_path: str):
    """Restores the database state from a ZIP backup by appending data."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # The order is critical to respect foreign key constraints
            import_order = {
                'dict_plants.csv': ('plants', get_database_path('db_plants.db')),
                'dict_kpi_groups.csv': ('kpi_groups', get_database_path('db_kpis.db')),
                'dict_kpi_subgroups.csv': ('kpi_subgroups', get_database_path('db_kpis.db')),
                'dict_kpi_indicators.csv': ('kpi_indicators', get_database_path('db_kpis.db')),
                'dict_kpis.csv': ('kpis', get_database_path('db_kpis.db')),
                'all_annual_kpi_master_targets.csv': ('annual_targets', get_database_path('db_kpi_targets.db')),
                'all_daily_kpi_targets.csv': ('daily_targets', get_database_path('db_periodic_targets.db')),
                'all_weekly_kpi_targets.csv': ('weekly_targets', get_database_path('db_periodic_targets.db')),
                'all_monthly_kpi_targets.csv': ('monthly_targets', get_database_path('db_periodic_targets.db')),
                'all_quarterly_kpi_targets.csv': ('quarterly_targets', get_database_path('db_periodic_targets.db')),
            }

            for file_name, (table_name, db_path) in import_order.items():
                if file_name not in zipf.namelist():
                    continue

                with zipf.open(file_name) as csv_file:
                    # Decode the file in memory
                    csv_text = io.TextIOWrapper(csv_file, 'utf-8')
                    reader = csv.DictReader(csv_text)
                    data = [row for row in reader]

                    if not data:
                        continue

                    with sqlite3.connect(db_path) as conn:
                        cursor = conn.cursor()
                        db_columns = get_table_columns(cursor, table_name)
                        
                        # Filter CSV data to only include columns that exist in the DB table
                        valid_data = []
                        for row in data:
                            valid_row = {k: v for k, v in row.items() if k in db_columns}
                            valid_data.append(valid_row)

                        if not valid_data:
                            continue

                        # Prepare the INSERT statement based on valid columns
                        columns = ', '.join(valid_data[0].keys())
                        placeholders = ', '.join('?' * len(valid_data[0]))
                        sql = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})"
                        
                        # Execute for all valid rows
                        cursor.executemany(sql, [list(row.values()) for row in valid_data])
                        conn.commit()

        return "Database restore/append completed successfully."

    except Exception as e:
        return f"Error restoring from backup: {e}\n{traceback.format_exc()}"