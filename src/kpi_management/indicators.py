# your_project_root/kpi_management/indicators.py
import sqlite3
import traceback

# Configuration import
try:
    from app_config import (
        DB_KPIS,
        DB_TARGETS,
        DB_KPI_DAYS,
        DB_KPI_WEEKS,
        DB_KPI_MONTHS,
        DB_KPI_QUARTERS
    )
except ImportError:
    print(
        "CRITICAL WARNING: app_config.py not found on PYTHONPATH. "
        "Database paths will not be correctly defined. "
        "Ensure your project's root directory is in PYTHONPATH or adjust imports."
    )
    # Define placeholders
    DB_KPIS = ":memory_kpis_indicators_error:"
    DB_TARGETS = ":memory_targets_indicators_error:"
    DB_KPI_DAYS = ":memory_days_indicators_error:"
    DB_KPI_WEEKS = ":memory_weeks_indicators_error:"
    DB_KPI_MONTHS = ":memory_months_indicators_error:"
    DB_KPI_QUARTERS = ":memory_quarters_indicators_error:"

# --- KPI Indicator CRUD Operations ---

def add_kpi_indicator(name: str, subgroup_id: int) -> int:
    """
    Adds a new KPI indicator to a specific subgroup.

    Args:
        name (str): The name of the KPI indicator. Must be unique within the subgroup.
        subgroup_id (int): The ID of the subgroup this indicator belongs to.

    Returns:
        int: The ID of the newly created KPI indicator.
             If an indicator with the same name already exists in the subgroup,
             its existing ID is returned.

    Raises:
        sqlite3.IntegrityError: If `subgroup_id` does not exist or for other integrity issues
                                (but duplicate name/subgroup is handled by returning existing ID).
        Exception: For other database errors.
    """
    db_kpis_str = str(DB_KPIS)
    if db_kpis_str.startswith(":memory_") or "error_db" in db_kpis_str:
         raise ConnectionError(f"DB_KPIS is not properly configured ({DB_KPIS}). Cannot add indicator.")

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)",
                (name, subgroup_id),
            )
            conn.commit()
            indicator_id = cursor.lastrowid
            print(f"INFO: KPI Indicator '{name}' (subgroup {subgroup_id}) added successfully with ID: {indicator_id}.")
            return indicator_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kpi_indicators.name, kpi_indicators.subgroup_id" in str(e) or \
               "UNIQUE constraint failed: kpi_indicators.subgroup_id, kpi_indicators.name" in str(e) : # Order might vary
                # Indicator with this name already exists in this subgroup, fetch and return its ID
                print(f"INFO: KPI Indicator '{name}' already exists in subgroup {subgroup_id}. Fetching existing ID.")
                cursor.execute(
                    "SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?",
                    (name, subgroup_id),
                )
                existing_row = cursor.fetchone()
                if existing_row:
                    existing_id = existing_row[0]
                    print(f"  Found existing indicator ID: {existing_id}")
                    return existing_id
                else:
                    # This case should ideally not happen if the UNIQUE constraint was the cause.
                    print(f"ERROR: IntegrityError for indicator '{name}' in subgroup {subgroup_id}, "
                          "but could not find existing entry after error. This is unexpected.")
                    raise # Re-raise the original integrity error
            elif "FOREIGN KEY constraint failed" in str(e):
                print(f"ERROR: Could not add KPI indicator '{name}'. Subgroup ID {subgroup_id} likely does not exist. Details: {e}")
                raise
            else:
                print(f"ERROR: IntegrityError while adding KPI indicator '{name}'. Details: {e}")
                raise
        except sqlite3.Error as e_general:
            print(f"ERROR: Database error while adding KPI indicator '{name}'. Details: {e_general}")
            print(traceback.format_exc())
            raise Exception(f"A database error occurred while adding KPI indicator '{name}'.") from e_general


def update_kpi_indicator(indicator_id: int, new_name: str, subgroup_id: int):
    """
    Updates the name and/or subgroup of an existing KPI indicator.

    Args:
        indicator_id (int): The ID of the KPI indicator to update.
        new_name (str): The new name for the KPI indicator.
        subgroup_id (int): The new subgroup ID for the KPI indicator.

    Raises:
        sqlite3.IntegrityError: If the new name already exists in the new subgroup,
                                or if the new subgroup_id is invalid.
        Exception: If the indicator_id does not exist or for other database errors.
    """
    if DB_KPIS.startswith(":memory_") or "error_db" in str(DB_KPIS):
         raise ConnectionError(f"DB_KPIS is not properly configured ({DB_KPIS}). Cannot update indicator.")

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE kpi_indicators SET name = ?, subgroup_id = ? WHERE id = ?",
                (new_name, subgroup_id, indicator_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(f"WARNING: No KPI indicator found with ID {indicator_id}. Update had no effect.")
                # Consider raising ValueError here if an update on non-existent ID is critical
            else:
                print(f"INFO: KPI indicator ID {indicator_id} updated to name '{new_name}' and subgroup {subgroup_id}.")
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                print(f"ERROR: Could not update KPI indicator ID {indicator_id}. "
                      f"The name '{new_name}' might already exist in subgroup {subgroup_id}. Details: {e}")
            elif "FOREIGN KEY constraint failed" in str(e):
                 print(f"ERROR: Could not update KPI indicator ID {indicator_id}. "
                      f"The new subgroup ID {subgroup_id} likely does not exist. Details: {e}")
            else:
                print(f"ERROR: IntegrityError while updating KPI indicator ID {indicator_id}. Details: {e}")
            raise
        except sqlite3.Error as e_general:
            print(f"ERROR: Database error while updating KPI indicator ID {indicator_id}. Details: {e_general}")
            print(traceback.format_exc())
            raise Exception(f"A database error occurred while updating KPI indicator ID {indicator_id}.") from e_general


def delete_kpi_indicator(indicator_id: int):
    """
    Deletes a KPI indicator. This is a critical operation that also triggers:
    1. Deletion of the corresponding kpis record (KPI specification) via ON DELETE CASCADE.
    2. Before (or as part of) kpis record deletion, associated data must be cleaned:
        - kpi_master_sub_links related to the kpis.id (handled by ON DELETE CASCADE from kpis table).
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
        "DB_KPIS": DB_KPIS, "DB_TARGETS": DB_TARGETS, "DB_KPI_DAYS": DB_KPI_DAYS,
        "DB_KPI_WEEKS": DB_KPI_WEEKS, "DB_KPI_MONTHS": DB_KPI_MONTHS, "DB_KPI_QUARTERS": DB_KPI_QUARTERS
    }
    for name, path_obj in db_paths_to_check.items():
        path_str = str(path_obj)
        if path_str.startswith(":memory_") or "error_db" in path_str:
            raise ConnectionError(f"{name} is not properly configured ({path_str}). Cannot delete indicator fully.")


    kpi_spec_id_to_delete = None
    try:
        # Step 1: Find the kpis.id (kpi_spec_id) associated with this kpi_indicators.id
        with sqlite3.connect(DB_KPIS) as conn_kpis_read:
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

        # Delete from annual_targets (DB_TARGETS)
        try:
            with sqlite3.connect(DB_TARGETS) as conn_targets:
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
            (DB_KPI_DAYS, "daily_targets"),
            (DB_KPI_WEEKS, "weekly_targets"),
            (DB_KPI_MONTHS, "monthly_targets"),
            (DB_KPI_QUARTERS, "quarterly_targets"),
        ]
        for db_path_del, table_name_del in periodic_dbs_info:
            try:
                with sqlite3.connect(db_path_del) as conn_periodic:
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
        
        # Note: kpi_master_sub_links cleanup is handled by ON DELETE CASCADE
        # when the 'kpis' record (kpi_spec_id_to_delete) is deleted.
        # This cascade happens when 'kpi_indicators' record (indicator_id) is deleted,
        # which in turn cascades to 'kpis'.
        print(f"  Data cleanup for KPI Spec ID {kpi_spec_id_to_delete} completed.")


    # Step 3: Delete the kpi_indicator itself.
    # This will also trigger ON DELETE CASCADE for the associated kpis record (if any was left or found),
    # which in turn triggers ON DELETE CASCADE for kpi_master_sub_links.
    print(f"  Proceeding to delete kpi_indicators entry for ID {indicator_id}.")
    with sqlite3.connect(DB_KPIS) as conn_kpis_delete:
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

    # Helper to set up a minimal kpi_groups and kpi_subgroups for testing
    def setup_minimal_parent_tables_for_indicators(db_path, subgroup_id_to_ensure):
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            # Ensure kpi_groups table and a group
            cur.execute("CREATE TABLE IF NOT EXISTS kpi_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);")
            cur.execute("INSERT OR IGNORE INTO kpi_groups (id, name) VALUES (?, ?)", (1, "Test Group for Indicators"))
            # Ensure kpi_subgroups table and the specific subgroup
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kpi_subgroups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, group_id INTEGER NOT NULL,
                    indicator_template_id INTEGER,
                    FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE, UNIQUE (name, group_id));
            """)
            cur.execute("INSERT OR IGNORE INTO kpi_subgroups (id, name, group_id) VALUES (?, ?, ?)",
                        (subgroup_id_to_ensure, f"Test Subgroup {subgroup_id_to_ensure}", 1))
            # Ensure kpis table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kpis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, indicator_id INTEGER NOT NULL, description TEXT,
                    calculation_type TEXT NOT NULL CHECK(calculation_type IN ('Incrementale', 'Media')),
                    unit_of_measure TEXT, visible BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE,
                    UNIQUE (indicator_id) );
            """)
            # Ensure kpi_indicators table (this module's target)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kpi_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subgroup_id INTEGER NOT NULL,
                    FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE,
                    UNIQUE (name, subgroup_id));
            """)
            conn.commit()

    if any(db_path.startswith(":memory_") or "error_db" in str(db_path) for db_path in [DB_KPIS, DB_TARGETS, DB_KPI_DAYS]):
        print("WARNING: One or more database paths are placeholders. Testing might be limited or use in-memory instances.")
        # For :memory: or placeholder, attempt to set up minimal kpi_indicators related schema in DB_KPIS
        if DB_KPIS.startswith(":memory_") or "error_db" in str(DB_KPIS):
             DB_KPIS_TEST_FILE = "test_indicators_kpis.sqlite"
             print(f"INFO: Using '{DB_KPIS_TEST_FILE}' for DB_KPIS during testing.")
             setup_minimal_parent_tables_for_indicators(DB_KPIS_TEST_FILE, TEST_SUBGROUP_ID)
             # Overwrite DB_KPIS for the scope of this test only
             DB_KPIS_ORIGINAL = DB_KPIS
             DB_KPIS = DB_KPIS_TEST_FILE
        # Similar minimal setup for other DBs if needed for delete test, e.g., creating dummy tables
        for db_path_placeholder_check in [DB_TARGETS, DB_KPI_DAYS, DB_KPI_WEEKS, DB_KPI_MONTHS, DB_KPI_QUARTERS]:
            if db_path_placeholder_check.startswith(":memory_") or "error_db" in str(db_path_placeholder_check):
                temp_db_file = f"test_indicators_{db_path_placeholder_check.split('_')[1]}.sqlite" # e.g. test_indicators_targets.sqlite
                print(f"INFO: Initializing dummy table in '{temp_db_file}' for {db_path_placeholder_check}")
                with sqlite3.connect(temp_db_file) as conn_other_db:
                    if "targets" in temp_db_file:
                        conn_other_db.execute("CREATE TABLE IF NOT EXISTS annual_targets (id INTEGER PRIMARY KEY, kpi_id INTEGER, year INTEGER);")
                    elif "days" in temp_db_file:
                        conn_other_db.execute("CREATE TABLE IF NOT EXISTS daily_targets (id INTEGER PRIMARY KEY, kpi_id INTEGER, date_value TEXT);")
                    # Add for weeks, months, quarters similarly
                if db_path_placeholder_check == DB_TARGETS: DB_TARGETS = temp_db_file
                if db_path_placeholder_check == DB_KPI_DAYS: DB_KPI_DAYS = temp_db_file
                # ... and so on for other DBs


    try:
        print(f"\nTest 1: Add new indicator 'Revenue' to subgroup {TEST_SUBGROUP_ID}")
        indicator_id_test = add_kpi_indicator("Revenue", TEST_SUBGROUP_ID)
        assert isinstance(indicator_id_test, int), "add_kpi_indicator should return an int."
        print(f"  SUCCESS: Added 'Revenue' with ID {indicator_id_test}")

        # Add a corresponding kpis spec for deletion test
        with sqlite3.connect(DB_KPIS) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO kpis (indicator_id, calculation_type, unit_of_measure) VALUES (?, ?, ?)",
                (indicator_id_test, "Incrementale", "EUR")
            )
            kpi_spec_id_for_test_indicator = cur.lastrowid
            conn.commit()
            print(f"  Added dummy kpis spec with ID {kpi_spec_id_for_test_indicator} for indicator {indicator_id_test}")

        print("\nTest 2: Attempt to add duplicate indicator 'Revenue' to same subgroup (should return existing ID)")
        existing_id = add_kpi_indicator("Revenue", TEST_SUBGROUP_ID)
        assert existing_id == indicator_id_test, "Duplicate add should return existing ID."
        print(f"  SUCCESS: Duplicate add returned existing ID {existing_id}.")

        print(f"\nTest 3: Update indicator ID {indicator_id_test} to 'Net Revenue' in subgroup {TEST_SUBGROUP_ID}")
        update_kpi_indicator(indicator_id_test, "Net Revenue", TEST_SUBGROUP_ID)
        with sqlite3.connect(DB_KPIS) as conn:
            name = conn.execute("SELECT name FROM kpi_indicators WHERE id = ?", (indicator_id_test,)).fetchone()[0]
            assert name == "Net Revenue", "Indicator name was not updated."
        print(f"  SUCCESS: Indicator ID {indicator_id_test} updated.")

        # Test 4: Delete the indicator
        # This will also test the cleanup of related kpis spec and (mocked/empty) target data
        print(f"\nTest 4: Delete indicator ID {indicator_id_test} ('Net Revenue')")
        # Add some dummy data to related tables to check deletion
        if kpi_spec_id_for_test_indicator:
            with sqlite3.connect(DB_TARGETS) as conn_t:
                conn_t.execute("INSERT OR IGNORE INTO annual_targets (kpi_id, year) VALUES (?, ?)", (kpi_spec_id_for_test_indicator, 2023))
                conn_t.commit()
            with sqlite3.connect(DB_KPI_DAYS) as conn_d:
                conn_d.execute("INSERT OR IGNORE INTO daily_targets (kpi_id, date_value) VALUES (?, ?)", (kpi_spec_id_for_test_indicator, "2023-01-01"))
                conn_d.commit()

        delete_kpi_indicator(indicator_id_test)
        with sqlite3.connect(DB_KPIS) as conn:
            row = conn.execute("SELECT name FROM kpi_indicators WHERE id = ?", (indicator_id_test,)).fetchone()
            assert row is None, "Indicator was not deleted from kpi_indicators."
            if kpi_spec_id_for_test_indicator:
                spec_row = conn.execute("SELECT id FROM kpis WHERE id = ?", (kpi_spec_id_for_test_indicator,)).fetchone()
                assert spec_row is None, "Associated kpis spec was not deleted by cascade."
        # Check other DBs
        if kpi_spec_id_for_test_indicator:
            with sqlite3.connect(DB_TARGETS) as conn_t:
                target_row = conn_t.execute("SELECT id FROM annual_targets WHERE kpi_id = ?", (kpi_spec_id_for_test_indicator,)).fetchone()
                assert target_row is None, "Annual target was not deleted."
            with sqlite3.connect(DB_KPI_DAYS) as conn_d:
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
            "test_indicators_kpis.sqlite", "test_indicators_targets.sqlite",
            "test_indicators_days.sqlite", "test_indicators_weeks.sqlite",
            "test_indicators_months.sqlite", "test_indicators_quarters.sqlite"
        ]
        import os
        for test_db_file in test_db_files:
            if os.path.exists(test_db_file) and (DB_KPIS == test_db_file or DB_TARGETS == test_db_file or DB_KPI_DAYS == test_db_file) : # Be specific to avoid deleting wrong files
                try:
                    os.remove(test_db_file)
                    print(f"INFO: Cleaned up test file: {test_db_file}")
                except OSError as e_clean:
                    print(f"ERROR: Could not clean up test file {test_db_file}: {e_clean}")
        if 'DB_KPIS_ORIGINAL' in locals() and DB_KPIS_ORIGINAL: # Restore original DB_KPIS if it was overwritten for testing
            DB_KPIS = DB_KPIS_ORIGINAL