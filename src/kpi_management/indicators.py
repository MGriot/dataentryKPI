# your_project_root/kpi_management/indicators.py
import sqlite3
import traceback
from src.config import settings as app_config
from pathlib import Path

# --- KPI Indicator CRUD Operations ---

def add_kpi_indicator(name: str, node_id: int) -> int:
    """
    Adds a new KPI indicator to a specific node in the recursive hierarchy.
    """
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_kpis_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_indicators (name, node_id) VALUES (?,?)",
                (name, node_id),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            cursor.execute("SELECT id FROM kpi_indicators WHERE name=? AND node_id=?", (name, node_id))
            row = cursor.fetchone()
            if row: return row[0]
            raise

def update_kpi_indicator(indicator_id: int, new_name: str, node_id: int):
    """
    Updates the name and/or parent node of an existing KPI indicator.
    """
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_kpis_path) as conn:
        try:
            conn.execute(
                "UPDATE kpi_indicators SET name = ?, node_id = ? WHERE id = ?",
                (new_name, node_id, indicator_id),
            )
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR (update_kpi_indicator): {e}")
            raise


def delete_kpi_indicator(indicator_id: int):
    """
    Deletes a KPI indicator. This is a critical operation that also triggers:
    1. Deletion of the corresponding kpis record (KPI specification) via ON DELETE CASCADE.
    2. Before (or as part of) kpis record deletion, associated data must be cleaned:
        - annual_targets for the kpis.id from DB_TARGETS (MANUAL DELETE REQUIRED).
        - periodic_targets (daily, weekly, monthly, quarterly) for the kpis.id
          from their respective databases (MANUAL DELETE REQUIRED).

    Args:
        indicator_id (int): The ID of the kpi_indicator to delete.

    Raises:
        Exception: If any part of the deletion process fails.
    """
    print(f"INFO: Initiating deletion of KPI Indicator ID: {indicator_id}")

    # Check if DB paths are configured
    db_paths_to_check = {
        "db_kpis.db": app_config.get_database_path("db_kpis.db"),
        "db_kpi_targets.db": app_config.get_database_path("db_kpi_targets.db"),
        "db_kpi_days.db": app_config.get_database_path("db_kpi_days.db"),
        "db_kpi_weeks.db": app_config.get_database_path("db_kpi_weeks.db"),
        "db_kpi_months.db": app_config.get_database_path("db_kpi_months.db"),
        "db_kpi_quarters.db": app_config.get_database_path("db_kpi_quarters.db"),
    }
    for name, path_obj in db_paths_to_check.items():
        if not isinstance(path_obj, Path) or not path_obj.parent.exists():
            raise ConnectionError(f"{name} is not properly configured ({path_obj}). Cannot delete indicator fully.")


    kpi_spec_id_to_delete = None
    try:
        # Step 1: Find the kpis.id (kpi_spec_id) associated with this kpi_indicators.id
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_kpis_read:
            # conn_kpis_read.row_factory = sqlite3.Row # Not strictly needed if only fetching one column
            kpi_spec_row = conn_kpis_read.execute(
                "SELECT id FROM kpis WHERE indicator_id = ?", (indicator_id,)
            ).fetchone()
            if kpi_spec_row:
                kpi_spec_id_to_delete = kpi_spec_row[0]
                print(f"  Found associated KPI Spec ID (kpis.id): {kpi_spec_id_to_delete} for indicator ID {indicator_id}.")
            else:
                print(f"  No KPI Spec (kpis record) found for indicator ID {indicator_id}. "
                      "This might mean it was already deleted or never created. "
                      "Proceeding to delete the indicator entry itself.")
    except sqlite3.Error as e:
        print(f"ERROR: Database error while fetching kpi_spec_id for indicator ID {indicator_id}. Details: {e}")
        print(traceback.format_exc())
        raise Exception(f"Failed to fetch kpi_spec_id for indicator {indicator_id} due to a database error.") from e

    # Step 2: If a kpi_spec_id was found, delete its related data from other tables
    if kpi_spec_id_to_delete:
        print(f"  Cleaning up data for KPI Spec ID: {kpi_spec_id_to_delete}...")

        # Delete from annual_targets (db_kpi_targets.db)
        try:
            with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn_targets:
                cursor_targets = conn_targets.cursor()
                cursor_targets.execute(
                    "DELETE FROM annual_targets WHERE kpi_id = ?", (kpi_spec_id_to_delete,)
                )
                conn_targets.commit()
                print(f"    Deleted {cursor_targets.rowcount} rows from annual_targets for kpi_id {kpi_spec_id_to_delete}.")
        except sqlite3.Error as e:
            print(f"ERROR: Failed to delete annual targets for kpi_spec_id {kpi_spec_id_to_delete}. Details: {e}")
            print(traceback.format_exc())
            raise Exception(f"Error deleting annual targets for kpi_spec_id {kpi_spec_id_to_delete}.") from e

        # Delete from periodic target tables
        periodic_dbs_info = [
            ("db_kpi_days.db", "daily_targets"),
            ("db_kpi_weeks.db", "weekly_targets"),
            ("db_kpi_months.db", "monthly_targets"),
            ("db_kpi_quarters.db", "quarterly_targets"),
        ]
        for db_file_name_del, table_name_del in periodic_dbs_info:
            try:
                with sqlite3.connect(app_config.get_database_path(db_file_name_del)) as conn_periodic:
                    cursor_periodic = conn_periodic.cursor()
                    cursor_periodic.execute(
                        f"DELETE FROM {table_name_del} WHERE kpi_id = ?",
                        (kpi_spec_id_to_delete,),
                    )
                    conn_periodic.commit()
                    print(f"    Deleted {cursor_periodic.rowcount} rows from {table_name_del} for kpi_id {kpi_spec_id_to_delete}.")
            except sqlite3.Error as e:
                print(f"ERROR: Failed to delete from {table_name_del} for kpi_spec_id {kpi_spec_id_to_delete}. Details: {e}")
                print(traceback.format_exc())
                raise Exception(f"Error deleting from {table_name_del} for kpi_spec_id {kpi_spec_id_to_delete}.") from e
        
        print(f"  Data cleanup for KPI Spec ID {kpi_spec_id_to_delete} completed.")


    # Step 3: Delete the kpi_indicator itself.
    # This will also trigger ON DELETE CASCADE for the associated kpis record (if any was left or found).
    print(f"  Proceeding to delete kpi_indicators entry for ID {indicator_id}.")
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_kpis_delete:
        try:
            conn_kpis_delete.execute("PRAGMA foreign_keys = ON;") # Ensure FKs are active
            cursor_delete_indicator = conn_kpis_delete.cursor()
            cursor_delete_indicator.execute(
                "DELETE FROM kpi_indicators WHERE id = ?", (indicator_id,)
            )
            conn_kpis_delete.commit()
            if cursor_delete_indicator.rowcount == 0:
                print(f"WARNING: No kpi_indicator with ID {indicator_id} found during the final delete step. It might have been deleted already.")
            else:
                print(f"INFO: KPI Indicator ID {indicator_id} (and its cascaded kpis spec and links) deleted successfully.")
        except sqlite3.Error as e:
            print(f"ERROR: Database error while deleting kpi_indicator ID {indicator_id}. Details: {e}")
            print(traceback.format_exc())
            raise Exception(f"Database error when deleting kpi_indicator ID {indicator_id}.") from e

    print(f"INFO: Deletion process for KPI Indicator ID {indicator_id} fully completed.")


def get_kpi_indicators_by_node(node_id: int) -> list[dict]:
    """
    Retrieves all KPI indicators for a given node ID in the recursive hierarchy.
    """
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_kpis_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, node_id, subgroup_id FROM kpi_indicators WHERE node_id = ? ORDER BY name",
                (node_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            print(f"ERROR: Database error while retrieving KPI indicators for node {node_id}. Details: {e}")
            raise
