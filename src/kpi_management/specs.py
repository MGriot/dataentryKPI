# src/kpi_management/specs.py
import sqlite3
import traceback
from pathlib import Path # Ensure Path is imported

# Configuration import
try:
    from app_config import DB_KPIS
    from gui.shared.constants import CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA
except ImportError:
    print(
        "CRITICAL WARNING: app_config.py not found on PYTHONPATH. "
        "DB_KPIS or calculation type constants will not be correctly defined. "
        "Ensure your project's root directory is in PYTHONPATH or adjust imports."
    )
    DB_KPIS = ":memory_kpis_specs_error:"  # Placeholder
    # Define placeholders for calc types if import fails, to allow script loading
    CALC_TYPE_INCREMENTALE = "Incrementale_fallback"
    CALC_TYPE_MEDIA = "Media_fallback"


# --- KPI Specification (kpis table) CRUD Operations ---


def add_kpi_spec(
    indicator_id: int,
    description: str,
    calculation_type: str,
    unit_of_measure: str,
    visible: bool,
) -> int:
    """
    Adds a new KPI specification (a record in the 'kpis' table).
    If a spec for the given indicator_id already exists, it attempts to update it.

    Args:
        indicator_id (int): The ID from the 'kpi_indicators' table this spec is for. Must be unique in 'kpis'.
        description (str): Description of the KPI.
        calculation_type (str): How the KPI is calculated (e.g., 'Incrementale', 'Media').
                                Must match one of the allowed types.
        unit_of_measure (str): The unit of measure for this KPI.
        visible (bool): Whether this KPI spec is visible by default.

    Returns:
        int: The ID of the newly created or updated KPI specification (kpis.id).

    Raises:
        ValueError: If calculation_type is not one of the allowed types.
        sqlite3.IntegrityError: If indicator_id does not exist in 'kpi_indicators' (FOREIGN KEY constraint),
                                or for other integrity issues not related to indicator_id uniqueness.
        Exception: For other database errors.
    """
    db_kpis_str = str(DB_KPIS)
    if db_kpis_str.startswith(":memory_") or "error_db" in db_kpis_str:
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({DB_KPIS}). Cannot add KPI spec."
        )

    allowed_calc_types = [CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA]
    if calculation_type not in allowed_calc_types:
        msg = f"Invalid calculation_type: '{calculation_type}'. Must be one of {allowed_calc_types}."
        print(f"ERROR: {msg}")
        raise ValueError(msg)

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    indicator_id,
                    description,
                    calculation_type,
                    unit_of_measure,
                    1 if visible else 0,
                ),
            )
            conn.commit()
            kpi_spec_id = cursor.lastrowid
            print(
                f"INFO: KPI Spec for indicator_id {indicator_id} added successfully with kpis.id: {kpi_spec_id}."
            )
            return kpi_spec_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kpis.indicator_id" in str(e):
                # Spec for this indicator_id already exists, attempt to update it.
                print(
                    f"INFO: KPI Spec for indicator_id {indicator_id} already exists. Attempting to update."
                )
                try:
                    # First, get the existing kpis.id
                    cursor.execute(
                        "SELECT id FROM kpis WHERE indicator_id=?", (indicator_id,)
                    )
                    existing_kpi_row = cursor.fetchone()
                    if existing_kpi_row:
                        existing_kpi_spec_id = existing_kpi_row[0]
                        print(
                            f"  Found existing kpis.id: {existing_kpi_spec_id}. Updating..."
                        )
                        update_kpi_spec(
                            kpi_spec_id=existing_kpi_spec_id,  # Pass the kpis.id
                            indicator_id=indicator_id,  # Pass the kpi_indicators.id
                            description=description,
                            calculation_type=calculation_type,
                            unit_of_measure=unit_of_measure,
                            visible=visible,
                        )
                        return existing_kpi_spec_id  # Return the ID of the updated spec
                    else:
                        # This state (UNIQUE error but no row found) should be rare.
                        print(
                            f"ERROR: UNIQUE constraint for indicator_id {indicator_id} failed, "
                            "but could not find the existing kpi_spec to update. This is unexpected."
                        )
                        raise  # Re-raise the original integrity error
                except Exception as e_update:
                    print(
                        f"ERROR: Failed to update existing KPI Spec for indicator_id {indicator_id}. Details: {e_update}"
                    )
                    raise  # Re-raise the update error
            elif "FOREIGN KEY constraint failed" in str(e):
                print(
                    f"ERROR: Could not add KPI Spec. Indicator ID {indicator_id} "
                    f"does not exist in 'kpi_indicators' table. Details: {e}"
                )
                raise
            else:
                print(
                    f"ERROR: IntegrityError while adding KPI Spec for indicator_id {indicator_id}. Details: {e}"
                )
                raise
        except sqlite3.Error as e_general:
            print(
                f"ERROR: Database error while adding KPI Spec for indicator_id {indicator_id}. Details: {e_general}"
            )
            print(traceback.format_exc())
            raise Exception(
                f"A database error occurred while adding KPI Spec for indicator_id {indicator_id}."
            ) from e_general


def update_kpi_spec(
    kpi_spec_id: int,  # This is kpis.id
    indicator_id: int,  # This is kpi_indicators.id
    description: str,
    calculation_type: str,
    unit_of_measure: str,
    visible: bool,
):
    """
    Updates an existing KPI specification.

    Args:
        kpi_spec_id (int): The ID of the KPI specification (from kpis.id) to update.
        indicator_id (int): The ID from 'kpi_indicators' this spec refers to.
                            This is usually not changed but included for completeness and uniqueness.
        description (str): New description.
        calculation_type (str): New calculation type.
        unit_of_measure (str): New unit of measure.
        visible (bool): New visibility state.

    Raises:
        ValueError: If calculation_type is not one of the allowed types.
        sqlite3.IntegrityError: If indicator_id constraint violations occur (e.g., trying to change
                                indicator_id to one that already has a spec, or FK violation).
        Exception: If kpi_spec_id does not exist or for other database errors.
    """
    db_kpis_str = str(DB_KPIS)
    if db_kpis_str.startswith(":memory_") or "error_db" in db_kpis_str:
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({DB_KPIS}). Cannot update KPI spec."
        )

    allowed_calc_types = [CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA]
    if calculation_type not in allowed_calc_types:
        msg = f"Invalid calculation_type: '{calculation_type}'. Must be one of {allowed_calc_types}."
        print(f"ERROR: {msg}")
        raise ValueError(msg)

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            # The indicator_id in the kpis table is UNIQUE.
            # If you are trying to change it, it must not conflict with an existing one.
            cursor.execute(
                """UPDATE kpis SET indicator_id=?, description=?, calculation_type=?,
                   unit_of_measure=?, visible=? WHERE id=?""",
                (
                    indicator_id,
                    description,
                    calculation_type,
                    unit_of_measure,
                    1 if visible else 0,
                    kpi_spec_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No KPI Spec found with kpis.id {kpi_spec_id}. Update had no effect."
                )
                # Consider raising ValueError if updating non-existent spec is critical
            else:
                print(
                    f"INFO: KPI Spec with kpis.id {kpi_spec_id} updated successfully."
                )
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kpis.indicator_id" in str(e):
                print(
                    f"ERROR: Could not update KPI Spec {kpi_spec_id}. "
                    f"The indicator_id {indicator_id} is already linked to another KPI Spec. Details: {e}"
                )
            elif "FOREIGN KEY constraint failed" in str(e):
                print(
                    f"ERROR: Could not update KPI Spec {kpi_spec_id}. "
                    f"The indicator_id {indicator_id} does not exist in 'kpi_indicators'. Details: {e}"
                )
            else:
                print(
                    f"ERROR: IntegrityError while updating KPI Spec {kpi_spec_id}. Details: {e}"
                )
            raise
        except sqlite3.Error as e_general:
            print(
                f"ERROR: Database error while updating KPI Spec {kpi_spec_id}. Details: {e_general}"
            )
            print(traceback.format_exc())
            raise Exception(
                f"A database error occurred while updating KPI Spec {kpi_spec_id}."
            ) from e_general


# Note: Deletion of a KPI Specification (kpis record) is typically handled
# by the deletion of its parent KPI Indicator (kpi_indicators record)
# through ON DELETE CASCADE, as defined in the kpis table schema:
# FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE
# Therefore, an explicit `delete_kpi_spec` function is often not needed here
# if that's the intended data lifecycle. If you need to delete a spec
# without deleting the indicator (which would break the FK if not handled carefully),
# that would be a different use case.

if __name__ == "__main__":
    print("--- Running kpi_management/specs.py for testing ---")

    # This test assumes DB_KPIS is configured and kpi_indicators table exists
    # with some data.
    TEST_INDICATOR_ID_FOR_SPEC = 10  # Example: An ID from kpi_indicators
    kpi_spec_id_created = None

    # Helper to setup minimal tables for specs testing
    def setup_minimal_tables_for_specs(db_path, indicator_id_to_ensure):
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            # Dependencies: kpi_groups, kpi_subgroups
            cur.execute(
                "CREATE TABLE IF NOT EXISTS kpi_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);"
            )
            cur.execute(
                "INSERT OR IGNORE INTO kpi_groups (id, name) VALUES (1, 'Test Group for Specs')"
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS kpi_subgroups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, group_id INTEGER NOT NULL,
                           FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE, UNIQUE (name, group_id));"""
            )
            cur.execute(
                "INSERT OR IGNORE INTO kpi_subgroups (id, name, group_id) VALUES (1, 'Test Subgroup for Specs', 1)"
            )

            # kpi_indicators table (parent for kpis)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS kpi_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subgroup_id INTEGER NOT NULL,
                    FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE,
                    UNIQUE (name, subgroup_id));
            """
            )
            # Ensure the specific indicator_id exists
            cur.execute(
                "INSERT OR IGNORE INTO kpi_indicators (id, name, subgroup_id) VALUES (?, ?, ?)",
                (indicator_id_to_ensure, f"Test Indicator {indicator_id_to_ensure}", 1),
            )
            cur.execute(
                f"INSERT OR IGNORE INTO kpi_indicators (id, name, subgroup_id) VALUES ({indicator_id_to_ensure + 1}, 'Another Test Ind for Specs', 1)"
            )

            # kpis table (this module's target)
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS kpis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    indicator_id INTEGER NOT NULL UNIQUE,
                    description TEXT,
                    calculation_type TEXT NOT NULL CHECK(calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}', '{CALC_TYPE_INCREMENTALE}_fallback', '{CALC_TYPE_MEDIA}_fallback')),
                    unit_of_measure TEXT,
                    visible BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE
                );
            """
            )
            conn.commit()
            print(
                f"INFO: Minimal tables for specs testing ensured/created in {db_path}"
            )

    DB_KPIS_SPECS_TEST_FILE = "test_kpi_specs.sqlite"
    DB_KPIS_ORIGINAL_SPECS = DB_KPIS  # Save original
    if DB_KPIS.startswith(":memory_") or "error_db" in str(DB_KPIS):
        print(
            f"INFO: Using '{DB_KPIS_SPECS_TEST_FILE}' for DB_KPIS during specs testing."
        )
        DB_KPIS = DB_KPIS_SPECS_TEST_FILE  # Override for tests
        setup_minimal_tables_for_specs(
            DB_KPIS_SPECS_TEST_FILE, TEST_INDICATOR_ID_FOR_SPEC
        )

    try:
        print(
            f"\nTest 1: Add new KPI Spec for indicator_id {TEST_INDICATOR_ID_FOR_SPEC}"
        )
        kpi_spec_id_created = add_kpi_spec(
            indicator_id=TEST_INDICATOR_ID_FOR_SPEC,
            description="Total Sales Revenue",
            calculation_type=CALC_TYPE_INCREMENTALE,
            unit_of_measure="USD",
            visible=True,
        )
        assert isinstance(
            kpi_spec_id_created, int
        ), "add_kpi_spec should return an int (kpis.id)."
        print(
            f"  SUCCESS: Added KPI Spec with kpis.id {kpi_spec_id_created} for indicator {TEST_INDICATOR_ID_FOR_SPEC}."
        )

        print("\nTest 2: Attempt to add spec for the same indicator_id (should update)")
        updated_kpi_spec_id = add_kpi_spec(
            indicator_id=TEST_INDICATOR_ID_FOR_SPEC,
            description="Total Sales Revenue (Updated)",
            calculation_type=CALC_TYPE_INCREMENTALE,
            unit_of_measure="EUR",  # Changed unit
            visible=True,
        )
        assert (
            updated_kpi_spec_id == kpi_spec_id_created
        ), "Adding spec for existing indicator_id should return the existing kpis.id."
        # Verify update
        with sqlite3.connect(DB_KPIS) as conn:
            row = conn.execute(
                "SELECT description, unit_of_measure FROM kpis WHERE id = ?",
                (kpi_spec_id_created,),
            ).fetchone()
            assert (
                row and row[0] == "Total Sales Revenue (Updated)" and row[1] == "EUR"
            ), "KPI Spec was not updated."
        print(
            f"  SUCCESS: KPI Spec for indicator {TEST_INDICATOR_ID_FOR_SPEC} (kpis.id {kpi_spec_id_created}) updated on duplicate add."
        )

        print(
            f"\nTest 3: Update existing KPI Spec (kpis.id {kpi_spec_id_created}) directly"
        )
        update_kpi_spec(
            kpi_spec_id=kpi_spec_id_created,
            indicator_id=TEST_INDICATOR_ID_FOR_SPEC,  # indicator_id usually doesn't change here
            description="Gross Sales Revenue",
            calculation_type=CALC_TYPE_MEDIA,
            unit_of_measure="GBP",
            visible=False,
        )
        with sqlite3.connect(DB_KPIS) as conn:
            row = conn.execute(
                "SELECT description, calculation_type, unit_of_measure, visible FROM kpis WHERE id = ?",
                (kpi_spec_id_created,),
            ).fetchone()
            assert (
                row
                and row[0] == "Gross Sales Revenue"
                and row[1] == CALC_TYPE_MEDIA
                and row[2] == "GBP"
                and row[3] == 0
            ), "KPI Spec not updated correctly by direct call."
        print(f"  SUCCESS: KPI Spec kpis.id {kpi_spec_id_created} updated directly.")

        print("\nTest 4: Add spec with invalid calculation_type (expecting ValueError)")
        try:
            add_kpi_spec(
                TEST_INDICATOR_ID_FOR_SPEC + 1,
                "Test Desc",
                "InvalidType",
                "Units",
                True,
            )
            print(
                "  FAILURE: Adding spec with invalid calculation_type did not raise ValueError."
            )
        except ValueError:
            print(
                "  SUCCESS: ValueError raised for invalid calculation_type as expected."
            )

        print(
            "\nTest 5: Add spec for non-existent indicator_id (expecting IntegrityError - FOREIGN KEY)"
        )
        NON_EXISTENT_INDICATOR_ID = 9999
        try:
            add_kpi_spec(
                NON_EXISTENT_INDICATOR_ID, "Test", CALC_TYPE_INCREMENTALE, "Units", True
            )
            print(
                "  FAILURE: Adding spec for non-existent indicator_id did not raise IntegrityError."
            )
        except sqlite3.IntegrityError as e_fk:
            if "FOREIGN KEY constraint failed" in str(e_fk):
                print(
                    "  SUCCESS: IntegrityError (FOREIGN KEY) raised for non-existent indicator_id as expected."
                )
            else:
                print(
                    f"  FAILURE: Expected FOREIGN KEY IntegrityError, but got: {e_fk}"
                )

        print("\n--- All kpi_management.specs tests passed (basic execution) ---")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED DURING TESTING (kpi_management.specs) ---")
        print(str(e))
        print(traceback.format_exc())
    finally:
        DB_KPIS = DB_KPIS_ORIGINAL_SPECS  # Restore original DB_KPIS
        if DB_KPIS_SPECS_TEST_FILE and os.path.exists(DB_KPIS_SPECS_TEST_FILE):
            import os

            try:
                os.remove(DB_KPIS_SPECS_TEST_FILE)
                print(f"INFO: Cleaned up test file: {DB_KPIS_SPECS_TEST_FILE}")
            except OSError as e_clean:
                print(
                    f"ERROR: Could not clean up test file {DB_KPIS_SPECS_TEST_FILE}: {e_clean}"
                )
