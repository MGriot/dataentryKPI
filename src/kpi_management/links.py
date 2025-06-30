# src/kpi_management/links.py
import sqlite3
import traceback
from pathlib import Path

# Configuration import
try:
    from app_config import DB_KPIS
except ImportError:
    print(
        "CRITICAL WARNING: app_config.py not found on PYTHONPATH. "
        "DB_KPIS will not be correctly defined. "
        "Ensure your project's root directory is in PYTHONPATH or adjust imports."
    )
    DB_KPIS = ":memory_kpis_links_error:" # Placeholder


# --- Helper to check DB path ---
def _validate_db_path():
    db_kpis_str = str(DB_KPIS)
    if db_kpis_str.startswith(":memory_") or "error_db" in db_kpis_str:
        raise ConnectionError(f"DB_KPIS is not properly configured ({DB_KPIS}).")


# --- Master/Sub KPI Link CRUD Operations ---

def add_master_sub_kpi_link(master_kpi_spec_id: int, sub_kpi_spec_id: int, weight: float = 1.0):
    """
    Adds a link between a master KPI and a sub KPI with a given distribution weight.
    If the link already exists, it attempts to update the weight.

    Args:
        master_kpi_spec_id (int): The ID (from kpis.id) of the master KPI.
        sub_kpi_spec_id (int): The ID (from kpis.id) of the sub KPI.
        weight (float): The distribution weight for this sub KPI under the master. Must be positive.

    Returns:
        int: The ID of the link record (from kpi_master_sub_links.id) if newly created.
             If updated, it might not return an ID directly without another query.
             For simplicity, this function primarily focuses on ensuring the link exists with the correct weight.

    Raises:
        ValueError: If master_kpi_spec_id equals sub_kpi_spec_id, or if weight is not positive.
        sqlite3.IntegrityError: If kpi_spec_ids do not exist in the 'kpis' table (FOREIGN KEY constraint).
        Exception: For other database errors.
    """
    _validate_db_path()

    if master_kpi_spec_id == sub_kpi_spec_id:
        msg = "A KPI cannot be a master and sub of itself."
        print(f"ERROR: {msg}")
        raise ValueError(msg)
    if not isinstance(weight, (int, float)) or weight <= 0:
        msg = "The distribution weight must be a positive number."
        print(f"ERROR: {msg} Received: {weight}")
        raise ValueError(msg)

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_master_sub_links (master_kpi_spec_id, sub_kpi_spec_id, distribution_weight) VALUES (?, ?, ?)",
                (master_kpi_spec_id, sub_kpi_spec_id, float(weight)),
            )
            conn.commit()
            link_id = cursor.lastrowid
            print(
                f"INFO: Linked Master KPI Spec ID {master_kpi_spec_id} to Sub KPI Spec ID {sub_kpi_spec_id} "
                f"with weight {weight}. Link ID: {link_id}"
            )
            return link_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kpi_master_sub_links.master_kpi_spec_id, kpi_master_sub_links.sub_kpi_spec_id" in str(e):
                # Link already exists, check if weight needs update
                print(f"INFO: Link between Master {master_kpi_spec_id} and Sub {sub_kpi_spec_id} already exists. "
                      "Attempting to update weight.")
                try:
                    update_master_sub_kpi_link_weight(master_kpi_spec_id, sub_kpi_spec_id, weight)
                    # To get the link ID here, you'd need another query.
                    # For now, successful update is the primary goal.
                    return None # Or query for ID if needed: conn.execute("SELECT id FROM ...").fetchone()[0]
                except Exception as e_update:
                    print(f"ERROR: Failed to update weight for existing link Master {master_kpi_spec_id} - Sub {sub_kpi_spec_id}. Details: {e_update}")
                    raise # Re-raise the update error
            elif "FOREIGN KEY constraint failed" in str(e):
                print(f"ERROR: Could not add link. Master KPI Spec ID {master_kpi_spec_id} or "
                      f"Sub KPI Spec ID {sub_kpi_spec_id} does not exist in 'kpis' table. Details: {e}")
                raise
            else:
                print(f"ERROR: IntegrityError while adding master-sub link. Details: {e}")
                raise
        except sqlite3.Error as e_general:
            print(f"ERROR: Database error while adding master-sub link. Details: {e_general}")
            print(traceback.format_exc())
            raise Exception("A database error occurred while adding master-sub link.") from e_general

def update_master_sub_kpi_link_weight(master_kpi_spec_id: int, sub_kpi_spec_id: int, new_weight: float):
    """
    Updates the distribution weight of an existing link between a master and a sub KPI.

    Args:
        master_kpi_spec_id (int): The ID of the master KPI.
        sub_kpi_spec_id (int): The ID of the sub KPI.
        new_weight (float): The new positive distribution weight.

    Raises:
        ValueError: If new_weight is not a positive number.
        Exception: If the link does not exist or for other database errors.
    """
    _validate_db_path()

    if not isinstance(new_weight, (int, float)) or new_weight <= 0:
        msg = "The distribution weight must be a positive number."
        print(f"ERROR: {msg} Received: {new_weight}")
        raise ValueError(msg)

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE kpi_master_sub_links SET distribution_weight = ? WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?",
                (float(new_weight), master_kpi_spec_id, sub_kpi_spec_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No link found between Master KPI Spec ID {master_kpi_spec_id} and "
                    f"Sub KPI Spec ID {sub_kpi_spec_id}. Weight update had no effect."
                )
                # Consider raising an error if updating a non-existent link is critical
                # raise ValueError("Link not found for weight update.")
            else:
                print(
                    f"INFO: Updated weight to {new_weight} for link Master {master_kpi_spec_id} - Sub {sub_kpi_spec_id}"
                )
        except sqlite3.Error as e:
            print(f"ERROR: Database error while updating link weight. Details: {e}")
            print(traceback.format_exc())
            raise Exception("A database error occurred while updating link weight.") from e

def remove_master_sub_kpi_link(master_kpi_spec_id: int, sub_kpi_spec_id: int):
    """
    Removes a specific link between a master and a sub KPI.

    Args:
        master_kpi_spec_id (int): The ID of the master KPI.
        sub_kpi_spec_id (int): The ID of the sub KPI.

    Raises:
        Exception: For database errors.
    """
    _validate_db_path()

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?",
                (master_kpi_spec_id, sub_kpi_spec_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"INFO: No link found to remove between Master KPI Spec ID {master_kpi_spec_id} and "
                    f"Sub KPI Spec ID {sub_kpi_spec_id}."
                )
            else:
                print(
                    f"INFO: Unlinked Sub KPI Spec ID {sub_kpi_spec_id} from Master KPI Spec ID {master_kpi_spec_id}."
                )
        except sqlite3.Error as e:
            print(f"ERROR: Database error while removing master-sub link. Details: {e}")
            print(traceback.format_exc())
            raise Exception("A database error occurred while removing master-sub link.") from e


def remove_all_links_for_kpi(kpi_spec_id: int):
    """
    Removes a KPI from all link roles (either as master or sub).
    This is typically used when a KPI specification (kpis record) is being deleted.
    However, with ON DELETE CASCADE defined on the kpi_master_sub_links table
    referencing kpis.id, this function might be redundant if the kpis record
    deletion correctly triggers these cascades. It's kept for explicit cleanup
    if needed or if cascade behavior is uncertain/disabled.

    Args:
        kpi_spec_id (int): The ID of the KPI Spec (from kpis.id) to remove from all links.

    Raises:
        Exception: For database errors.
    """
    _validate_db_path()

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            # Delete where it's a master
            cursor.execute(
                "DELETE FROM kpi_master_sub_links WHERE master_kpi_spec_id = ?",
                (kpi_spec_id,),
            )
            master_rows_deleted = cursor.rowcount
            # Delete where it's a sub
            cursor.execute(
                "DELETE FROM kpi_master_sub_links WHERE sub_kpi_spec_id = ?",
                (kpi_spec_id,),
            )
            sub_rows_deleted = cursor.rowcount
            conn.commit()
            print(
                f"INFO: Removed all master/sub links for KPI Spec ID {kpi_spec_id}. "
                f"({master_rows_deleted} as master, {sub_rows_deleted} as sub)."
            )
        except sqlite3.Error as e:
            print(f"ERROR: Database error while removing all links for KPI Spec ID {kpi_spec_id}. Details: {e}")
            print(traceback.format_exc())
            raise Exception(f"Database error removing all links for KPI Spec ID {kpi_spec_id}.") from e


if __name__ == "__main__":
    print("--- Running kpi_management/links.py for testing ---")

    # This test block assumes DB_KPIS is configured and the necessary tables
    # (kpis, kpi_master_sub_links) exist.
    # For robust testing, use a dedicated test database.

    # Helper to setup minimal tables for links testing
    def setup_minimal_tables_for_links(db_path):
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            # kpi_groups, kpi_subgroups, kpi_indicators are needed for kpis table FK
            cur.execute("CREATE TABLE IF NOT EXISTS kpi_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);")
            cur.execute("INSERT OR IGNORE INTO kpi_groups (id, name) VALUES (1, 'Test Group for Links')")
            cur.execute("""CREATE TABLE IF NOT EXISTS kpi_subgroups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, group_id INTEGER NOT NULL,
                           FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE, UNIQUE (name, group_id));""")
            cur.execute("INSERT OR IGNORE INTO kpi_subgroups (id, name, group_id) VALUES (1, 'Test Subgroup for Links', 1)")
            cur.execute("""CREATE TABLE IF NOT EXISTS kpi_indicators (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subgroup_id INTEGER NOT NULL,
                           FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE, UNIQUE (name, subgroup_id));""")
            cur.execute("INSERT OR IGNORE INTO kpi_indicators (id, name, subgroup_id) VALUES (1, 'Master Ind Link Test', 1)")
            cur.execute("INSERT OR IGNORE INTO kpi_indicators (id, name, subgroup_id) VALUES (2, 'Sub Ind1 Link Test', 1)")
            cur.execute("INSERT OR IGNORE INTO kpi_indicators (id, name, subgroup_id) VALUES (3, 'Sub Ind2 Link Test', 1)")

            # kpis table (parent for kpi_master_sub_links)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kpis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, indicator_id INTEGER NOT NULL UNIQUE,
                    description TEXT, calculation_type TEXT NOT NULL, unit_of_measure TEXT,
                    FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE);""")
            # Create some kpis records to link
            cur.execute("INSERT OR IGNORE INTO kpis (id, indicator_id, calculation_type) VALUES (100, 1, 'Media')") # Master
            cur.execute("INSERT OR IGNORE INTO kpis (id, indicator_id, calculation_type) VALUES (101, 2, 'Media')") # Sub1
            cur.execute("INSERT OR IGNORE INTO kpis (id, indicator_id, calculation_type) VALUES (102, 3, 'Media')") # Sub2

            # kpi_master_sub_links table (this module's target)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kpi_master_sub_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    master_kpi_spec_id INTEGER NOT NULL,
                    sub_kpi_spec_id INTEGER NOT NULL,
                    distribution_weight REAL NOT NULL DEFAULT 1.0,
                    FOREIGN KEY (master_kpi_spec_id) REFERENCES kpis(id) ON DELETE CASCADE,
                    FOREIGN KEY (sub_kpi_spec_id) REFERENCES kpis(id) ON DELETE CASCADE,
                    UNIQUE (master_kpi_spec_id, sub_kpi_spec_id)); """)
            conn.commit()
            print(f"INFO: Minimal tables for links testing ensured/created in {db_path}")

    DB_KPIS_LINKS_TEST_FILE = "test_kpi_links.sqlite"
    DB_KPIS_ORIGINAL_LINKS = DB_KPIS # Save original
    if DB_KPIS.startswith(":memory_") or "error_db" in str(DB_KPIS):
        print(f"INFO: Using '{DB_KPIS_LINKS_TEST_FILE}' for DB_KPIS during links testing.")
        DB_KPIS = DB_KPIS_LINKS_TEST_FILE # Override for tests
        setup_minimal_tables_for_links(DB_KPIS_LINKS_TEST_FILE)


    # Test kpi_spec_ids (these are kpis.id)
    MASTER_ID = 100
    SUB_ID_1 = 101
    SUB_ID_2 = 102
    NON_EXISTENT_KPI_ID = 999

    link_id1 = None
    try:
        print("\nTest 1: Add a new master-sub link")
        link_id1 = add_master_sub_kpi_link(MASTER_ID, SUB_ID_1, weight=1.5)
        assert link_id1 is not None, "Failed to add new link or get its ID."
        print(f"  SUCCESS: Added link Master {MASTER_ID} to Sub {SUB_ID_1} with weight 1.5. Link ID: {link_id1}")

        print("\nTest 2: Attempt to add the same link (should update weight or indicate no change)")
        # This will internally call update_master_sub_kpi_link_weight if UNIQUE constraint is hit.
        add_master_sub_kpi_link(MASTER_ID, SUB_ID_1, weight=2.0)
        # Verify weight update
        with sqlite3.connect(DB_KPIS) as conn:
            weight_val = conn.execute(
                "SELECT distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id=? AND sub_kpi_spec_id=?",
                (MASTER_ID, SUB_ID_1)
            ).fetchone()
            assert weight_val and abs(weight_val[0] - 2.0) < 0.001, "Link weight was not updated."
        print(f"  SUCCESS: Link Master {MASTER_ID} to Sub {SUB_ID_1} weight updated to 2.0.")

        print("\nTest 3: Update weight of an existing link directly")
        update_master_sub_kpi_link_weight(MASTER_ID, SUB_ID_1, new_weight=2.5)
        with sqlite3.connect(DB_KPIS) as conn:
            weight_val = conn.execute(
                "SELECT distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id=? AND sub_kpi_spec_id=?",
                (MASTER_ID, SUB_ID_1)
            ).fetchone()
            assert weight_val and abs(weight_val[0] - 2.5) < 0.001, "Link weight not updated by direct call."
        print(f"  SUCCESS: Link Master {MASTER_ID} to Sub {SUB_ID_1} weight updated directly to 2.5.")

        print("\nTest 4: Add another link")
        add_master_sub_kpi_link(MASTER_ID, SUB_ID_2, weight=1.0)
        print(f"  SUCCESS: Added link Master {MASTER_ID} to Sub {SUB_ID_2} with weight 1.0.")

        print("\nTest 5: Remove a specific link")
        remove_master_sub_kpi_link(MASTER_ID, SUB_ID_1)
        with sqlite3.connect(DB_KPIS) as conn:
            row = conn.execute(
                "SELECT id FROM kpi_master_sub_links WHERE master_kpi_spec_id=? AND sub_kpi_spec_id=?",
                (MASTER_ID, SUB_ID_1)
            ).fetchone()
            assert row is None, "Link was not removed."
        print(f"  SUCCESS: Removed link Master {MASTER_ID} - Sub {SUB_ID_1}.")

        print("\nTest 6: Remove all links for a master KPI")
        # First, re-add a link to ensure there's something to remove
        add_master_sub_kpi_link(MASTER_ID, SUB_ID_1, weight=1.0)
        remove_all_links_for_kpi(MASTER_ID)
        with sqlite3.connect(DB_KPIS) as conn:
            rows = conn.execute(
                "SELECT id FROM kpi_master_sub_links WHERE master_kpi_spec_id=?", (MASTER_ID,)
            ).fetchall()
            assert not rows, "Not all links removed for master KPI."
        print(f"  SUCCESS: All links removed for Master KPI {MASTER_ID}.")

        print("\nTest 7: Add link with non-existent master_kpi_spec_id (expecting IntegrityError)")
        try:
            add_master_sub_kpi_link(NON_EXISTENT_KPI_ID, SUB_ID_1)
            print("  FAILURE: Adding link with non-existent master ID did not raise IntegrityError.")
        except sqlite3.IntegrityError:
            print("  SUCCESS: IntegrityError (FOREIGN KEY) raised as expected for non-existent master.")

        print("\nTest 8: Add link with invalid weight (expecting ValueError)")
        try:
            add_master_sub_kpi_link(MASTER_ID, SUB_ID_1, weight=-1.0)
            print("  FAILURE: Adding link with invalid weight did not raise ValueError.")
        except ValueError:
            print("  SUCCESS: ValueError raised as expected for invalid weight.")

        print("\n--- All kpi_management.links tests passed (basic execution) ---")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED DURING TESTING (kpi_management.links) ---")
        print(str(e))
        print(traceback.format_exc())
    finally:
        DB_KPIS = DB_KPIS_ORIGINAL_LINKS # Restore original DB_KPIS
        if DB_KPIS_LINKS_TEST_FILE and os.path.exists(DB_KPIS_LINKS_TEST_FILE):
             import os
             try:
                 os.remove(DB_KPIS_LINKS_TEST_FILE)
                 print(f"INFO: Cleaned up test file: {DB_KPIS_LINKS_TEST_FILE}")
             except OSError as e_clean:
                 print(f"ERROR: Could not clean up test file {DB_KPIS_LINKS_TEST_FILE}: {e_clean}")
