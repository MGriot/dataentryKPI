import csv
import sqlite3
import zipfile
import io
import traceback
from pathlib import Path
from src.config.settings import get_database_path

def get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> list[str]:
    """Fetches the column names for a given table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

def import_from_zip(zip_path: str):
    """Restores the database state from a ZIP backup by appending data.

    Expects the raw per-table CSV dumps produced by export_manager.export_raw_backup_csvs
    (filenames/tables must match RAW_BACKUP_TABLES there) -- these preserve primary keys and
    foreign-key columns, unlike the human-readable enriched CSVs used for single-table export.
    The order below respects foreign-key dependencies (parents before children).
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            import_order = [
                ('raw_plants.csv', 'plants', get_database_path('db_plants.db')),
                ('raw_kpi_nodes.csv', 'kpi_nodes', get_database_path('db_kpis.db')),
                ('raw_kpi_indicators.csv', 'kpi_indicators', get_database_path('db_kpis.db')),
                ('raw_kpis.csv', 'kpis', get_database_path('db_kpis.db')),
                ('raw_kpi_plant_visibility.csv', 'kpi_plant_visibility', get_database_path('db_kpis.db')),
                ('raw_kpi_indicator_templates.csv', 'kpi_indicator_templates', get_database_path('db_kpi_templates.db')),
                ('raw_template_defined_indicators.csv', 'template_defined_indicators', get_database_path('db_kpi_templates.db')),
                ('raw_global_kpi_splits.csv', 'global_kpi_splits', get_database_path('db_kpi_templates.db')),
                ('raw_global_split_years.csv', 'global_split_years', get_database_path('db_kpi_templates.db')),
                ('raw_global_split_indicators.csv', 'global_split_indicators', get_database_path('db_kpi_templates.db')),
                ('raw_annual_targets.csv', 'annual_targets', get_database_path('db_kpi_targets.db')),
                ('raw_kpi_annual_target_values.csv', 'kpi_annual_target_values', get_database_path('db_kpi_targets.db')),
                ('raw_kpi_targets.csv', 'kpi_targets', get_database_path('db_kpi_targets.db')),
                ('raw_daily_targets.csv', 'daily_targets', get_database_path('db_kpi_days.db')),
                ('raw_weekly_targets.csv', 'weekly_targets', get_database_path('db_kpi_weeks.db')),
                ('raw_monthly_targets.csv', 'monthly_targets', get_database_path('db_kpi_months.db')),
                ('raw_quarterly_targets.csv', 'quarterly_targets', get_database_path('db_kpi_quarters.db')),
                ('raw_actual_measurements.csv', 'actual_measurements', get_database_path('db_kpi_actuals.db')),
            ]

            for file_name, table_name, db_path in import_order:
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