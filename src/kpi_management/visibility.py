import sqlite3
import traceback

import app_config
from db_core.utils import get_database_path

DB_KPIS = get_database_path('db_kpis.db')

def _validate_db_path(db_path_obj, db_name_str):
    """Validates if the provided DB path object is usable."""
    if not db_path_obj.exists():
        raise ConnectionError(f"Database file for {db_name_str} not found at {db_path_obj}")

def set_kpi_stabilimento_visibility(kpi_id: int, stabilimento_id: int, is_enabled: bool):
    """Sets or updates the visibility of a KPI for a specific stabilimento.
    If the entry does not exist, it will be created.
    """
    _validate_db_path(DB_KPIS, "DB_KPIS")
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO kpi_stabilimento_visibility (kpi_id, stabilimento_id, is_enabled) VALUES (?, ?, ?)",
                (kpi_id, stabilimento_id, 1 if is_enabled else 0),
            )
            conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"Errore database durante l'impostazione della visibilità KPI-Stabilimento: {e}") from e

def get_kpi_stabilimento_visibility(kpi_id: int, stabilimento_id: int) -> bool:
    """Gets the visibility status of a KPI for a specific stabilimento.
    Returns True if enabled, False if disabled, and True if no specific entry exists (default).
    """
    _validate_db_path(DB_KPIS, "DB_KPIS")
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_enabled FROM kpi_stabilimento_visibility WHERE kpi_id = ? AND stabilimento_id = ?",
            (kpi_id, stabilimento_id),
        )
        row = cursor.fetchone()
        if row:
            return bool(row['is_enabled'])
        return True # Default to visible if no specific entry exists

def get_stabilimenti_for_kpi(kpi_id: int) -> list:
    """Returns a list of stabilimento IDs for which a KPI has explicit visibility settings.
    Each item in the list is a dictionary with 'stabilimento_id' and 'is_enabled'.
    """
    _validate_db_path(DB_KPIS, "DB_KPIS")
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT stabilimento_id, is_enabled FROM kpi_stabilimento_visibility WHERE kpi_id = ?",
            (kpi_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

def get_kpis_for_stabilimento(stabilimento_id: int) -> list:
    """Returns a list of KPI IDs for which a stabilimento has explicit visibility settings.
    Each item in the list is a dictionary with 'kpi_id' and 'is_enabled'.
    """
    _validate_db_path(DB_KPIS, "DB_KPIS")
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT kpi_id, is_enabled FROM kpi_stabilimento_visibility WHERE stabilimento_id = ?",
            (stabilimento_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

def delete_kpi_stabilimento_visibility(kpi_id: int, stabilimento_id: int):
    """Deletes a specific KPI-stabilimento visibility entry.
    This effectively reverts to the default visibility (True) for that pair.
    """
    _validate_db_path(DB_KPIS, "DB_KPIS")
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM kpi_stabilimento_visibility WHERE kpi_id = ? AND stabilimento_id = ?",
                (kpi_id, stabilimento_id),
            )
            conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"Errore database durante l'eliminazione della visibilità KPI-Stabilimento: {e}") from e

if __name__ == "__main__":
    print("--- Running kpi_management/visibility.py for testing ---")
    # Ensure app_config is set up for testing or use a test DB
    # For a real test, you'd want to create a temporary db_kpis.db and stabilimenti.db
    # and populate them with test data.

    # Example usage (requires a test setup with kpis and stabilimenti)
    # Assuming KPI ID 1 and Stabilimento ID 1 exist for testing
    test_kpi_id = 1
    test_stabilimento_id = 1

    try:
        print(f"Setting KPI {test_kpi_id} for Stabilimento {test_stabilimento_id} to disabled...")
        set_kpi_stabilimento_visibility(test_kpi_id, test_stabilimento_id, False)
        is_visible = get_kpi_stabilimento_visibility(test_kpi_id, test_stabilimento_id)
        print(f"Is KPI {test_kpi_id} visible for Stabilimento {test_stabilimento_id}? {is_visible}")
        assert not is_visible

        print(f"Setting KPI {test_kpi_id} for Stabilimento {test_stabilimento_id} to enabled...")
        set_kpi_stabilimento_visibility(test_kpi_id, test_stabilimento_id, True)
        is_visible = get_kpi_stabilimento_visibility(test_kpi_id, test_stabilimento_id)
        print(f"Is KPI {test_kpi_id} visible for Stabilimento {test_stabilimento_id}? {is_visible}")
        assert is_visible

        print(f"Getting all stabilimenti for KPI {test_kpi_id}...")
        stabs_for_kpi = get_stabilimenti_for_kpi(test_kpi_id)
        print(f"Stabilimenti for KPI {test_kpi_id}: {stabs_for_kpi}")

        print(f"Deleting visibility for KPI {test_kpi_id} and Stabilimento {test_stabilimento_id}...")
        delete_kpi_stabilimento_visibility(test_kpi_id, test_stabilimento_id)
        is_visible = get_kpi_stabilimento_visibility(test_kpi_id, test_stabilimento_id)
        print(f"Is KPI {test_kpi_id} visible for Stabilimento {test_stabilimento_id} after deletion? {is_visible}")
        assert is_visible # Should revert to default True

    except Exception as e:
        print(f"An error occurred during testing: {e}")
        print(traceback.format_exc())
