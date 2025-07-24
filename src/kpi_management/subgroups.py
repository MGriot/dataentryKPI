# your_project_root/kpi_management/subgroups.py
import sqlite3
import traceback
import app_config
from pathlib import Path

# CALC_TYPE constants might be needed by _apply_template_indicator_to_new_subgroup
# if it directly constructs kpis records.
from gui.shared.constants import CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA

# --- Module Availability Flags & Mock Definitions ---
_data_retriever_available = False
_indicators_module_available = False
_templates_module_propagate_available = False
_specs_module_available = False

try:
    from data_retriever import get_template_defined_indicators, get_kpi_subgroup_by_id_with_template_name
    _data_retriever_available = True
except ImportError:
    print("WARNING: data_retriever not fully available for subgroups.py. Mocks being used.")
    def get_template_defined_indicators(template_id): return []
    def get_kpi_subgroup_by_id_with_template_name(subgroup_id): return None

try:
    from .indicators import add_kpi_indicator, delete_kpi_indicator
    _indicators_module_available = True
except ImportError:
    print("WARNING: kpi_management.indicators not available for subgroups.py. Mocks being used.")
    def add_kpi_indicator(name, subgroup_id): return None
    def delete_kpi_indicator(indicator_id): pass

try:
    # This function is responsible for creating/updating indicators and specs based on template changes.
    # It's assumed to be in templates.py
    from .templates import _propagate_template_indicator_change
    _templates_module_propagate_available = True
except ImportError:
    print("WARNING: kpi_management.templates._propagate_template_indicator_change not available. Mocks being used.")
    def _propagate_template_indicator_change(template_id, indicator_definition, action, specific_subgroup_ids=None): pass

try:
    from .specs import add_kpi_spec # For _apply_template_indicator_to_new_subgroup
    _specs_module_available = True
except ImportError:
    print("WARNING: kpi_management.specs.add_kpi_spec not available for subgroups.py. Mocks being used.")
    def add_kpi_spec(indicator_id, description, calculation_type, unit_of_measure, visible): return None


# --- Helper Function to Apply Template Indicators to a New/Updated Subgroup ---
def _apply_template_indicator_to_new_subgroup(subgroup_id: int, indicator_definition: dict):
    """
    When a new subgroup is created and linked to a template, or an existing subgroup
    is linked to a new template, this function creates the actual kpi_indicator
    and kpis spec records for that subgroup based on the template definition.

    Args:
        subgroup_id (int): The ID of the subgroup.
        indicator_definition (dict): A dictionary representing a single indicator
                                     definition from a kpi_indicator_template.
                                     Expected keys: 'indicator_name_in_template',
                                     'default_description', 'default_calculation_type',
                                     'default_unit_of_measure', 'default_visible'.
    """
    if not _indicators_module_available or not _specs_module_available:
        print("ERROR (_apply_template): Missing 'indicators' or 'specs' module. Cannot apply template.")
        return

    db_kpis_path = app_config.get_database_path("db_kpis.db")
    if not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({db_kpis_path}). Cannot apply template to subgroup."
        )

    indicator_name = indicator_definition.get("indicator_name_in_template")
    desc = indicator_definition.get("default_description", "")
    calc_type = indicator_definition.get("default_calculation_type", CALC_TYPE_INCREMENTALE)
    unit = indicator_definition.get("default_unit_of_measure", "")
    visible = bool(indicator_definition.get("default_visible", True))

    if not indicator_name:
        print("ERROR (_apply_template): 'indicator_name_in_template' missing in definition. Skipping.")
        return

    print(f"  Applying template indicator '{indicator_name}' to subgroup {subgroup_id}...")
    try:
        # 1. Create the kpi_indicator record
        # add_kpi_indicator will return existing ID if name/subgroup_id combo exists.
        actual_indicator_id = add_kpi_indicator(name=indicator_name, subgroup_id=subgroup_id)

        if not actual_indicator_id:
            print(f"  ERROR (_apply_template): Failed to create/retrieve indicator '{indicator_name}' for subgroup {subgroup_id}.")
            return

        # 2. Create/Update the kpis spec record for this new/existing indicator
        # add_kpi_spec will update if a spec for actual_indicator_id already exists.
        add_kpi_spec(
            indicator_id=actual_indicator_id,
            description=desc,
            calculation_type=calc_type,
            unit_of_measure=unit,
            visible=visible,
        )
        print(f"    Applied/Updated spec for indicator ID {actual_indicator_id} ('{indicator_name}') in subgroup {subgroup_id}.")

    except Exception as e:
        print(f"ERROR (_apply_template): Failed to apply indicator definition '{indicator_name}' to subgroup {subgroup_id}. Details: {e}")
        print(traceback.format_exc())


# --- KPI Subgroup CRUD Operations ---

def add_kpi_subgroup(name: str, group_id: int, indicator_template_id: int = None) -> int:
    """
    Adds a new KPI subgroup. If an indicator_template_id is provided,
    it applies the indicators defined in that template to the new subgroup.

    Args:
        name (str): The name of the subgroup. Must be unique within the group.
        group_id (int): The ID of the parent KPI group.
        indicator_template_id (int, optional): The ID of a kpi_indicator_template to link.

    Returns:
        int: The ID of the newly created KPI subgroup.

    Raises:
        sqlite3.IntegrityError: If name/group_id is not unique, or group_id is invalid.
        Exception: For other database or processing errors.
    """
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    if not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({db_kpis_path}). Cannot add subgroup."
        )
    if indicator_template_id and (not _data_retriever_available) :
        print("WARNING: Data retriever not available. Cannot apply template indicators if template_id is provided.")


    subgroup_id = None
    with sqlite3.connect(db_kpis_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_subgroups (name, group_id, indicator_template_id) VALUES (?,?,?)",
                (name, group_id, indicator_template_id),
            )
            subgroup_id = cursor.lastrowid
            conn.commit()
            print(f"INFO: KPI Subgroup '{name}' (group {group_id}) added successfully with ID: {subgroup_id}.")
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                 print(f"ERROR: Could not add subgroup '{name}'. It likely already exists in group {group_id}. Details: {e}")
            elif "FOREIGN KEY constraint failed" in str(e):
                 print(f"ERROR: Could not add subgroup '{name}'. Parent group ID {group_id} likely does not exist. Details: {e}")
            else:
                print(f"ERROR: IntegrityError while adding subgroup '{name}'. Details: {e}")
            raise
        except sqlite3.Error as e_general:
            print(f"ERROR: Database error while adding subgroup '{name}'. Details: {e_general}")
            print(traceback.format_exc())
            raise Exception(f"A database error occurred while adding subgroup '{name}'.") from e_general

    if subgroup_id and indicator_template_id and _data_retriever_available:
        print(f"  Applying template ID {indicator_template_id} to new subgroup ID {subgroup_id}...")
        try:
            template_indicators = get_template_defined_indicators(indicator_template_id)
            if not template_indicators:
                print(f"  Template ID {indicator_template_id} has no defined indicators to apply.")
            for ind_def in template_indicators:
                _apply_template_indicator_to_new_subgroup(subgroup_id, dict(ind_def)) # Pass as dict
            print(f"  Finished applying template indicators for subgroup {subgroup_id}.")
        except Exception as e_apply:
            # Log error but don't necessarily fail the subgroup creation itself.
            # The subgroup is created; template application is an enhancement.
            print(f"ERROR: Failed to apply all indicators from template {indicator_template_id} to subgroup {subgroup_id}. Details: {e_apply}")
            print(traceback.format_exc())
            # Consider if this should raise an error that rolls back or if partial success is okay.

    return subgroup_id


def update_kpi_subgroup(subgroup_id: int, new_name: str, group_id: int, new_template_id: int = None):
    """
    Updates an existing KPI subgroup's name, parent group, and linked template.
    Handles changes in template linkage by adding/removing/updating indicators.

    Args:
        subgroup_id (int): The ID of the subgroup to update.
        new_name (str): The new name for the subgroup.
        group_id (int): The new parent group ID.
        new_template_id (int, optional): The new kpi_indicator_template ID.
                                         None to unlink from any template.
    Raises:
        ValueError: If subgroup_id is not found.
        sqlite3.IntegrityError: For constraint violations (e.g. duplicate name/group, invalid group_id).
        Exception: For other errors.
    """
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    if not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({db_kpis_path}). Cannot update subgroup."
        )
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    if not isinstance(db_kpi_templates_path, Path) or not db_kpi_templates_path.parent.exists():
        raise ConnectionError(
            f"DB_KPI_TEMPLATES is not properly configured ({db_kpi_templates_path}). Cannot update subgroup."
        )

    if not _data_retriever_available or not _templates_module_propagate_available:
         print("WARNING: Data retriever or templates._propagate module not available. Template change logic will be skipped or mocked.")


    current_subgroup_info_dict = None
    if _data_retriever_available:
        current_subgroup_info = get_kpi_subgroup_by_id_with_template_name(subgroup_id)
        if current_subgroup_info:
            current_subgroup_info_dict = dict(current_subgroup_info)
        else:
            print(f"ERROR: KPI Subgroup with ID {subgroup_id} not found. Cannot update.")
            raise ValueError(f"KPI Subgroup with ID {subgroup_id} not found.")
    else: # If data_retriever is mocked, we can't get current state easily. Proceed with caution.
        print(f"WARNING: Cannot fetch current subgroup info for ID {subgroup_id} due to missing data_retriever.")
        # We need at least the old template ID for comparison. We'll have to query it directly if possible.
        with sqlite3.connect(db_kpis_path) as conn_read_old_tpl:
            row = conn_read_old_tpl.execute("SELECT indicator_template_id, name FROM kpi_subgroups WHERE id = ?", (subgroup_id,)).fetchone()
            if not row:
                print(f"ERROR: KPI Subgroup with ID {subgroup_id} not found (direct query). Cannot update.")
                raise ValueError(f"KPI Subgroup with ID {subgroup_id} not found.")
            current_subgroup_info_dict = {"indicator_template_id": row[0], "name": row[1]}


    old_template_id = current_subgroup_info_dict.get("indicator_template_id") if current_subgroup_info_dict else None

    with sqlite3.connect(db_kpis_path) as conn_update:
        try:
            cursor = conn_update.cursor()
            cursor.execute(
                "UPDATE kpi_subgroups SET name = ?, group_id = ?, indicator_template_id = ? WHERE id = ?",
                (new_name, group_id, new_template_id, subgroup_id),
            )
            conn_update.commit()
            if cursor.rowcount == 0:
                # Should have been caught by the check above, but as a safeguard.
                print(f"ERROR: KPI Subgroup ID {subgroup_id} not found during UPDATE. This is unexpected.")
                raise ValueError(f"KPI Subgroup ID {subgroup_id} disappeared during update.")
            print(f"INFO: KPI Subgroup ID {subgroup_id} updated to name '{new_name}', group {group_id}, template {new_template_id}.")
        except sqlite3.IntegrityError as e:
            # Handle potential UNIQUE constraint on (name, group_id) or invalid group_id (FOREIGN KEY)
            print(f"ERROR: Could not update subgroup ID {subgroup_id}. Name/group combo might be duplicate, or group_id invalid. Details: {e}")
            raise
        except sqlite3.Error as e_general:
            print(f"ERROR: Database error while updating subgroup ID {subgroup_id}. Details: {e_general}")
            print(traceback.format_exc())
            raise Exception(f"A database error occurred while updating subgroup ID {subgroup_id}.") from e_general

    # Handle template change logic
    if old_template_id != new_template_id:
        print(f"  Template for subgroup {subgroup_id} ('{new_name}') changed from {old_template_id} to {new_template_id}.")

        if not _data_retriever_available or not _templates_module_propagate_available:
            print("  WARNING: Skipping detailed template propagation due to missing modules.")
            return # Cannot proceed with detailed propagation

        # Phase 1: If old template existed, effectively "remove" its influence
        # _propagate_template_indicator_change with action 'remove' will delete indicators
        # that were defined by the old template IF they are not part of the new template.
        # This is a complex interaction. The original _propagate handled this.
        if old_template_id is not None:
            print(f"    Processing removal of indicators from old template {old_template_id} (if not in new)...")
            template_definitions = get_template_defined_indicators(old_template_id)
            for old_def_row in template_definitions:
                old_def = dict(old_def_row)
                # We need to check if this definition is ALSO in the new template.
                # If it is, _propagate_template_indicator_change with 'add_or_update' later will handle it.
                # If it's NOT in the new template, then it should be removed.
                is_in_new_template = False
                if new_template_id is not None:
                    new_template_definitions_check = get_template_defined_indicators(new_template_id)
                    for new_def_check_row in new_template_definitions_check:
                        if dict(new_def_check_row)['indicator_name_in_template'] == old_def['indicator_name_in_template']:
                            is_in_new_template = True
                            break
                if not is_in_new_template:
                     print(f"      Indicator '{old_def['indicator_name_in_template']}' from old template is NOT in new. Marking for removal via _propagate.")
                     _propagate_template_indicator_change(
                        template_id=old_template_id, # The template that *defined* this indicator
                        indicator_definition=old_def,
                        action="remove", # This tells propagate to remove the corresponding indicator/spec
                        specific_subgroup_ids=[subgroup_id]
                    )
                else:
                    print(f"      Indicator '{old_def['indicator_name_in_template']}' from old template IS ALSO in new. Update will handle.")


        # Phase 2: If new template exists, apply its definitions.
        # _apply_template_indicator_to_new_subgroup handles adding/updating indicators & specs.
        # Alternatively, _propagate_template_indicator_change with 'add_or_update'
        # could be used if it's more aligned with template-driven changes.
        # Using _apply_template_indicator_to_new_subgroup for direct application here.
        if new_template_id is not None:
            print(f"    Applying/Updating indicators from new template {new_template_id}...")
            new_template_definitions = get_template_defined_indicators(new_template_id)
            if not new_template_definitions:
                 print(f"    New template ID {new_template_id} has no defined indicators.")
            for new_def_row in new_template_definitions:
                _apply_template_indicator_to_new_subgroup(subgroup_id, dict(new_def_row))
            print(f"  Finished applying/updating indicators from new template {new_template_id} for subgroup {subgroup_id}.")


def delete_kpi_subgroup(subgroup_id: int):
    """
    Deletes a KPI subgroup and all its associated kpi_indicators.
    The deletion of kpi_indicators will, in turn, trigger cascading deletes
    for their kpis specs and related target data via `delete_kpi_indicator`.

    Args:
        subgroup_id (int): The ID of the subgroup to delete.
    Raises:
        ImportError: If kpi_management.indicators.delete_kpi_indicator is not available.
        Exception: For database or processing errors.
    """
    print(f"INFO: Initiating deletion of KPI Subgroup ID {subgroup_id} and its contents.")

    if not _indicators_module_available:
        msg = "ERROR: Cannot proceed with delete_kpi_subgroup. Missing dependency: kpi_management.indicators.delete_kpi_indicator."
        print(msg)
        raise ImportError(msg)
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    if not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({db_kpis_path}). Cannot delete subgroup."
        )


    indicators_in_subgroup_ids = []
    try:
        with sqlite3.connect(db_kpis_path) as conn_read:
            conn_read.row_factory = sqlite3.Row
            indicators_rows = conn_read.execute(
                "SELECT id FROM kpi_indicators WHERE subgroup_id = ?", (subgroup_id,)
            ).fetchall()
            indicators_in_subgroup_ids = [ind_row["id"] for ind_row in indicators_rows]
            print(f"  Found {len(indicators_in_subgroup_ids)} indicators in subgroup {subgroup_id} for deletion.")
    except sqlite3.Error as e:
        print(f"ERROR: Database error while collecting indicators for subgroup {subgroup_id} deletion. Details: {e}")
        print(traceback.format_exc())
        raise Exception(f"Failed to collect indicators for subgroup {subgroup_id} due to a database error.") from e

    # Explicitly delete each indicator within the subgroup.
    # `delete_kpi_indicator` handles the full cleanup cascade.
    for ind_id in indicators_in_subgroup_ids:
        try:
            print(f"  Calling delete_kpi_indicator for indicator ID: {ind_id} (part of subgroup {subgroup_id})")
            delete_kpi_indicator(ind_id)
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to delete indicator ID {ind_id} (part of subgroup {subgroup_id}). Halting subgroup deletion. Details: {e}")
            print(traceback.format_exc())
            raise Exception(f"Failed to delete child indicator ID {ind_id} for subgroup {subgroup_id}. Subgroup deletion incomplete.") from e

    # After all indicators are deleted, delete the subgroup itself.
    print(f"  Proceeding to delete the kpi_subgroups entry for ID {subgroup_id}.")
    with sqlite3.connect(db_kpis_path) as conn_delete_sg:
        try:
            conn_delete_sg.execute("PRAGMA foreign_keys = ON;") # Good practice
            cursor = conn_delete_sg.cursor()
            cursor.execute("DELETE FROM kpi_subgroups WHERE id = ?", (subgroup_id,))
            conn_delete_sg.commit()
            if cursor.rowcount == 0:
                print(f"WARNING: No KPI subgroup with ID {subgroup_id} found during final delete. It might have been deleted already.")
            else:
                print(f"INFO: KPI Subgroup ID {subgroup_id} deleted successfully.")
        except sqlite3.Error as e:
            print(f"ERROR: Database error while deleting kpi_subgroups entry for ID {subgroup_id}. Details: {e}")
            print(traceback.format_exc())
            raise Exception(f"Database error when deleting kpi_subgroups entry for ID {subgroup_id}.") from e


if __name__ == "__main__":
    print("--- Running kpi_management/subgroups.py for testing ---")
    # This requires kpi_groups, kpi_indicator_templates, kpi_indicators, kpis tables to exist.

    TEST_GROUP_ID = 1
    TEST_TEMPLATE_ID = 1 # Assume a template exists with this ID for some tests
    subgroup_id_created = None
    indicator_id_in_subgroup = None

    def setup_minimal_tables_for_subgroups(db_kpis_path, db_templates_path, group_id, template_id):
        # Setup in DB_KPIS
        with sqlite3.connect(db_kpis_path) as conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS kpi_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);")
            cur.execute("INSERT OR IGNORE INTO kpi_groups (id, name) VALUES (?, 'Test Group for Subgroups')", (group_id,))
            cur.execute("""CREATE TABLE IF NOT EXISTS kpi_subgroups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, group_id INTEGER NOT NULL,
                           indicator_template_id INTEGER,
                           FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE,
                           FOREIGN KEY (indicator_template_id) REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL,
                           UNIQUE (name, group_id));""")
            cur.execute("""CREATE TABLE IF NOT EXISTS kpi_indicators (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subgroup_id INTEGER NOT NULL,
                           FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE, UNIQUE (name, subgroup_id));""")
            cur.execute(f"""CREATE TABLE IF NOT EXISTS kpis (id INTEGER PRIMARY KEY AUTOINCREMENT, indicator_id INTEGER NOT NULL UNIQUE, description TEXT,
                           calculation_type TEXT NOT NULL CHECK(calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}')),
                           unit_of_measure TEXT, visible BOOLEAN DEFAULT 1,
                           FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE);""")
            conn.commit()

        # Setup in DB_KPI_TEMPLATES
        with sqlite3.connect(db_templates_path) as conn_tpl:
            cur_tpl = conn_tpl.cursor()
            cur_tpl.execute("CREATE TABLE IF NOT EXISTS kpi_indicator_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT);")
            cur_tpl.execute("INSERT OR IGNORE INTO kpi_indicator_templates (id, name, description) VALUES (?, 'Test Template for Subgroups', 'Desc')", (template_id,))
            cur_tpl.execute(f"""CREATE TABLE IF NOT EXISTS template_defined_indicators (id INTEGER PRIMARY KEY AUTOINCREMENT, template_id INTEGER NOT NULL,
                               indicator_name_in_template TEXT NOT NULL, default_description TEXT,
                               default_calculation_type TEXT NOT NULL CHECK(default_calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}')),
                               default_unit_of_measure TEXT, default_visible BOOLEAN DEFAULT 1,
                               FOREIGN KEY (template_id) REFERENCES kpi_indicator_templates(id) ON DELETE CASCADE,
                               UNIQUE (template_id, indicator_name_in_template));""")
            # Add a definition to the test template
            cur_tpl.execute("""INSERT OR IGNORE INTO template_defined_indicators
                               (template_id, indicator_name_in_template, default_calculation_type, default_unit_of_measure)
                               VALUES (?, 'Tpl Ind 1', ?, 'Units')""", (template_id, CALC_TYPE_INCREMENTALE))
            cur_tpl.execute("""INSERT OR IGNORE INTO template_defined_indicators
                               (template_id, indicator_name_in_template, default_calculation_type, default_unit_of_measure)
                               VALUES (?, 'Tpl Ind 2', ?, 'Count')""", (template_id, CALC_TYPE_MEDIA))
            conn_tpl.commit()
        print(f"INFO: Minimal tables for subgroups testing ensured/created in {db_kpis_path} and {db_templates_path}")


    test_db_file_kpis = "test_kpi_subgroups_kpis.sqlite"
    test_db_file_templates = "test_kpi_subgroups_templates.sqlite"
    # Save original app_config settings for database paths
    original_db_base_dir = app_config.SETTINGS["database_base_dir"]

    # Create dummy DB files for testing if they don't exist
    if not Path(test_db_file_kpis).exists():
        Path(test_db_file_kpis).touch()
    if not Path(test_db_file_templates).exists():
        Path(test_db_file_templates).touch()

    # Temporarily set app_config to use the test files' directory
    app_config.SETTINGS["database_base_dir"] = str(Path(test_db_file_kpis).parent)

    # Setup minimal tables for subgroups
    setup_minimal_tables_for_subgroups(app_config.get_database_path("db_kpis.db"), app_config.get_database_path("db_kpi_templates.db"), TEST_GROUP_ID, TEST_TEMPLATE_ID)

    try:
        print(f"\nTest 1: Add new subgroup 'Sales Team A' to group {TEST_GROUP_ID} (no template)")
        subgroup_id_created = add_kpi_subgroup("Sales Team A", TEST_GROUP_ID)
        assert isinstance(subgroup_id_created, int)
        print(f"  SUCCESS: Added 'Sales Team A' with ID {subgroup_id_created}")

        print(f"\nTest 2: Add new subgroup 'Support Team B' to group {TEST_GROUP_ID} WITH template {TEST_TEMPLATE_ID}")
        # This requires data_retriever, indicators, and specs modules to be working or mocked.
        if not _data_retriever_available or not _indicators_module_available or not _specs_module_available:
            print("  SKIPPING Test 2 due to missing dependencies for template application.")
        else:
            subgroup_id_with_template = add_kpi_subgroup("Support Team B", TEST_GROUP_ID, indicator_template_id=TEST_TEMPLATE_ID)
            assert isinstance(subgroup_id_with_template, int)
            print(f"  SUCCESS: Added 'Support Team B' with ID {subgroup_id_with_template} and applied template.")
            # Verification: Check if indicators from template were created in DB_KPIS
            with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
                indicators_from_tpl = conn.execute("SELECT name FROM kpi_indicators WHERE subgroup_id = ?", (subgroup_id_with_template,)).fetchall()
                indicator_names_from_tpl = {row[0] for row in indicators_from_tpl}
                assert "Tpl Ind 1" in indicator_names_from_tpl and "Tpl Ind 2" in indicator_names_from_tpl
                print(f"    Verified: Indicators 'Tpl Ind 1', 'Tpl Ind 2' created for subgroup {subgroup_id_with_template}.")


        print(f"\nTest 3: Update subgroup {subgroup_id_created} name and link to template {TEST_TEMPLATE_ID}")
        if not _data_retriever_available or not _templates_module_propagate_available or not _specs_module_available:
            print("  SKIPPING Test 3 due to missing dependencies for template update logic.")
        else:
            update_kpi_subgroup(subgroup_id_created, "Sales Team Alpha", TEST_GROUP_ID, new_template_id=TEST_TEMPLATE_ID)
            # Verification
            with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
                row = conn.execute("SELECT name, indicator_template_id FROM kpi_subgroups WHERE id = ?", (subgroup_id_created,)).fetchone()
                assert row and row[0] == "Sales Team Alpha" and row[1] == TEST_TEMPLATE_ID
                indicators_after_update = conn.execute("SELECT name FROM kpi_indicators WHERE subgroup_id = ?", (subgroup_id_created,)).fetchall()
                indicator_names_after_update = {r[0] for r in indicators_after_update}
                assert "Tpl Ind 1" in indicator_names_after_update
            print(f"  SUCCESS: Subgroup {subgroup_id_created} updated and template indicators applied.")


        print(f"\nTest 4: Delete subgroup {subgroup_id_created} ('Sales Team Alpha')")
        # This requires indicators module to be working for cascading delete test.
        if not _indicators_module_available:
             print("  SKIPPING Test 4 due to missing indicators module for full delete cascade.")
        else:
            # If indicators were created (e.g. from template in Test 3), they should be deleted.
            delete_kpi_subgroup(subgroup_id_created)
            with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
                row = conn.execute("SELECT id FROM kpi_subgroups WHERE id = ?", (subgroup_id_created,)).fetchone()
                assert row is None, "Subgroup was not deleted."
                indicators_left = conn.execute("SELECT id FROM kpi_indicators WHERE subgroup_id = ?", (subgroup_id_created,)).fetchall()
                assert not indicators_left, "Indicators within the deleted subgroup were not cleaned up."
            print(f"  SUCCESS: Subgroup {subgroup_id_created} and its indicators deleted.")
            subgroup_id_created = None # Mark as deleted


        print("\n--- All kpi_management.subgroups tests passed (basic execution) ---")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED DURING TESTING (kpi_management.subgroups) ---")
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
                print(f"ERROR: Could not clean up test file {test_db_file_kpis}: {e_clean}")
        if Path(test_db_file_templates).exists():
            import os
            try:
                os.remove(test_db_file_templates)
                print(f"INFO: Cleaned up test file: {test_db_file_templates}")
            except OSError as e_clean:
                print(f"ERROR: Could not clean up test file {test_db_file_templates}: {e_clean}")