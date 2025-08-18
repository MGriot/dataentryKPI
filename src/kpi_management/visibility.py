import sqlite3
import traceback

from src import app_config
from src.db_core.utils import get_database_path

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

def get_plants_for_kpi(kpi_id: int) -> list:
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

if __name__ == "__main__":
    print("--- Running kpi_management/visibility.py for testing ---")
    # Ensure app_config is set up for testing or use a test DB
    # For a real test, you'd want to create a temporary db_kpis.db and plants.db
    # and populate them with test data.

    # Example usage (requires a test setup with kpis and plants)
    # Assuming KPI ID 1 and Plant ID 1 exist for testing
    test_kpi_id = 1
    test_plant_id = 1

    try:
        print(f"Setting KPI {test_kpi_id} for Plant {test_plant_id} to disabled...")
        set_kpi_plant_visibility(test_kpi_id, test_plant_id, False)
        is_visible = get_kpi_plant_visibility(test_kpi_id, test_plant_id)
        print(f"Is KPI {test_kpi_id} visible for Plant {test_plant_id}? {is_visible}")
        assert not is_visible

        print(f"Setting KPI {test_kpi_id} for Plant {test_plant_id} to enabled...")
        set_kpi_plant_visibility(test_kpi_id, test_plant_id, True)
        is_visible = get_kpi_plant_visibility(test_kpi_id, test_plant_id)
        print(f"Is KPI {test_kpi_id} visible for Plant {test_plant_id}? {is_visible}")
        assert is_visible

        print(f"Getting all plants for KPI {test_kpi_id}...")
        plants_for_kpi = get_plants_for_kpi(test_kpi_id)
        print(f"Plants for KPI {test_kpi_id}: {plants_for_kpi}")

        print(f"Deleting visibility for KPI {test_kpi_id} and Plant {test_plant_id}...")
        delete_kpi_plant_visibility(test_kpi_id, test_plant_id)
        is_visible = get_kpi_plant_visibility(test_kpi_id, test_plant_id)
        print(f"Is KPI {test_kpi_id} visible for Plant {test_plant_id} after deletion? {is_visible}")
        assert is_visible # Should revert to default True

    except Exception as e:
        print(f"An error occurred during testing: {e}")
        print(traceback.format_exc())