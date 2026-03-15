# src/kpi_management/specs.py
import sqlite3
import traceback
from src.config import settings as app_config
from pathlib import Path # Ensure Path is imported

from src.config.settings import CALC_TYPE_INCREMENTAL, CALC_TYPE_AVERAGE

# --- KPI Specification (kpis table) CRUD Operations ---


def add_kpi_spec(
    indicator_id: int,
    description: str,
    calculation_type: str,
    unit_of_measure: str,
    visible: bool,
    formula_json: str = None,
    formula_string: str = None,
    is_calculated: bool = False,
    default_distribution_profile: str = None,
) -> int:
    """
    Adds a new KPI specification (a record in the 'kpis' table).
    If a spec for the given indicator_id already exists, it attempts to update it.
    """
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    if not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({db_kpis_path}). Cannot add KPI spec."
        )

    allowed_calc_types = [CALC_TYPE_INCREMENTAL, CALC_TYPE_AVERAGE]
    if calculation_type not in allowed_calc_types:
        msg = f"Invalid calculation_type: '{calculation_type}'. Must be one of {allowed_calc_types}."
        print(f"ERROR: {msg}")
        raise ValueError(msg)

    with sqlite3.connect(db_kpis_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible, formula_json, formula_string, is_calculated, default_distribution_profile)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    indicator_id,
                    description,
                    calculation_type,
                    unit_of_measure,
                    1 if visible else 0,
                    formula_json,
                    formula_string,
                    1 if is_calculated else 0,
                    default_distribution_profile,
                ),
            )
            conn.commit()
            kpi_spec_id = cursor.lastrowid
            return kpi_spec_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kpis.indicator_id" in str(e):
                # Spec for this indicator_id already exists, attempt to update it.
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM kpis WHERE indicator_id=?", (indicator_id,))
                existing_kpi_row = cursor.fetchone()
                if existing_kpi_row:
                    existing_kpi_spec_id = existing_kpi_row[0]
                    cursor.execute(
                        """UPDATE kpis SET description=?, calculation_type=?,
                           unit_of_measure=?, visible=?, formula_json=?, formula_string=?, is_calculated=?, default_distribution_profile=? WHERE id=?""",
                        (
                            description,
                            calculation_type,
                            unit_of_measure,
                            1 if visible else 0,
                            formula_json,
                            formula_string,
                            1 if is_calculated else 0,
                            default_distribution_profile,
                            existing_kpi_spec_id,
                        ),
                    )
                    conn.commit()
                    return existing_kpi_spec_id
                raise
            raise

def update_kpi_spec(
    kpi_spec_id: int,
    indicator_id: int,
    description: str,
    calculation_type: str,
    unit_of_measure: str,
    visible: bool,
    formula_json: str = None,
    formula_string: str = None,
    is_calculated: bool = False,
    default_distribution_profile: str = None,
):
    """Updates an existing KPI specification."""
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_kpis_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE kpis SET indicator_id=?, description=?, calculation_type=?,
                   unit_of_measure=?, visible=?, formula_json=?, formula_string=?, is_calculated=?, default_distribution_profile=? WHERE id=?""",
                (
                    indicator_id,
                    description,
                    calculation_type,
                    unit_of_measure,
                    1 if visible else 0,
                    formula_json,
                    formula_string,
                    1 if is_calculated else 0,
                    default_distribution_profile,
                    kpi_spec_id,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR: Database error while updating KPI Spec {kpi_spec_id}: {e}")
            raise

def get_kpi_spec_by_indicator_id(indicator_id: int) -> dict | None:
    """Retrieves a KPI specification by its associated indicator ID."""
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_kpis_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, indicator_id, description, calculation_type, unit_of_measure, visible, formula_json, formula_string, is_calculated, default_distribution_profile
                   FROM kpis WHERE indicator_id = ?""",
                (indicator_id,),
            )
            row = cursor.fetchone()
            if row:
                spec_data = dict(row)
                spec_data["visible"] = bool(spec_data["visible"])
                spec_data["is_calculated"] = bool(spec_data["is_calculated"])
                return spec_data
            return None
        except sqlite3.Error as e:
            print(f"ERROR: Database error while retrieving KPI Spec: {e}")
            raise
            row = cursor.fetchone()
            if row:
                spec_data = dict(row)
                spec_data["visible"] = bool(spec_data["visible"])
                return spec_data
            return None
        except sqlite3.Error as e:
            print(f"ERROR: Database error while retrieving KPI Spec: {e}")
            raise


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
            # Dependencies: kpi_nodes
            cur.execute("CREATE TABLE IF NOT EXISTS kpi_nodes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, parent_id INTEGER, node_type TEXT, FOREIGN KEY (parent_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE, UNIQUE (name, parent_id));")
            cur.execute("INSERT OR IGNORE INTO kpi_nodes (id, name, node_type) VALUES (1, 'Test Group for Specs', 'group')")
            cur.execute("INSERT OR IGNORE INTO kpi_nodes (id, name, parent_id, node_type) VALUES (2, 'Test Subgroup for Specs', 1, 'subgroup')")

            # kpi_indicators table (parent for kpis)
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS kpi_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, node_id INTEGER NOT NULL, subgroup_id INTEGER,
                    FOREIGN KEY (node_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE,
                    UNIQUE (name, node_id));
            """
            )
            # Ensure the specific indicator_id exists
            cur.execute(
                "INSERT OR IGNORE INTO kpi_indicators (id, name, node_id) VALUES (?, ?, ?)",
                (indicator_id_to_ensure, f"Test Indicator {indicator_id_to_ensure}", 2),
            )
            cur.execute(
                f"INSERT OR IGNORE INTO kpi_indicators (id, name, node_id) VALUES ({indicator_id_to_ensure + 1}, 'Another Test Ind for Specs', 2)"
            )

            # kpis table (this module's target)
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS kpis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    indicator_id INTEGER NOT NULL UNIQUE,
                    description TEXT,
                    calculation_type TEXT NOT NULL CHECK(calculation_type IN ('{CALC_TYPE_INCREMENTAL}', '{CALC_TYPE_AVERAGE}')),
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

    test_db_file_kpis = "test_kpi_specs.sqlite"
    # Save original app_config settings for database paths
    original_db_base_dir = app_config.SETTINGS["database_base_dir"]

    # Create dummy DB file for testing if it doesn't exist
    if not Path(test_db_file_kpis).exists():
        Path(test_db_file_kpis).touch()

    # Temporarily set app_config to use the test file's directory
    app_config.SETTINGS["database_base_dir"] = str(Path(test_db_file_kpis).parent)

    # Setup minimal tables for specs testing
    setup_minimal_tables_for_specs(app_config.get_database_path("db_kpis.db"), TEST_INDICATOR_ID_FOR_SPEC)

    try:
        print(
            f"\nTest 1: Add new KPI Spec for indicator_id {TEST_INDICATOR_ID_FOR_SPEC}"
        )
        kpi_spec_id_created = add_kpi_spec(
            indicator_id=TEST_INDICATOR_ID_FOR_SPEC,
            description="Total Sales Revenue",
            calculation_type=CALC_TYPE_INCREMENTAL,
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
            calculation_type=CALC_TYPE_INCREMENTAL,
            unit_of_measure="EUR",  # Changed unit
            visible=True,
        )
        assert (
            updated_kpi_spec_id == kpi_spec_id_created
        ), "Adding spec for existing indicator_id should return the existing kpis.id."
        # Verify update
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
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
            calculation_type=CALC_TYPE_AVERAGE,
            unit_of_measure="GBP",
            visible=False,
        )
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            row = conn.execute(
                "SELECT description, calculation_type, unit_of_measure, visible FROM kpis WHERE id = ?",
                (kpi_spec_id_created,),
            ).fetchone()
            assert (
                row
                and row[0] == "Gross Sales Revenue"
                and row[1] == CALC_TYPE_AVERAGE
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
                NON_EXISTENT_INDICATOR_ID, "Test", CALC_TYPE_INCREMENTAL, "Units", True
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
        # Restore original app_config setting
        app_config.SETTINGS["database_base_dir"] = original_db_base_dir
        if Path(test_db_file_kpis).exists():
            import os

            try:
                os.remove(test_db_file_kpis)
                print(f"INFO: Cleaned up test file: {test_db_file_kpis}")
            except OSError as e_clean:
                print(
                    f"ERROR: Could not clean up test file {test_db_file_kpis}: {e_clean}"
                )