# src/stabilimenti_management/crud.py
import sqlite3
import traceback
from pathlib import Path

# --- Configuration Imports ---
try:
    from app_config import DB_STABILIMENTI, DB_TARGETS
except ImportError:
    print(
        "CRITICAL WARNING: app_config.py not found in stabilimenti_management/crud.py"
    )
    DB_STABILIMENTI = Path(":memory_stabilimenti_error.sqlite")
    DB_TARGETS = Path(":memory_targets_for_stabilimenti_error.sqlite")


# --- Helper to check DB path ---
def _validate_db_path(db_path_obj, db_name_str):
    """Validates if the provided DB path object is usable."""
    path_str = str(db_path_obj)
    if path_str.startswith(":memory_") or "error_db" in path_str:
        raise ConnectionError(f"{db_name_str} is not properly configured ({path_str}).")


# --- Stabilimento CRUD Operations ---


def add_stabilimento(name: str, description: str = "", visible: bool = True) -> int:
    """
    Adds a new stabilimento to the database.

    Args:
        name (str): The name of the stabilimento. Must be unique.
        description (str, optional): A description for the stabilimento. Defaults to "".
        visible (bool, optional): Whether the stabilimento is visible. Defaults to True.

    Returns:
        int: The ID of the newly created stabilimento.

    Raises:
        sqlite3.IntegrityError: If the stabilimento name already exists.
        Exception: For other database errors.
    """
    if DB_STABILIMENTI.startswith(":memory_") or "error_db" in str(DB_STABILIMENTI):
        raise ConnectionError(
            f"DB_STABILIMENTI is not properly configured ({DB_STABILIMENTI}). Cannot add stabilimento."
        )

# --- Stabilimento CRUD Operations ---


def add_stabilimento(name: str, description: str = "", visible: bool = True) -> int:
    """Adds a new stabilimento to the database."""
    _validate_db_path(DB_STABILIMENTI, "DB_STABILIMENTI")  # FIX: Use helper
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO stabilimenti (name, description, visible) VALUES (?,?,?)",
                (name, description, 1 if visible else 0),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise Exception(f"Uno stabilimento con nome '{name}' esiste già.") from e
        except Exception as e_general:
            raise Exception(
                "Errore database durante l'aggiunta dello stabilimento."
            ) from e_general


def update_stabilimento(
    stabilimento_id: int, name: str, description: str, visible: bool
):
    """Updates an existing stabilimento's details."""
    _validate_db_path(DB_STABILIMENTI, "DB_STABILIMENTI")  # FIX: Use helper
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE stabilimenti SET name=?, description=?, visible=? WHERE id=?",
                (name, description, 1 if visible else 0, stabilimento_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No stabilimento found with ID {stabilimento_id}. Update had no effect."
                )
        except sqlite3.IntegrityError as e:
            raise Exception(
                f"Il nome '{name}' è già utilizzato da un altro stabilimento."
            ) from e
        except Exception as e_general:
            raise Exception(
                "Errore database durante l'aggiornamento dello stabilimento."
            ) from e_general


def is_stabilimento_referenced(stabilimento_id: int) -> bool:
    """
    Checks if a stabilimento is referenced in the annual_targets table.
    Helper function for safe deletion.
    """
    if DB_TARGETS.startswith(":memory_") or "error_db" in str(DB_TARGETS):
        print(
            f"WARNING: DB_TARGETS is not properly configured ({DB_TARGETS}). Cannot check references accurately."
        )
        return True  # Assume referenced to be safe if DB_TARGETS is misconfigured

    try:
        with sqlite3.connect(DB_TARGETS) as conn_targets:
            cursor = conn_targets.cursor()
            cursor.execute(
                "SELECT 1 FROM annual_targets WHERE stabilimento_id = ? LIMIT 1",
                (stabilimento_id,),
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(
            f"ERROR: Database error while checking references for stabilimento ID {stabilimento_id} in DB_TARGETS. Details: {e}"
        )
        print(traceback.format_exc())
        return True  # Assume referenced to be safe on error


def is_stabilimento_referenced(stabilimento_id: int) -> bool:
    """Checks if a stabilimento is referenced in the annual_targets table."""
    _validate_db_path(DB_TARGETS, "DB_TARGETS")  # FIX: Use helper
    try:
        with sqlite3.connect(DB_TARGETS) as conn_targets:
            cursor = conn_targets.cursor()
            cursor.execute(
                "SELECT 1 FROM annual_targets WHERE stabilimento_id = ? LIMIT 1",
                (stabilimento_id,),
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(
            f"ERROR: Database error while checking references for stabilimento ID {stabilimento_id}: {e}"
        )
        return True  # Assume referenced to be safe on error


def delete_stabilimento(stabilimento_id: int, force_delete_if_referenced: bool = False):
    """
    Deletes a stabilimento. By default, deletion is prevented if referenced in targets.
    """
    _validate_db_path(DB_STABILIMENTI, "DB_STABILIMENTI")  # FIX: Use helper
    if not force_delete_if_referenced:
        if is_stabilimento_referenced(stabilimento_id):
            raise ValueError(
                f"Stabilimento ID {stabilimento_id} è referenziato nei target e non può essere eliminato."
            )

    with sqlite3.connect(DB_STABILIMENTI) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stabilimenti WHERE id = ?", (stabilimento_id,))
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No stabilimento found with ID {stabilimento_id} to delete."
                )
        except sqlite3.Error as e:
            raise Exception(
                "Errore database durante l'eliminazione dello stabilimento."
            ) from e


if __name__ == "__main__":
    print("--- Running stabilimenti_management/crud.py for testing ---")

    # This test block assumes DB_STABILIMENTI and DB_TARGETS are configured.
    # For robust testing, use a dedicated test database setup.

    stabilimento_id_created = None

    # Helper to setup minimal tables for stabilimenti testing
    def setup_minimal_tables_for_stabilimenti(db_stabilimenti_path, db_targets_path):
        with sqlite3.connect(db_stabilimenti_path) as conn_s:
            cur_s = conn_s.cursor()
            cur_s.execute(
                """
                CREATE TABLE IF NOT EXISTS stabilimenti (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    visible BOOLEAN NOT NULL DEFAULT 1);
            """
            )
            conn_s.commit()
        with sqlite3.connect(db_targets_path) as conn_t:
            cur_t = conn_t.cursor()
            # Simplified annual_targets for reference check
            cur_t.execute(
                """
                CREATE TABLE IF NOT EXISTS annual_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    stabilimento_id INTEGER NOT NULL,
                    kpi_id INTEGER NOT NULL,
                    annual_target1 REAL DEFAULT 0);
            """
            )  # No FK defined here to stabilimenti in another DB file for basic SQLite test
            conn_t.commit()
        print(
            f"INFO: Minimal tables for stabilimenti testing ensured/created in {db_stabilimenti_path} and {db_targets_path}"
        )

    DB_STAB_TEST_FILE = "test_stabilimenti_crud_stab.sqlite"
    DB_TARG_FOR_STAB_TEST_FILE = "test_stabilimenti_crud_targets.sqlite"
    DB_STAB_ORIGINAL, DB_TARG_ORIGINAL = DB_STABILIMENTI, DB_TARGETS

    if (
        DB_STABILIMENTI.startswith(":memory_")
        or "error_db" in str(DB_STABILIMENTI)
        or DB_TARGETS.startswith(":memory_")
        or "error_db" in str(DB_TARGETS)
    ):
        print(f"INFO: Using test files for stabilimenti testing.")
        DB_STABILIMENTI = DB_STAB_TEST_FILE
        DB_TARGETS = DB_TARG_FOR_STAB_TEST_FILE
        setup_minimal_tables_for_stabilimenti(
            DB_STAB_TEST_FILE, DB_TARG_FOR_STAB_TEST_FILE
        )

    try:
        print("\nTest 1: Add new stabilimento 'Main Plant'")
        stabilimento_id_created = add_stabilimento(
            "Main Plant", "Primary manufacturing facility", True
        )
        assert isinstance(stabilimento_id_created, int)
        print(f"  SUCCESS: Added 'Main Plant' with ID {stabilimento_id_created}")

        print(
            "\nTest 2: Attempt to add duplicate 'Main Plant' (expecting IntegrityError)"
        )
        try:
            add_stabilimento("Main Plant", "Duplicate attempt")
            print(
                "  FAILURE: Duplicate stabilimento addition did not raise IntegrityError."
            )
        except sqlite3.IntegrityError:
            print(
                "  SUCCESS: IntegrityError raised for duplicate stabilimento as expected."
            )

        print(f"\nTest 3: Update stabilimento ID {stabilimento_id_created}")
        update_stabilimento(
            stabilimento_id_created,
            "Main Plant (Renamed)",
            "Updated description",
            False,
        )
        with sqlite3.connect(DB_STABILIMENTI) as conn:
            row = conn.execute(
                "SELECT name, description, visible FROM stabilimenti WHERE id = ?",
                (stabilimento_id_created,),
            ).fetchone()
            assert (
                row
                and row[0] == "Main Plant (Renamed)"
                and row[1] == "Updated description"
                and row[2] == 0
            )
        print(f"  SUCCESS: Stabilimento ID {stabilimento_id_created} updated.")

        print(
            f"\nTest 4: Delete stabilimento ID {stabilimento_id_created} (no references)"
        )
        delete_stabilimento(stabilimento_id_created)
        with sqlite3.connect(DB_STABILIMENTI) as conn:
            row = conn.execute(
                "SELECT id FROM stabilimenti WHERE id = ?", (stabilimento_id_created,)
            ).fetchone()
            assert row is None, "Stabilimento was not deleted."
        print(f"  SUCCESS: Stabilimento ID {stabilimento_id_created} deleted.")
        stabilimento_id_created = None  # Mark as deleted

        print(
            "\nTest 5: Attempt to delete stabilimento referenced in targets (expecting ValueError)"
        )
        # Add a new stabilimento and a target referencing it
        ref_stab_id = add_stabilimento("Referenced Plant", "Test for delete constraint")
        with sqlite3.connect(DB_TARGETS) as conn_t:
            conn_t.execute(
                "INSERT INTO annual_targets (year, stabilimento_id, kpi_id) VALUES (?,?,?)",
                (2023, ref_stab_id, 1),
            )
            conn_t.commit()
        try:
            delete_stabilimento(ref_stab_id)
            print(
                "  FAILURE: Deleting referenced stabilimento did not raise ValueError."
            )
        except ValueError:
            print(
                "  SUCCESS: ValueError raised for deleting referenced stabilimento as expected."
            )

        print(f"\nTest 6: Force delete stabilimento ID {ref_stab_id} (referenced)")
        delete_stabilimento(ref_stab_id, force_delete_if_referenced=True)
        with sqlite3.connect(DB_STABILIMENTI) as conn:
            row = conn.execute(
                "SELECT id FROM stabilimenti WHERE id = ?", (ref_stab_id,)
            ).fetchone()
            assert row is None, "Stabilimento was not force deleted."
        # Check if target is orphaned (it will be with this simplified setup)
        with sqlite3.connect(DB_TARGETS) as conn_t:
            target_row = conn_t.execute(
                "SELECT id FROM annual_targets WHERE stabilimento_id = ?",
                (ref_stab_id,),
            ).fetchone()
            assert (
                target_row is not None
            ), "Target should still exist (orphaned) after force delete."
            print(
                f"  SUCCESS: Stabilimento ID {ref_stab_id} force deleted. Orphaned target confirmed."
            )

        print(
            "\n--- All stabilimenti_management.crud tests passed (basic execution) ---"
        )

    except Exception as e:
        print(
            f"\n--- AN ERROR OCCURRED DURING TESTING (stabilimenti_management.crud) ---"
        )
        print(str(e))
        print(traceback.format_exc())
    finally:
        DB_STABILIMENTI, DB_TARGETS = DB_STAB_ORIGINAL, DB_TARG_ORIGINAL  # Restore
        import os

        for test_db_file in [DB_STAB_TEST_FILE, DB_TARG_FOR_STAB_TEST_FILE]:
            if os.path.exists(test_db_file) and (
                DB_STABILIMENTI == test_db_file
                or DB_TARGETS == test_db_file
                or DB_STAB_ORIGINAL == test_db_file
                or DB_TARG_ORIGINAL == test_db_file
            ):
                try:
                    os.remove(test_db_file)
                    print(f"INFO: Cleaned up test file: {test_db_file}")
                except OSError as e_clean:
                    print(
                        f"ERROR: Could not clean up test file {test_db_file}: {e_clean}"
                    )
