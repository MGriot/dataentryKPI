import sqlite3
import json
import traceback
from pathlib import Path
from src.config import settings as app_config

def migrate_to_dynamic_targets():
    db_targets_path = app_config.get_database_path("db_kpi_targets.db")
    print(f"Starting migration for {db_targets_path}...")

    try:
        with sqlite3.connect(db_targets_path) as conn:
            cursor = conn.cursor()
            
            # 1. Create the new normalized table for target values
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_annual_target_values (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annual_target_id INTEGER NOT NULL,
                    target_number INTEGER NOT NULL,
                    target_value REAL,
                    is_manual BOOLEAN NOT NULL DEFAULT 1,
                    is_formula_based BOOLEAN NOT NULL DEFAULT 0,
                    formula TEXT,
                    formula_inputs TEXT DEFAULT '[]',
                    FOREIGN KEY (annual_target_id) REFERENCES annual_targets(id) ON DELETE CASCADE,
                    UNIQUE(annual_target_id, target_number)
                )
            """)
            
            # 2. Check if we need to migrate data (if new table is empty)
            cursor.execute("SELECT COUNT(*) FROM kpi_annual_target_values")
            if cursor.fetchone()[0] == 0:
                print("Migrating data from annual_targets to kpi_annual_target_values...")
                
                # Fetch all existing records
                cursor.execute("SELECT id, annual_target1, annual_target2, is_target1_manual, is_target2_manual, "
                               "target1_is_formula_based, target2_is_formula_based, target1_formula, target2_formula, "
                               "target1_formula_inputs, target2_formula_inputs FROM annual_targets")
                rows = cursor.fetchall()
                
                migration_data = []
                for row in rows:
                    at_id, t1, t2, m1, m2, f1_flag, f2_flag, f1_str, f2_str, f1_in, f2_t2_in = row
                    
                    # Target 1
                    migration_data.append((at_id, 1, t1, m1, f1_flag, f1_str, f1_in))
                    # Target 2
                    migration_data.append((at_id, 2, t2, m2, f2_flag, f2_str, f2_t2_in))
                
                if migration_data:
                    cursor.executemany("""
                        INSERT INTO kpi_annual_target_values 
                        (annual_target_id, target_number, target_value, is_manual, is_formula_based, formula, formula_inputs)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, migration_data)
                    print(f"Successfully migrated {len(migration_data)} target value entries.")

            # 3. Update Periodic Target Databases CHECK constraints
            # We can't easily ALTER a CHECK constraint in SQLite. 
            # But we can recreate the tables if needed. 
            # Actually, most of them were CHECK(target_number IN (1, 2)).
            
            periodic_dbs = ["db_kpi_days.db", "db_kpi_weeks.db", "db_kpi_months.db", "db_kpi_quarters.db"]
            periodic_tables = ["daily_targets", "weekly_targets", "monthly_targets", "quarterly_targets"]
            
            for db_name, table_name in zip(periodic_dbs, periodic_tables):
                db_path = app_config.get_database_path(db_name)
                print(f"Updating CHECK constraint for {table_name} in {db_name}...")
                with sqlite3.connect(db_path) as p_conn:
                    p_cursor = p_conn.cursor()
                    
                    # Get period column name
                    p_cursor.execute(f"PRAGMA table_info({table_name})")
                    cols = p_cursor.fetchall()
                    period_col = cols[5][1] # 6th column is the period value (date_value, etc.)
                    
                    # Recreate table without the restrictive CHECK(target_number IN (1, 2))
                    # or update it to CHECK(target_number > 0)
                    p_cursor.execute(f"ALTER TABLE {table_name} RENAME TO {table_name}_old")
                    
                    p_cursor.execute(f"""
                        CREATE TABLE {table_name} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            year INTEGER NOT NULL,
                            plant_id INTEGER NOT NULL,
                            kpi_id INTEGER NOT NULL,
                            target_number INTEGER NOT NULL CHECK(target_number > 0),
                            {period_col} TEXT NOT NULL,
                            target_value REAL NOT NULL,
                            UNIQUE(year, plant_id, kpi_id, target_number, {period_col})
                        )
                    """)
                    
                    p_cursor.execute(f"INSERT INTO {table_name} SELECT * FROM {table_name}_old")
                    p_cursor.execute(f"DROP TABLE {table_name}_old")
                    p_conn.commit()

            conn.commit()
            print("Migration completed successfully.")
            return True

    except Exception as e:
        print(f"Migration FAILED: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    migrate_to_dynamic_targets()
