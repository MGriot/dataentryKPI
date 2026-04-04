# src/kpi_management/splits.py
import sqlite3
import json
import traceback
from src.config import settings as app_config
from pathlib import Path

def add_global_split(name: str, years: list[int], repartition_logic: str, repartition_values: dict, distribution_profile: str, profile_params: dict, afflicted_indicators: list[dict] = None) -> int:
    """Adds a new global KPI split template and optionally links indicators."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_templates_path) as conn:
        try:
            cursor = conn.cursor()
            # We still keep 'year' in the main table for backward compatibility (first year)
            first_year = years[0] if years else None
            cursor.execute(
                """INSERT INTO global_kpi_splits (name, year, repartition_logic, repartition_values, distribution_profile, profile_params)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, first_year, repartition_logic, json.dumps(repartition_values), distribution_profile, json.dumps(profile_params))
            )
            split_id = cursor.lastrowid
            
            # Insert years into mapping table
            for y in years:
                cursor.execute("INSERT OR IGNORE INTO global_split_years (global_split_id, year) VALUES (?, ?)", (split_id, y))
            
            conn.commit()
            
            if afflicted_indicators:
                update_global_split_indicators(split_id, afflicted_indicators)
                
            return split_id
        except sqlite3.Error as e:
            print(f"ERROR: Database error while adding global split '{name}'. Details: {e}")
            print(traceback.format_exc())
            raise

def update_global_split(split_id: int, **kwargs):
    """Updates an existing global KPI split template and its linked indicators."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    
    # Handle afflicted_indicators separately
    afflicted = kwargs.pop('afflicted_indicators', None)
    years = kwargs.pop('years', None)
    
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
    
    with sqlite3.connect(db_templates_path) as conn:
        try:
            cursor = conn.cursor()
            if set_clauses:
                params.append(split_id)
                query = f"UPDATE global_kpi_splits SET {', '.join(set_clauses)} WHERE id = ?"
                cursor.execute(query, params)

            if years is not None:
                # Update first year for backward compatibility
                if years:
                    cursor.execute("UPDATE global_kpi_splits SET year = ? WHERE id = ?", (years[0], split_id))
                
                # Sync mapping table
                cursor.execute("DELETE FROM global_split_years WHERE global_split_id = ?", (split_id,))
                for y in years:
                    cursor.execute("INSERT INTO global_split_years (global_split_id, year) VALUES (?, ?)", (split_id, y))
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR: Database error while updating global split ID {split_id}. Details: {e}")
            raise

    if afflicted is not None:
        update_global_split_indicators(split_id, afflicted)

def delete_global_split(split_id: int):
    """Deletes a global KPI split template and its afflicted indicators."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_templates_path) as conn:
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM global_kpi_splits WHERE id = ?", (split_id,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR: Database error while deleting global split ID {split_id}. Details: {e}")
            print(traceback.format_exc())
            raise

def get_indicators_for_global_split(split_id: int) -> list[dict]:
    """Retrieves all indicators afflicted by a global split."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_templates_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM global_split_indicators WHERE global_split_id = ?", (split_id,)).fetchall()]
        except sqlite3.Error as e:
            print(f"ERROR: {e}")
            return []

def update_global_split_indicators(split_id: int, indicators_data: list[dict]):
    """
    Syncs the list of afflicted indicators for a global split.
    indicators_data: list of {'indicator_id': int, 'override_distribution_profile': str|None}
    """
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_templates_path) as conn:
        try:
            cursor = conn.cursor()
            # Clear existing
            cursor.execute("DELETE FROM global_split_indicators WHERE global_split_id = ?", (split_id,))
            # Insert new
            for ind in indicators_data:
                cursor.execute(
                    "INSERT INTO global_split_indicators (global_split_id, indicator_id, override_distribution_profile) VALUES (?, ?, ?)",
                    (split_id, ind['indicator_id'], ind.get('override_distribution_profile'))
                )
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR updating global split indicators: {e}")
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
                
                # Fetch years
                years_rows = conn.execute("SELECT year FROM global_split_years WHERE global_split_id = ?", (split_id,)).fetchall()
                res['years'] = [r['year'] for r in years_rows]
                return res
            return None
        except sqlite3.Error as e:
            print(f"ERROR: Database error while retrieving global split ID {split_id}. Details: {e}")
            return None

def get_global_splits_for_indicator(indicator_id: int) -> list[dict]:
    """Retrieves all global splits that affect a specific indicator."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_templates_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("""
                SELECT s.* FROM global_kpi_splits s
                JOIN global_split_indicators i ON s.id = i.global_split_id
                WHERE i.indicator_id = ?
            """, (indicator_id,)).fetchall()
            
            results = []
            for row in rows:
                res = dict(row)
                # Fetch years for each
                y_rows = conn.execute("SELECT year FROM global_split_years WHERE global_split_id = ?", (res['id'],)).fetchall()
                res['years'] = [yr['year'] for yr in y_rows]
                results.append(res)
            return results
        except sqlite3.Error as e:
            print(f"ERROR: {e}")
            return []

def get_all_global_splits(year: int = None) -> list[dict]:
    """Retrieves all global KPI split templates, optionally filtered by year."""
    db_templates_path = app_config.get_database_path("db_kpi_templates.db")
    
    query = "SELECT * FROM global_kpi_splits"
    params = []
    
    if year:
        query = """
            SELECT s.* FROM global_kpi_splits s
            JOIN global_split_years y ON s.id = y.global_split_id
            WHERE y.year = ?
        """
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
                
                # Fetch years for each split
                y_rows = conn.execute("SELECT year FROM global_split_years WHERE global_split_id = ?", (res['id'],)).fetchall()
                res['years'] = [yr['year'] for yr in y_rows]
                results.append(res)
            return results
        except sqlite3.Error as e:
            print(f"ERROR: Database error while retrieving all global splits. Details: {e}")
            return []
