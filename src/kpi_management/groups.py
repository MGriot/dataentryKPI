# your_project_root/kpi_management/groups.py
import sqlite3
import traceback

# Configuration import
# This assumes 'app_config.py' is in a directory that's part of your PYTHONPATH,
# typically the project root.
try:
    from app_config import DB_KPIS
except ImportError:
    # Fallback for scenarios where app_config might not be in the default path
    # (e.g., running this script standalone without proper project setup)
    # In a structured project, this import should work directly.
    print(
        "CRITICAL WARNING: app_config.py not found on PYTHONPATH. "
        "DB_KPIS will not be correctly defined. "
        "Ensure your project's root directory is in PYTHONPATH or adjust imports."
    )
    # Define a placeholder to allow the script to load, but operations will fail.
    DB_KPIS = (
        ":memory:"  # Or some other placeholder like "error_db_kpis_not_found.sqlite"
    )


# Function imports from other modules
_data_retriever_available = False
_indicators_module_available = False

try:
    # Assumes data_retriever.py is at the project root, accessible via PYTHONPATH
    from data_retriever import get_kpi_subgroups_by_group_revised

    _data_retriever_available = True
except ImportError:
    print(
        "WARNING: Could not import 'get_kpi_subgroups_by_group_revised' from 'data_retriever'. "
        "The 'delete_kpi_group' function will be non-operational. "
        "Ensure data_retriever.py is in your PYTHONPATH."
    )

    # Define a mock function if not available, so the script can load for other functions
    def get_kpi_subgroups_by_group_revised(group_id):
        print(
            f"MOCK ALERT: 'get_kpi_subgroups_by_group_revised({group_id})' called - data_retriever not loaded."
        )
        return []


try:
    # Relative import for a sibling module 'indicators.py' within the 'kpi_management' package
    from .indicators import delete_kpi_indicator

    _indicators_module_available = True
except ImportError:
    # This might happen if indicators.py doesn't exist yet or if this script is run
    # in a way that Python doesn't recognize 'kpi_management' as a package.
    print(
        "WARNING: Could not import 'delete_kpi_indicator' from '.indicators'. "
        "The 'delete_kpi_group' function will be non-operational. "
        "Ensure indicators.py exists in the same kpi_management package."
    )

    def delete_kpi_indicator(indicator_id):
        print(
            f"MOCK ALERT: 'delete_kpi_indicator({indicator_id})' called - indicators module not loaded."
        )
        pass


# --- KPI Group CRUD Operations ---


def add_kpi_group(name: str) -> int:
    """
    Adds a new KPI group to the database.

    Args:
        name (str): The name of the KPI group. Must be unique.

    Returns:
        int: The ID of the newly created KPI group.

    Raises:
        sqlite3.IntegrityError: If the group name already exists.
        Exception: For other database errors.
    """
    db_kpis_str = str(DB_KPIS)
    if db_kpis_str == ":memory:" or "error_db_kpis_not_found" in db_kpis_str:
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({DB_KPIS}). Cannot add group."
        )

    with sqlite3.connect(str(DB_KPIS)) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO kpi_groups (name) VALUES (?)", (name,))
            conn.commit()
            group_id = cursor.lastrowid
            print(f"INFO: KPI group '{name}' added successfully with ID: {group_id}.")
            return group_id
        except sqlite3.IntegrityError as e:
            # This typically means "UNIQUE constraint failed: kpi_groups.name"
            print(
                f"ERROR: Could not add KPI group '{name}'. It likely already exists. Details: {e}"
            )
            raise
        except sqlite3.Error as e:
            print(
                f"ERROR: Database error while adding KPI group '{name}'. Details: {e}"
            )
            print(traceback.format_exc())
            raise Exception(
                f"A database error occurred while adding KPI group '{name}'."
            ) from e


def update_kpi_group(group_id: int, new_name: str):
    """
    Updates the name of an existing KPI group.

    Args:
        group_id (int): The ID of the KPI group to update.
        new_name (str): The new unique name for the KPI group.

    Raises:
        sqlite3.IntegrityError: If the new name already exists for another group.
        Exception: If the group_id does not exist or for other database errors.
    """
    db_kpis_str = str(DB_KPIS)
    if db_kpis_str == ":memory:" or "error_db_kpis_not_found" in db_kpis_str:
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({DB_KPIS}). Cannot update group."
        )

    with sqlite3.connect(str(DB_KPIS)) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE kpi_groups SET name = ? WHERE id = ?", (new_name, group_id)
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No KPI group found with ID {group_id}. Update had no effect."
                )
                # Depending on desired behavior, you might raise an error here
                # raise ValueError(f"KPI group with ID {group_id} not found for update.")
            else:
                print(f"INFO: KPI group ID {group_id} updated to '{new_name}'.")
        except sqlite3.IntegrityError as e:
            print(
                f"ERROR: Could not update KPI group ID {group_id} to '{new_name}'. New name might already exist. Details: {e}"
            )
            raise
        except sqlite3.Error as e:
            print(
                f"ERROR: Database error while updating KPI group ID {group_id}. Details: {e}"
            )
            print(traceback.format_exc())
            raise Exception(
                f"A database error occurred while updating KPI group ID {group_id}."
            ) from e


def delete_kpi_group(group_id: int):
    """
    Deletes a KPI group and all its associated subgroups and indicators.
    This function first explicitly deletes all indicators belonging to the group's
    subgroups to ensure all related data (kpis specs, targets across DBs)
    is cleaned up by `delete_kpi_indicator`. Then, it deletes the group,
    allowing SQLite's `ON DELETE CASCADE` to remove the subgroups.

    Args:
        group_id (int): The ID of the KPI group to delete.

    Raises:
        ImportError: If required functions from other modules are not available.
        Exception: If any part of the deletion process fails.
    """
    print(f"INFO: Initiating deletion of KPI group ID {group_id} and its contents.")

    if not _data_retriever_available or not _indicators_module_available:
        missing = []
        if not _data_retriever_available:
            missing.append("data_retriever.get_kpi_subgroups_by_group_revised")
        if not _indicators_module_available:
            missing.append("kpi_management.indicators.delete_kpi_indicator")
        msg = f"ERROR: Cannot proceed with delete_kpi_group. Missing dependencies: {', '.join(missing)}."
        print(msg)
        raise ImportError(msg)

    db_kpis_str = str(DB_KPIS)
    if db_kpis_str == ":memory:" or "error_db_kpis_not_found" in db_kpis_str:
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({DB_KPIS}). Cannot delete group."
        )

    indicators_to_delete_ids = []
    try:
        # Get all subgroups for the group
        subgroups_in_group = get_kpi_subgroups_by_group_revised(group_id)
        if not subgroups_in_group:
            print(f"INFO: KPI group ID {group_id} has no subgroups.")
        else:
            print(
                f"INFO: Found {len(subgroups_in_group)} subgroups for group ID {group_id}."
            )

        # Collect all indicator IDs from these subgroups
        with sqlite3.connect(str(DB_KPIS)) as conn_read:
            conn_read.row_factory = sqlite3.Row
            for sg_dict in subgroups_in_group:
                print(
                    f"  Checking indicators in subgroup ID {sg_dict['id']} ('{sg_dict['name']}')..."
                )
                indicators_rows = conn_read.execute(
                    "SELECT id FROM kpi_indicators WHERE subgroup_id = ?",
                    (sg_dict["id"],),
                ).fetchall()
                for ind_row in indicators_rows:
                    indicators_to_delete_ids.append(ind_row["id"])
            print(
                f"  Collected {len(indicators_to_delete_ids)} indicator IDs for explicit deletion."
            )

    except sqlite3.Error as e:
        print(
            f"ERROR: Database error while collecting indicators for group ID {group_id} deletion. Details: {e}"
        )
        print(traceback.format_exc())
        raise Exception(
            f"Failed to collect indicators for group ID {group_id} due to a database error."
        ) from e
    except (
        Exception
    ) as e:  # Catch other errors (e.g., from data_retriever if it raises one)
        print(
            f"ERROR: Unexpected error while preparing to delete group ID {group_id}. Details: {e}"
        )
        print(traceback.format_exc())
        raise

    # Explicitly delete each indicator. `delete_kpi_indicator` handles cleanup
    # of its kpis spec and related target data from other databases.
    for ind_id in indicators_to_delete_ids:
        try:
            print(f"  Calling delete_kpi_indicator for indicator ID: {ind_id}")
            delete_kpi_indicator(
                ind_id
            )  # This must be robust and handle its own connections
        except Exception as e:
            # Log the error. Deciding whether to continue or halt is important.
            # For a critical operation like this, it's safer to halt and report.
            print(
                f"CRITICAL ERROR: Failed to delete indicator ID {ind_id} (part of group ID {group_id}). Halting group deletion. Details: {e}"
            )
            print(traceback.format_exc())
            raise Exception(
                f"Failed to delete child indicator ID {ind_id} for group {group_id}. Group deletion incomplete."
            ) from e

    # After all associated indicators (and their kpis specs, targets) are gone,
    # delete the kpi_group itself. SQLite's `ON DELETE CASCADE` from kpi_groups
    # to kpi_subgroups will clean up the (now empty of indicators) subgroups.
    print(f"INFO: Proceeding to delete the kpi_groups entry for ID {group_id}.")
    with sqlite3.connect(str(DB_KPIS)) as conn_delete_group:
        try:
            conn_delete_group.execute("PRAGMA foreign_keys = ON;")
            cursor = conn_delete_group.cursor()
            cursor.execute("DELETE FROM kpi_groups WHERE id = ?", (group_id,))
            conn_delete_group.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No KPI group with ID {group_id} found during the final delete step. It might have been deleted already or never existed."
                )
            else:
                print(
                    f"INFO: KPI group ID {group_id} and its associated subgroups (via cascade) deleted successfully."
                )
        except sqlite3.Error as e:
            print(
                f"ERROR: Database error while deleting the main entry for group ID {group_id}. Details: {e}"
            )
            print(traceback.format_exc())
            # At this point, child indicators might be deleted, but the group itself failed.
            raise Exception(
                f"Database error when deleting the kpi_groups entry for ID {group_id}."
            ) from e


if __name__ == "__main__":
    print("--- Running kpi_management/groups.py for testing ---")

    # This test block assumes that:
    # 1. app_config.py is findable and DB_KPIS is defined.
    # 2. data_retriever.py and kpi_management/indicators.py are available
    #    with their respective functions, or their mocks will be used.
    # 3. The database specified by DB_KPIS exists and is writable.
    #    For a clean test, it's best to use a temporary/test database.

    # --- Test Setup ---
    # For robust testing, you'd ideally use a dedicated test database.
    # Here, we'll try to use the configured DB_KPIS.
    # If using a real DB, be CAREFUL as this script PERFORMS DELETIONS.

    if (
        DB_KPIS == ":memory:"
        or "error_db_kpis_not_found" in str(DB_KPIS)
        or "placeholder" in str(DB_KPIS)
    ):
        print(
            "INFO: Using in-memory database for testing or placeholder DB. Re-initializing tables."
        )
        # Re-initialize basic tables for kpi_groups for testing if mocks are active
        try:
            with sqlite3.connect(
                str(DB_KPIS) if DB_KPIS != ":memory:" else "test_groups_module.sqlite"
            ) as conn_test_setup:  # Use a file for :memory: persistence during test
                if DB_KPIS == ":memory:":
                    DB_KPIS = "test_groups_module.sqlite"  # for cleanup
                cursor_setup = conn_test_setup.cursor()
                cursor_setup.execute("DROP TABLE IF EXISTS kpi_indicators;")
                cursor_setup.execute("DROP TABLE IF EXISTS kpi_subgroups;")
                cursor_setup.execute("DROP TABLE IF EXISTS kpi_groups;")
                cursor_setup.execute(
                    "CREATE TABLE kpi_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);"
                )
                cursor_setup.execute(
                    """CREATE TABLE kpi_subgroups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, group_id INTEGER NOT NULL,
                        indicator_template_id INTEGER,
                        FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE, UNIQUE (name, group_id));"""
                )
                cursor_setup.execute(
                    """CREATE TABLE kpi_indicators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subgroup_id INTEGER NOT NULL,
                        FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE, UNIQUE (name, subgroup_id));"""
                )
                conn_test_setup.commit()
            print(f"INFO: Test tables re-created in {DB_KPIS}")
        except Exception as e_setup:
            print(
                f"ERROR: Could not set up test tables in {DB_KPIS}. Testing aborted. Error: {e_setup}"
            )
            exit(1)

    print(f"INFO: Data Retriever Available: {_data_retriever_available}")
    print(f"INFO: Indicators Module Available: {_indicators_module_available}")
    if not _data_retriever_available or not _indicators_module_available:
        print("WARNING: Some operations in delete_kpi_group will use mock functions.")

    g_id = None
    try:
        # Test 1: Add a new group
        print("\nTest 1: Add new group 'Finance'")
        g_id = add_kpi_group("Finance")
        assert isinstance(g_id, int), "add_kpi_group should return an integer ID."
        print(f"  SUCCESS: Added 'Finance' with ID {g_id}")

        # Test 2: Add another group
        add_kpi_group("Operations")
        print("  SUCCESS: Added 'Operations'")

        # Test 3: Attempt to add duplicate group
        print("\nTest 3: Add duplicate group 'Finance' (expecting IntegrityError)")
        try:
            add_kpi_group("Finance")
            print("  FAILURE: Duplicate group addition did not raise IntegrityError.")
        except sqlite3.IntegrityError:
            print("  SUCCESS: IntegrityError raised for duplicate group as expected.")

        # Test 4: Update an existing group
        print(f"\nTest 4: Update group ID {g_id} ('Finance') to 'Financial Planning'")
        update_kpi_group(g_id, "Financial Planning")
        # Verification (manual query)
        with sqlite3.connect(str(DB_KPIS)) as conn:
            name = conn.execute(
                "SELECT name FROM kpi_groups WHERE id = ?", (g_id,)
            ).fetchone()[0]
            assert name == "Financial Planning", "Group name was not updated."
        print(f"  SUCCESS: Group ID {g_id} updated to 'Financial Planning'")

        # Test 5: Attempt to update a group to an existing name
        print(
            "\nTest 5: Update group 'Operations' to 'Financial Planning' (expecting IntegrityError)"
        )
        ops_id = None
        with sqlite3.connect(str(DB_KPIS)) as conn:  # Get ID for "Operations"
            ops_id_row = conn.execute(
                "SELECT id FROM kpi_groups WHERE name = 'Operations'"
            ).fetchone()
            if ops_id_row:
                ops_id = ops_id_row[0]

        if ops_id:
            try:
                update_kpi_group(ops_id, "Financial Planning")
                print(
                    "  FAILURE: Updating to existing name did not raise IntegrityError."
                )
            except sqlite3.IntegrityError:
                print(
                    "  SUCCESS: IntegrityError raised for update to existing name as expected."
                )
        else:
            print("  SKIPPED Test 5: Could not find 'Operations' group for test.")

        # Test 6: Delete a group
        # For a full test of delete_kpi_group, you'd also create subgroups and indicators.
        # Here, we test its basic operation. If mocks are used, it tests the flow.
        print(f"\nTest 6: Delete group ID {g_id} ('Financial Planning')")
        delete_kpi_group(g_id)
        # Verification (manual query)
        with sqlite3.connect(str(DB_KPIS)) as conn:
            row = conn.execute(
                "SELECT name FROM kpi_groups WHERE id = ?", (g_id,)
            ).fetchone()
            assert row is None, "Group was not deleted."
        print(f"  SUCCESS: Group ID {g_id} deleted.")
        g_id = None  # mark as deleted

        print("\n--- All kpi_management.groups tests passed (basic execution) ---")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED DURING TESTING ---")
        print(str(e))
        print(traceback.format_exc())

    finally:
        # Cleanup any remaining test data if an error occurred mid-test or if using a persistent test DB
        if (
            DB_KPIS == "test_groups_module.sqlite"
        ):  # Only if we used the file-based test db
            print(f"INFO: Cleaning up test database file: {DB_KPIS}")
            import os

            try:
                os.remove(DB_KPIS)
                print(f"  SUCCESS: Removed {DB_KPIS}")
            except OSError as e_ose:
                print(
                    f"  ERROR: Could not remove {DB_KPIS}. Manual cleanup may be needed. Error: {e_ose}"
                )
