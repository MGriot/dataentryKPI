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

def get_kpi_indicators_by_subgroup(subgroup_id: int) -> list[dict]:
    """
    Legacy support for retrieving KPI indicators by subgroup_id.
    """
    return get_kpi_indicators_by_node(subgroup_id + 1000) # Assuming the 1000 offset migration


if __name__ == "__main__":
    print("--- Running kpi_management/indicators.py for testing ---")

    # This test block assumes that:
    # 1. app_config.py is findable and all DB paths are defined.
    # 2. The databases exist and are writable. For robust testing, a dedicated test setup is ideal.
    # 3. Related tables (kpi_groups, kpi_subgroups, kpis) might need entries for full testing.

    # --- Test Setup ---
    # For simplicity, we'll assume a subgroup ID 1 exists. In a real test suite,
    # you'd create test groups and subgroups first.
    TEST_SUBGROUP_ID = 1 # Example, ensure this exists or create it for testing.
    indicator_id_test = None
    kpi_spec_id_for_test_indicator = None

    # Helper to set up a minimal kpi_nodes for testing
    def setup_minimal_parent_tables_for_indicators(db_path, node_id_to_ensure):
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS kpi_nodes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, parent_id INTEGER, node_type TEXT, FOREIGN KEY (parent_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE, UNIQUE (name, parent_id));")
            cur.execute("INSERT OR IGNORE INTO kpi_nodes (id, name, node_type) VALUES (?, ?, ?)", (node_id_to_ensure, f"Test Node {node_id_to_ensure}", "subgroup"))
            # Ensure kpis table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kpis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, indicator_id INTEGER NOT NULL UNIQUE, description TEXT,
                    calculation_type TEXT NOT NULL CHECK(calculation_type IN ('Incremental', 'Average')),
                    unit_of_measure TEXT, visible BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE,
                    UNIQUE (indicator_id) );
            """)
            # Ensure kpi_indicators table (this module's target)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kpi_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, node_id INTEGER NOT NULL,
                    subgroup_id INTEGER,
                    FOREIGN KEY (node_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE,
                    UNIQUE (name, node_id));
            """)
            conn.commit()

    # Save original app_config settings for database paths
    original_db_base_dir = app_config.SETTINGS["database_base_dir"]

    # Override app_config's database_base_dir for this test if needed
    test_db_file_kpis = "test_indicators_kpis.sqlite"
    test_db_file_targets = "test_indicators_targets.sqlite"
    test_db_file_days = "test_indicators_days.sqlite"
    test_db_file_weeks = "test_indicators_weeks.sqlite"
    test_db_file_months = "test_indicators_months.sqlite"
    test_db_file_quarters = "test_indicators_quarters.sqlite"

    # Create dummy DB files for testing if they don't exist
    for db_file in [test_db_file_kpis, test_db_file_targets, test_db_file_days, test_db_file_weeks, test_db_file_months, test_db_file_quarters]:
        if not Path(db_file).exists():
            Path(db_file).touch()

    # Temporarily set app_config to use the test files' directory
    app_config.SETTINGS["database_base_dir"] = str(Path(test_db_file_kpis).parent)

    # Setup minimal parent tables for indicators
    setup_minimal_parent_tables_for_indicators(app_config.get_database_path("db_kpis.db"), TEST_SUBGROUP_ID)

    try:
        print(f"\nTest 1: Add new indicator 'Revenue' to node {TEST_SUBGROUP_ID}")
        indicator_id_test = add_kpi_indicator("Revenue", TEST_SUBGROUP_ID)
        assert isinstance(indicator_id_test, int), "add_kpi_indicator should return an int."
        print(f"  SUCCESS: Added 'Revenue' with ID {indicator_id_test}")

        # Add a corresponding kpis spec for deletion test
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO kpis (indicator_id, calculation_type, unit_of_measure) VALUES (?, ?, ?)",
                (indicator_id_test, "Incremental", "EUR")
            )
            kpi_spec_id_for_test_indicator = cur.lastrowid
            conn.commit()
            print(f"  Added dummy kpis spec with ID {kpi_spec_id_for_test_indicator} for indicator {indicator_id_test}")

        print("\nTest 2: Attempt to add duplicate indicator 'Revenue' to same subgroup (should return existing ID)")
        existing_id = add_kpi_indicator("Revenue", TEST_SUBGROUP_ID)
        assert existing_id == indicator_id_test, "Duplicate add should return existing ID."
        print(f"  SUCCESS: Duplicate add returned existing ID {existing_id}.")

        print(f"\nTest 3: Update indicator ID {indicator_id_test} to 'Net Revenue' in node {TEST_SUBGROUP_ID}")
        update_kpi_indicator(indicator_id_test, "Net Revenue", TEST_SUBGROUP_ID)
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            name = conn.execute("SELECT name FROM kpi_indicators WHERE id = ?", (indicator_id_test,)).fetchone()[0]
            assert name == "Net Revenue", "Indicator name was not updated."
        print(f"  SUCCESS: Indicator ID {indicator_id_test} updated.")

        # Test 4: Delete the indicator
        # This will also test the cleanup of related kpis spec and (mocked/empty) target data
        print(f"\nTest 4: Delete indicator ID {indicator_id_test} ('Net Revenue')")
        # Add some dummy data to related tables to check deletion
        if kpi_spec_id_for_test_indicator:
            with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn_t:
                conn_t.execute("INSERT OR IGNORE INTO annual_targets (kpi_id, year) VALUES (?, ?)", (kpi_spec_id_for_test_indicator, 2023))
                conn_t.commit()
            with sqlite3.connect(app_config.get_database_path("db_kpi_days.db")) as conn_d:
                conn_d.execute("INSERT OR IGNORE INTO daily_targets (kpi_id, date_value) VALUES (?, ?)", (kpi_spec_id_for_test_indicator, "2023-01-01"))
                conn_d.commit()

        delete_kpi_indicator(indicator_id_test)
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            row = conn.execute("SELECT name FROM kpi_indicators WHERE id = ?", (indicator_id_test,)).fetchone()
            assert row is None, "Indicator was not deleted from kpi_indicators."
            if kpi_spec_id_for_test_indicator:
                spec_row = conn.execute("SELECT id FROM kpis WHERE id = ?", (kpi_spec_id_for_test_indicator,)).fetchone()
                assert spec_row is None, "Associated kpis spec was not deleted by cascade."
        # Check other DBs
        if kpi_spec_id_for_test_indicator:
            with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn_t:
                target_row = conn_t.execute("SELECT id FROM annual_targets WHERE kpi_id = ?", (kpi_spec_id_for_test_indicator,)).fetchone()
                assert target_row is None, "Annual target was not deleted."
            with sqlite3.connect(app_config.get_database_path("db_kpi_days.db")) as conn_d:
                day_row = conn_d.execute("SELECT id FROM daily_targets WHERE kpi_id = ?", (kpi_spec_id_for_test_indicator,)).fetchone()
                assert day_row is None, "Daily target was not deleted."

        print(f"  SUCCESS: Indicator ID {indicator_id_test} and its related data (kpis spec, targets) deleted.")
        indicator_id_test = None # Mark as deleted

        print("\n--- All kpi_management.indicators tests passed (basic execution) ---")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED DURING TESTING (kpi_management.indicators) ---")
        print(str(e))
        print(traceback.format_exc())
    finally:
        # Cleanup test database files if they were created
        test_db_files = [
            test_db_file_kpis, test_db_file_targets,
            test_db_file_days, test_db_file_weeks,
            test_db_file_months, test_db_file_quarters
        ]
        import os
        for test_db_file in test_db_files:
            if os.path.exists(test_db_file):
                try:
                    os.remove(test_db_file)
                    print(f"INFO: Cleaned up test file: {test_db_file}")
                except OSError as e_clean:
                    print(f"ERROR: Could not clean up test file {test_db_file}: {e_clean}")
        # Restore original app_config setting
        app_config.SETTINGS["database_base_dir"] = original_db_base_dir
