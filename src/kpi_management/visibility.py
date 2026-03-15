import sqlite3
import traceback

from src.config import settings as app_config
from src.config.settings import get_database_path

def _get_db_kpis_path():
    return get_database_path('db_kpis.db')

def _validate_db_path(db_path_obj, db_name_str):
    """Validates if the provided DB path object is usable."""
    if not db_path_obj.exists():
        raise ConnectionError(f"Database file for {db_name_str} not found at {db_path_obj}")

def set_kpi_plant_visibility(kpi_id: int, plant_id: int, is_enabled: bool):
    """Sets or updates the visibility of a KPI for a specific plant.
    If the entry does not exist, it will be created.
    """
    _validate_db_path(_get_db_kpis_path(), "DB_KPIS")
    with sqlite3.connect(_get_db_kpis_path()) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO kpi_plant_visibility (kpi_id, plant_id, is_enabled) VALUES (?, ?, ?)",
                (kpi_id, plant_id, 1 if is_enabled else 0),
            )
            conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"Database error while setting KPI-Plant visibility: {e}") from e

def update_plant_visibility(kpi_id: int, visibility_data: list):
    """Updates visibility for multiple plants for a given KPI.
    visibility_data is a list of dicts: [{'plant_id': int, 'is_enabled': bool}]
    """
    _validate_db_path(_get_db_kpis_path(), "DB_KPIS")
    with sqlite3.connect(_get_db_kpis_path()) as conn:
        try:
            cursor = conn.cursor()
            for entry in visibility_data:
                cursor.execute(
                    "INSERT OR REPLACE INTO kpi_plant_visibility (kpi_id, plant_id, is_enabled) VALUES (?, ?, ?)",
                    (kpi_id, entry['plant_id'], 1 if entry['is_enabled'] else 0),
                )
            conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"Database error while updating KPI-Plant visibility: {e}") from e

def get_kpi_plant_visibility(kpi_id: int, plant_id: int) -> bool:
    """Gets the visibility status of a KPI for a specific plant.
    Returns True if enabled, False if disabled, and True if no specific entry exists (default).
    """
    _validate_db_path(_get_db_kpis_path(), "DB_KPIS")
    with sqlite3.connect(_get_db_kpis_path()) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_enabled FROM kpi_plant_visibility WHERE kpi_id = ? AND plant_id = ?",
            (kpi_id, plant_id),
        )
        row = cursor.fetchone()
        if row:
            return bool(row['is_enabled'])
        return True # Default to visible if no specific entry exists

def get_plant_visibility_for_kpi(kpi_id: int) -> list:
    """Returns a list of plant IDs for which a KPI has explicit visibility settings.
    Each item in the list is a dictionary with 'plant_id' and 'is_enabled'.
    """
    _validate_db_path(_get_db_kpis_path(), "DB_KPIS")
    with sqlite3.connect(_get_db_kpis_path()) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT plant_id, is_enabled FROM kpi_plant_visibility WHERE kpi_id = ?",
            (kpi_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

def get_plants_for_kpi(kpi_id: int) -> list:
    """Alias for get_plant_visibility_for_kpi (legacy support)"""
    return get_plant_visibility_for_kpi(kpi_id)

def get_kpis_for_plant(plant_id: int) -> list:
    """Returns a list of KPI IDs for which a plant has explicit visibility settings.
    Each item in the list is a dictionary with 'kpi_id' and 'is_enabled'.
    """
    _validate_db_path(_get_db_kpis_path(), "DB_KPIS")
    with sqlite3.connect(_get_db_kpis_path()) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT kpi_id, is_enabled FROM kpi_plant_visibility WHERE plant_id = ?",
            (plant_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

def delete_kpi_plant_visibility(kpi_id: int, plant_id: int):
    """Deletes a specific KPI-plant visibility entry.
    This effectively reverts to the default visibility (True) for that pair.
    """
    _validate_db_path(_get_db_kpis_path(), "DB_KPIS")
    with sqlite3.connect(_get_db_kpis_path()) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM kpi_plant_visibility WHERE kpi_id = ? AND plant_id = ?",
                (kpi_id, plant_id),
            )
            conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"Database error while deleting KPI-Plant visibility: {e}") from e
