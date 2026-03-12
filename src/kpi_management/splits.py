# src/kpi_management/splits.py
import sqlite3
import json
import traceback
from src.config import settings as app_config
from pathlib import Path

def add_global_split(name: str, year: int, repartition_logic: str, repartition_values: dict, distribution_profile: str, profile_params: dict) -> int:
    """Adds a new global KPI split template."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_templates_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO global_kpi_splits (name, year, repartition_logic, repartition_values, distribution_profile, profile_params)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, year, repartition_logic, json.dumps(repartition_values), distribution_profile, json.dumps(profile_params))
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"ERROR: Database error while adding global split '{name}'. Details: {e}")
            print(traceback.format_exc())
            raise

def update_global_split(split_id: int, **kwargs):
    """Updates an existing global KPI split template."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    
    # Map fields to their serialization logic
    serialized_fields = {'repartition_values', 'profile_params'}
    
    set_clauses = []
    params = []
    for key, value in kwargs.items():
        if key in serialized_fields:
            set_clauses.append(f"{key} = ?")
            params.append(json.dumps(value))
        else:
            set_clauses.append(f"{key} = ?")
            params.append(value)
    
    if not set_clauses:
        return

    params.append(split_id)
    query = f"UPDATE global_kpi_splits SET {', '.join(set_clauses)} WHERE id = ?"

    with sqlite3.connect(db_templates_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR: Database error while updating global split ID {split_id}. Details: {e}")
            print(traceback.format_exc())
            raise

def delete_global_split(split_id: int):
    """Deletes a global KPI split template."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_templates_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM global_kpi_splits WHERE id = ?", (split_id,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR: Database error while deleting global split ID {split_id}. Details: {e}")
            print(traceback.format_exc())
            raise

def get_global_split(split_id: int) -> dict:
    """Retrieves a single global KPI split template."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_templates_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM global_kpi_splits WHERE id = ?", (split_id,)).fetchone()
            if row:
                res = dict(row)
                res['repartition_values'] = json.loads(res['repartition_values'])
                res['profile_params'] = json.loads(res['profile_params'])
                return res
            return None
        except sqlite3.Error as e:
            print(f"ERROR: Database error while retrieving global split ID {split_id}. Details: {e}")
            return None

def get_all_global_splits(year: int = None) -> list[dict]:
    """Retrieves all global KPI split templates, optionally filtered by year."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    query = "SELECT * FROM global_kpi_splits"
    params = []
    if year:
        query += " WHERE year = ?"
        params.append(year)
    query += " ORDER BY name"

    with sqlite3.connect(db_templates_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(query, params).fetchall()
            results = []
            for row in rows:
                res = dict(row)
                res['repartition_values'] = json.loads(res['repartition_values'])
                res['profile_params'] = json.loads(res['profile_params'])
                results.append(res)
            return results
        except sqlite3.Error as e:
            print(f"ERROR: Database error while retrieving all global splits. Details: {e}")
            return []
