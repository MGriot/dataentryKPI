# src/plants_management/crud.py
import sqlite3
import traceback
from pathlib import Path

from src.config.settings import get_database_path

# --- Configuration Imports ---
DB_PLANTS = get_database_path('db_plants.db')
DB_TARGETS = get_database_path('db_kpi_targets.db')


# --- Helper to check DB path ---
def _validate_db_path(db_path_obj, db_name_str):
    """Validates if the provided DB path object is usable."""
    if not db_path_obj.exists():
        raise ConnectionError(f"Database file for {db_name_str} not found at {db_path_obj}")


# --- Plant CRUD Operations ---


def add_plant(name: str, description: str = "", visible: bool = True, color: str = "#000000") -> int:
    """Adds a new plant to the database."""
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    with sqlite3.connect(DB_PLANTS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO plants (name, description, visible, color) VALUES (?,?,?,?)",
                (name, description, 1 if visible else 0, color),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise Exception(f"A plant with name '{name}' already exists.") from e
        except Exception as e_general:
            raise Exception(
                "Database error while adding the plant."
            ) from e_general


def update_plant(
    plant_id: int, name: str, description: str, visible: bool, color: str
):
    """Updates an existing plant's details."""
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    with sqlite3.connect(DB_PLANTS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plants SET name=?, description=?, visible=?, color=? WHERE id=?",
                (name, description, 1 if visible else 0, color, plant_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No plant found with ID {plant_id}. Update had no effect."
                )
        except sqlite3.IntegrityError as e:
            raise Exception(
                f"The name '{name}' is already used by another plant."
            ) from e
        except Exception as e_general:
            raise Exception(
                "Database error while updating the plant."
            ) from e_general


def update_plant_color(plant_id: int, color: str):
    """Updates the color of an existing plant."""
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    with sqlite3.connect(DB_PLANTS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plants SET color=? WHERE id=?",
                (color, plant_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No plant found with ID {plant_id}. Color update had no effect."
                )
        except Exception as e_general:
            raise Exception(
                "Database error while updating the plant color."
            ) from e_general


def is_plant_referenced(plant_id: int) -> bool:
    """Checks if a plant is referenced in the annual_targets table."""
    _validate_db_path(DB_TARGETS, "DB_TARGETS")
    try:
        with sqlite3.connect(DB_TARGETS) as conn_targets:
            cursor = conn_targets.cursor()
            cursor.execute(
                "SELECT 1 FROM annual_targets WHERE plant_id = ? LIMIT 1",
                (plant_id,),
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(
            f"ERROR: Database error while checking references for plant ID {plant_id}: {e}"
        )
        return True  # Assume referenced to be safe on error

def get_plant_by_id(plant_id: int) -> dict | None:
    """Retrieves a single plant by its ID."""
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    with sqlite3.connect(DB_PLANTS) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, visible, color FROM plants WHERE id = ?", (plant_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def delete_plant(plant_id: int, force_delete_if_referenced: bool = False):
    """
    Deletes a plant. By default, deletion is prevented if referenced in targets.
    """
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    if not force_delete_if_referenced:
        if is_plant_referenced(plant_id):
            raise ValueError(
                f"Plant ID {plant_id} is referenced in targets and cannot be deleted."
            )

    with sqlite3.connect(DB_PLANTS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM plants WHERE id = ?", (plant_id,))
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No plant found with ID {plant_id} to delete."
                )
        except sqlite3.Error as e:
            raise Exception(
                "Database error while deleting the plant."
            ) from e


if __name__ == "__main__":
    print("--- Running plants_management/crud.py for testing ---")

    plant_id_created = None

    def setup_minimal_tables_for_plants(db_plants_path, db_targets_path):
        with sqlite3.connect(db_plants_path) as conn_s:
            cur_s = conn_s.cursor()
            cur_s.execute(
                """
                CREATE TABLE IF NOT EXISTS plants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    visible BOOLEAN NOT NULL DEFAULT 1,
                    color TEXT NOT NULL DEFAULT '#000000');
            """
            )
            conn_s.commit()
        with sqlite3.connect(db_targets_path) as conn_t:
            cur_t = conn_t.cursor()
            cur_t.execute(
                """
                CREATE TABLE IF NOT EXISTS annual_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    plant_id INTEGER NOT NULL,
                    kpi_id INTEGER NOT NULL,
                    annual_target1 REAL DEFAULT 0);
            """
            )
            conn_t.commit()
        print(
            f"INFO: Minimal tables for plants testing ensured/created in {db_plants_path} and {db_targets_path}"
        )

    DB_PLANT_TEST_FILE = "test_plants_crud_stab.sqlite"
    DB_TARG_FOR_PLANT_TEST_FILE = "test_plants_crud_targets.sqlite"
    DB_PLANT_ORIGINAL, DB_TARG_ORIGINAL = DB_PLANTS, DB_TARGETS

    if (
        str(DB_PLANTS).startswith(":memory_")
        or "error_db" in str(DB_PLANTS)
        or str(DB_TARGETS).startswith(":memory_")
        or "error_db" in str(DB_TARGETS)
    ):
        print(f"INFO: Using test files for plants testing.")
        DB_PLANTS = DB_PLANT_TEST_FILE
        DB_TARGETS = DB_TARG_FOR_PLANT_TEST_FILE
        setup_minimal_tables_for_plants(
            DB_PLANT_TEST_FILE, DB_TARG_FOR_PLANT_TEST_FILE
        )

    try:
        print("\nTest 1: Add new plant 'Main Plant'")
        plant_id_created = add_plant(
            "Main Plant", "Primary manufacturing facility", True, "#FF0000"
        )
        assert isinstance(plant_id_created, int)
        print(f"  SUCCESS: Added 'Main Plant' with ID {plant_id_created}")

        print(
            "\nTest 2: Attempt to add duplicate 'Main Plant' (expecting Exception)"
        )
        try:
            add_plant("Main Plant", "Duplicate attempt", True, "#00FF00")
            print(
                "  FAILURE: Duplicate plant addition did not raise Exception."
            )
        except Exception as e:
            if "A plant with name 'Main Plant' already exists." in str(e):
                print(
                    "  SUCCESS: Exception raised for duplicate plant as expected."
                )
            else:
                raise

        print(f"\nTest 3: Update plant ID {plant_id_created}")
        update_plant(
            plant_id_created,
            "Main Plant (Renamed)",
            "Updated description",
            False,
            "#0000FF"
        )
        with sqlite3.connect(DB_PLANTS) as conn:
            row = conn.execute(
                "SELECT name, description, visible, color FROM plants WHERE id = ?",
                (plant_id_created,),
            ).fetchone()
            assert (
                row
                and row[0] == "Main Plant (Renamed)"
                and row[1] == "Updated description"
                and row[2] == 0
                and row[3] == "#0000FF"
            )
        print(f"  SUCCESS: Plant ID {plant_id_created} updated.")

        print(f"\nTest 4: Update plant color for ID {plant_id_created}")
        update_plant_color(plant_id_created, "#FFFF00")
        with sqlite3.connect(DB_PLANTS) as conn:
            row = conn.execute(
                "SELECT color FROM plants WHERE id = ?",
                (plant_id_created,),
            ).fetchone()
            assert row and row[0] == "#FFFF00"
        print(f"  SUCCESS: Plant ID {plant_id_created} color updated.")

        print(
            f"\nTest 5: Delete plant ID {plant_id_created} (no references)"
        )
        delete_plant(plant_id_created)
        with sqlite3.connect(DB_PLANTS) as conn:
            row = conn.execute(
                "SELECT id FROM plants WHERE id = ?", (plant_id_created,)
            ).fetchone()
            assert row is None, "Plant was not deleted."
        print(f"  SUCCESS: Plant ID {plant_id_created} deleted.")
        plant_id_created = None

        print(
            "\nTest 6: Attempt to delete plant referenced in targets (expecting ValueError)"
        )
        ref_plant_id = add_plant("Referenced Plant", "Test for delete constraint", True, "#CCCCCC")
        with sqlite3.connect(DB_TARGETS) as conn_t:
            conn_t.execute(
                "INSERT INTO annual_targets (year, plant_id, kpi_id) VALUES (?,?,?)",
                (2023, ref_plant_id, 1),
            )
            conn_t.commit()
        try:
            delete_plant(ref_plant_id)
            print(
                "  FAILURE: Deleting referenced plant did not raise ValueError."
            )
        except ValueError:
            print(
                "  SUCCESS: ValueError raised for deleting referenced plant as expected."
            )

        print(f"\nTest 7: Force delete plant ID {ref_plant_id} (referenced)")
        delete_plant(ref_plant_id, force_delete_if_referenced=True)
        with sqlite3.connect(DB_PLANTS) as conn:
            row = conn.execute(
                "SELECT id FROM plants WHERE id = ?", (ref_plant_id,)
            ).fetchone()
            assert row is None, "Plant was not force deleted."
        with sqlite3.connect(DB_TARGETS) as conn_t:
            target_row = conn_t.execute(
                "SELECT id FROM annual_targets WHERE plant_id = ?",
                (ref_plant_id,),
            ).fetchone()
            assert (
                target_row is not None
            ), "Target should still exist (orphaned) after force delete."
            print(
                f"  SUCCESS: Plant ID {ref_plant_id} force deleted. Orphaned target confirmed."
            )

        print(
            "\n--- All plants_management.crud tests passed (basic execution) ---"
        )

    except Exception as e:
        print(
            f"\n--- AN ERROR OCCURRED DURING TESTING (plants_management.crud) ---"
        )
        print(str(e))
        print(traceback.format_exc())
    finally:
        DB_PLANTS, DB_TARGETS = DB_PLANT_ORIGINAL, DB_TARG_ORIGINAL
        import os

        for test_db_file in [DB_PLANT_TEST_FILE, DB_TARG_FOR_PLANT_TEST_FILE]:
            if os.path.exists(test_db_file):
                try:
                    os.remove(test_db_file)
                    print(f"INFO: Cleaned up test file: {test_db_file}")
                except OSError as e_clean:
                    print(
                        f"ERROR: Could not clean up test file {test_db_file}: {e_clean}"
                    )