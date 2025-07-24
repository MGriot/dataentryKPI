# src/kpi_management/templates.py
import sqlite3
import traceback
import app_config
from pathlib import Path # Ensure Path is imported

from gui.shared.constants import CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA

# --- Module Availability Flags & Mock Definitions ---
_data_retriever_available = False
_indicators_module_available = False
_specs_module_available = False

try:
    from data_retriever import (
        get_template_indicator_definition_by_name,
        get_template_indicator_definition_by_id,
        get_template_defined_indicators # Used in delete_kpi_indicator_template
    )
    _data_retriever_available = True
except ImportError:
    print("WARNING: data_retriever not fully available for templates.py. Mocks being used.")
    def get_template_indicator_definition_by_name(template_id, indicator_name): return None
    def get_template_indicator_definition_by_id(definition_id): return None
    def get_template_defined_indicators(template_id): return []

try:
    # These are needed by _propagate_template_indicator_change
    from .indicators import add_kpi_indicator, delete_kpi_indicator
    _indicators_module_available = True
except ImportError:
    print("WARNING: kpi_management.indicators not available for templates.py. Mocks being used for _propagate.")
    def add_kpi_indicator(name, subgroup_id): return None # Returns ID
    def delete_kpi_indicator(indicator_id): pass

try:
    # Needed by _propagate_template_indicator_change
    from .specs import add_kpi_spec # To add/update the kpis record
    _specs_module_available = True
except ImportError:
    print("WARNING: kpi_management.specs not available for templates.py. Mocks being used for _propagate.")
    def add_kpi_spec(indicator_id, description, calculation_type, unit_of_measure, visible): return None # Returns ID


# --- Propagation Helper Function (Critical Logic) ---
def _propagate_template_indicator_change(
    template_id: int,
    indicator_definition: dict,
    action: str, # "add_or_update" or "remove"
    specific_subgroup_ids: list = None
):
    """
    Propagates changes from a template's indicator definition to all linked subgroups.
    If 'add_or_update': Creates/updates the corresponding kpi_indicator and kpis spec.
    If 'remove': Deletes the corresponding kpi_indicator (which cascades to kpis spec).

    Args:
        template_id (int): The ID of the template whose definition changed.
        indicator_definition (dict): The definition of the indicator that was
                                     added, updated, or removed from the template.
                                     Expected keys depend on action, but usually:
                                     'indicator_name_in_template', 'default_description',
                                     'default_calculation_type', etc.
        action (str): "add_or_update" or "remove".
        specific_subgroup_ids (list, optional): If provided, propagation is limited
                                                to these subgroup IDs. Otherwise,
                                                it applies to all subgroups linked
                                                to the template_id.
    """
    if not _indicators_module_available or not _specs_module_available:
        print(f"ERROR (_propagate): Missing 'indicators' or 'specs' module. Cannot propagate template change for indicator: {indicator_definition.get('indicator_name_in_template')}")
        return

    db_kpis_path = app_config.get_database_path("db_kpis.db")
    if not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError(f"DB_KPIS is not properly configured ({db_kpis_path}). Cannot propagate template change.")


    subgroups_to_update_rows = []
    print(f"  Propagating template (ID:{template_id}) change for indicator '{indicator_definition.get('indicator_name_in_template')}', action: {action}.")

    try:
        with sqlite3.connect(db_kpis_path) as conn_kpis_read:
            conn_kpis_read.row_factory = sqlite3.Row
            if specific_subgroup_ids:
                placeholders = ",".join("?" for _ in specific_subgroup_ids)
                query_sg = f"SELECT id FROM kpi_subgroups WHERE indicator_template_id = ? AND id IN ({placeholders})"
                params_sg = [template_id] + specific_subgroup_ids
                subgroups_to_update_rows = conn_kpis_read.execute(query_sg, params_sg).fetchall()
                print(f"    Targeting specific subgroups: {specific_subgroup_ids}")
            else:
                subgroups_to_update_rows = conn_kpis_read.execute(
                    "SELECT id FROM kpi_subgroups WHERE indicator_template_id = ?",
                    (template_id,),
                ).fetchall()
                print(f"    Targeting all subgroups linked to template {template_id}.")
    except sqlite3.Error as e_read:
        print(f"ERROR (_propagate): Database error fetching subgroups for template {template_id}. Details: {e_read}")
        print(traceback.format_exc())
        return # Cannot proceed

    if not subgroups_to_update_rows:
        print(f"    No subgroups found linked to template {template_id} (or specified list). No propagation needed.")
        return

    print(f"    Found {len(subgroups_to_update_rows)} subgroups for propagation.")

    # Actions are performed within a single connection to DB_KPIS for transactional integrity if possible,
    # though delete_kpi_indicator itself opens connections to other DBs.
    with sqlite3.connect(db_kpis_path) as conn_kpis_action:
        conn_kpis_action.row_factory = sqlite3.Row # For fetching existing_indicator
        conn_kpis_action.execute("PRAGMA foreign_keys = ON;")

        for sg_row in subgroups_to_update_rows:
            subgroup_id = sg_row["id"]
            indicator_name_in_subgroup = indicator_definition.get("indicator_name_in_template")

            if not indicator_name_in_subgroup:
                print(f"    ERROR (_propagate): 'indicator_name_in_template' missing in definition for subgroup {subgroup_id}. Skipping.")
                continue

            print(f"    Processing subgroup ID: {subgroup_id} for indicator '{indicator_name_in_subgroup}'")

            # Check if an indicator with this name already exists in this specific subgroup
            existing_indicator_row = conn_kpis_action.execute(
                "SELECT id FROM kpi_indicators WHERE name = ? AND subgroup_id = ?",
                (indicator_name_in_subgroup, subgroup_id),
            ).fetchone()
            existing_indicator_id = existing_indicator_row["id"] if existing_indicator_row else None

            if action == "add_or_update":
                actual_indicator_id = None
                if not existing_indicator_id:
                    print(f"      Indicator '{indicator_name_in_subgroup}' not found in subgroup {subgroup_id}. Adding...")
                    try:
                        # Use the add_kpi_indicator function from the indicators module
                        actual_indicator_id = add_kpi_indicator(name=indicator_name_in_subgroup, subgroup_id=subgroup_id)
                        if not actual_indicator_id: # Should not happen if add_kpi_indicator is robust
                             print(f"      ERROR (_propagate): add_kpi_indicator failed to return an ID for '{indicator_name_in_subgroup}'.")
                             continue
                        print(f"      Added kpi_indicator '{indicator_name_in_subgroup}' with ID {actual_indicator_id} to subgroup {subgroup_id}.")
                    except Exception as e_add_ind:
                        print(f"      ERROR (_propagate): Failed to add kpi_indicator '{indicator_name_in_subgroup}' to subgroup {subgroup_id}. Details: {e_add_ind}")
                        continue # Skip to next subgroup or definition
                else:
                    actual_indicator_id = existing_indicator_id
                    print(f"      Indicator '{indicator_name_in_subgroup}' (ID: {actual_indicator_id}) already exists in subgroup {subgroup_id}. Will update its spec.")

                if actual_indicator_id:
                    # Now add or update the kpis spec for this indicator
                    desc = indicator_definition.get("default_description", "")
                    calc = indicator_definition.get("default_calculation_type", CALC_TYPE_INCREMENTALE)
                    unit = indicator_definition.get("default_unit_of_measure", "")
                    vis = bool(indicator_definition.get("default_visible", True))
                    try:
                        # add_kpi_spec from specs module handles insert-or-update logic for the spec
                        add_kpi_spec(
                            indicator_id=actual_indicator_id, # This is kpi_indicators.id
                            description=desc,
                            calculation_type=calc,
                            unit_of_measure=unit,
                            visible=vis
                        )
                        print(f"      Applied/Updated kpis spec for indicator ID {actual_indicator_id} in subgroup {subgroup_id}.")
                    except Exception as e_add_spec:
                        print(f"      ERROR (_propagate): Failed to add/update kpis spec for indicator ID {actual_indicator_id}. Details: {e_add_spec}")
                        # Consider if this is a fatal error for this subgroup's propagation

            elif action == "remove":
                if existing_indicator_id:
                    print(f"      Indicator '{indicator_name_in_subgroup}' (ID: {existing_indicator_id}) found in subgroup {subgroup_id}. Removing...")
                    try:
                        # delete_kpi_indicator handles removal of spec and related target data
                        delete_kpi_indicator(existing_indicator_id)
                        print(f"      Removed indicator ID {existing_indicator_id} and its spec/targets from subgroup {subgroup_id}.")
                    except Exception as e_del_ind:
                        print(f"      ERROR (_propagate): Failed to delete indicator ID {existing_indicator_id} from subgroup {subgroup_id}. Details: {e_del_ind}")
                        # Consider if this is a fatal error
                else:
                    print(f"      Indicator '{indicator_name_in_subgroup}' not found in subgroup {subgroup_id}. No removal needed for this subgroup.")
        try:
            conn_kpis_action.commit() # Commit changes made within conn_kpis_action for this propagation run
            print(f"  Propagation changes committed for template {template_id}, indicator '{indicator_name_in_subgroup}'.")
        except sqlite3.Error as e_commit:
            print(f"ERROR (_propagate): Failed to commit changes for template {template_id}. Details: {e_commit}")
            # Consider rollback or other error handling


# --- KPI Indicator Template CRUD ---

def add_kpi_indicator_template(name: str, description: str = "") -> int:
    """Adds a new KPI indicator template."""
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    if not isinstance(db_kpi_templates_path, Path) or not db_kpi_templates_path.parent.exists():
        raise ConnectionError(f"DB_KPI_TEMPLATES is not properly configured ({db_kpi_templates_path}). Cannot add template.")
    with sqlite3.connect(db_kpi_templates_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_indicator_templates (name, description) VALUES (?,?)",
                (name, description),
            )
            conn.commit()
            template_id = cursor.lastrowid
            print(f"INFO: KPI Indicator Template '{name}' added with ID: {template_id}.")
            return template_id
        except sqlite3.IntegrityError:
            print(f"ERROR: KPI Indicator Template '{name}' already exists.")
            raise
        except sqlite3.Error as e:
            print(f"ERROR: Database error adding template '{name}': {e}")
            raise

def update_kpi_indicator_template(template_id: int, name: str, description: str):
    """
    Updates an existing KPI indicator template."""
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    if not isinstance(db_kpi_templates_path, Path) or not db_kpi_templates_path.parent.exists():
        raise ConnectionError(f"DB_KPI_TEMPLATES is not properly configured ({db_kpi_templates_path}). Cannot update template.")
    with sqlite3.connect(db_kpi_templates_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE kpi_indicator_templates SET name = ?, description = ? WHERE id = ?",
                (name, description, template_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(f"WARNING: No template found with ID {template_id} to update.")
            else:
                print(f"INFO: KPI Indicator Template ID {template_id} updated to name '{name}'.")
        except sqlite3.IntegrityError:
            print(f"ERROR: Cannot update template ID {template_id}. New name '{name}' might already exist.")
            raise
        except sqlite3.Error as e:
            print(f"ERROR: Database error updating template ID {template_id}: {e}")
            raise

def delete_kpi_indicator_template(template_id: int):
    """
    Deletes a KPI indicator template.
    This involves:
    1. Identifying all subgroups currently linked to this template.
    2. Getting all indicator definitions within this template.
    3. For each definition, propagating a "remove" action to the linked subgroups.
    4. Unlinking subgroups from this template (setting their indicator_template_id to NULL).
    5. Deleting the template itself and its definitions from DB_KPI_TEMPLATES.
    """
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    if not isinstance(db_kpi_templates_path, Path) or not db_kpi_templates_path.parent.exists() or \
       not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError("DB_KPI_TEMPLATES or DB_KPIS is not properly configured. Cannot delete template.")
    if not _data_retriever_available :
        print("WARNING (delete_template): data_retriever not available. Cannot fetch all template definitions for full cleanup.")

    print(f"INFO: Initiating deletion of KPI Indicator Template ID: {template_id}.")
    linked_subgroup_ids = []
    try:
        with sqlite3.connect(db_kpis_path) as conn_kpis_read:
            conn_kpis_read.row_factory = sqlite3.Row
            rows = conn_kpis_read.execute(
                "SELECT id FROM kpi_subgroups WHERE indicator_template_id = ?",
                (template_id,),
            ).fetchall()
            linked_subgroup_ids = [row["id"] for row in rows]
            print(f"  Template ID {template_id} is linked to {len(linked_subgroup_ids)} subgroups: {linked_subgroup_ids}")
    except sqlite3.Error as e_read_links:
        print(f"ERROR: Failed to fetch subgroups linked to template {template_id}. Details: {e_read_links}")
        raise

    definitions_in_template_rows = []
    if _data_retriever_available:
        definitions_in_template_rows = get_template_defined_indicators(template_id)
        print(f"  Template ID {template_id} has {len(definitions_in_template_rows)} indicator definitions.")

    # Propagate removal of each defined indicator to linked subgroups
    if linked_subgroup_ids and definitions_in_template_rows:
        print("  Propagating removal of template's indicators from linked subgroups...")
        for def_row in definitions_in_template_rows:
            def_dict = dict(def_row)
            try:
                _propagate_template_indicator_change(
                    template_id=template_id, # The template being deleted
                    indicator_definition=def_dict,
                    action="remove",
                    specific_subgroup_ids=linked_subgroup_ids
                )
            except Exception as e_prop_del:
                # Log and decide if fatal. For template deletion, it's safer to attempt all.
                print(f"    ERROR during propagation of removal for definition '{def_dict.get('indicator_name_in_template')}': {e_prop_del}")
    elif linked_subgroup_ids and not _data_retriever_available:
        print("  WARNING: Cannot propagate indicator removal - data_retriever was not available to get definitions.")


    # Unlink subgroups from this template (set their indicator_template_id to NULL)
    try:
        with sqlite3.connect(db_kpis_path) as conn_kpis_update:
            cursor = conn_kpis_update.cursor()
            cursor.execute(
                "UPDATE kpi_subgroups SET indicator_template_id = NULL WHERE indicator_template_id = ?",
                (template_id,),
            )
            conn_kpis_update.commit()
            print(f"  Unlinked {cursor.rowcount} subgroups from template ID {template_id}.")
    except sqlite3.Error as e_unlink:
        print(f"ERROR: Failed to unlink subgroups from template {template_id}. Details: {e_unlink}")
        raise # This is a critical step

    # Delete the template itself and its definitions (CASCADE should handle definitions)
    try:
        with sqlite3.connect(db_kpi_templates_path) as conn_tpl_delete:
            conn_tpl_delete.execute("PRAGMA foreign_keys = ON;") # Ensure cascade delete of template_defined_indicators
            cursor_del_tpl = conn_tpl_delete.cursor()
            cursor_del_tpl.execute(
                "DELETE FROM kpi_indicator_templates WHERE id = ?", (template_id,)
            )
            conn_tpl_delete.commit()
            if cursor_del_tpl.rowcount == 0:
                print(f"WARNING: Template ID {template_id} not found for deletion in DB_KPI_TEMPLATES (final step).")
            else:
                print(f"INFO: KPI Indicator Template ID {template_id} and its definitions deleted successfully.")
    except sqlite3.Error as e_del_final:
        print(f"ERROR: Failed to delete template ID {template_id} from DB_KPI_TEMPLATES. Details: {e_del_final}")
        raise


# --- Template Indicator Definition CRUD ---

def add_indicator_definition_to_template(
    template_id: int, indicator_name: str, calc_type: str, unit: str,
    visible: bool = True, description: str = ""
):
    """Adds an indicator definition to an existing template and propagates the change."""
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    if not isinstance(db_kpi_templates_path, Path) or not db_kpi_templates_path.parent.exists():
        raise ConnectionError(f"DB_KPI_TEMPLATES is not properly configured ({db_kpi_templates_path}). Cannot add definition.")
    if not _data_retriever_available:
        print("WARNING (add_def): data_retriever not available. Cannot check for existing definition properly.")


    definition_details = {
        "template_id": template_id, # Added for _propagate consistency
        "indicator_name_in_template": indicator_name,
        "default_description": description,
        "default_calculation_type": calc_type,
        "default_unit_of_measure": unit,
        "default_visible": 1 if visible else 0, # Ensure it's 0 or 1 for DB
    }
    definition_id = None

    with sqlite3.connect(db_kpi_templates_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO template_defined_indicators
                   (template_id, indicator_name_in_template, default_description,
                    default_calculation_type, default_unit_of_measure, default_visible)
                   VALUES (?,?,?,?,?,?)""",
                (template_id, indicator_name, description, calc_type, unit, 1 if visible else 0),
            )
            conn.commit()
            definition_id = cursor.lastrowid
            definition_details["id"] = definition_id # Add ID for propagation
            print(f"INFO: Added definition '{indicator_name}' to template {template_id}. Definition ID: {definition_id}")
        except sqlite3.IntegrityError:
            print(f"INFO: Definition '{indicator_name}' already exists in template {template_id}. Attempting to update it.")
            existing_def_row = None
            if _data_retriever_available:
                existing_def_row = get_template_indicator_definition_by_name(template_id, indicator_name)

            if existing_def_row:
                existing_def = dict(existing_def_row)
                definition_id = existing_def["id"]
                definition_details["id"] = definition_id
                # Check if an actual update is needed
                if (existing_def["default_calculation_type"] != calc_type or
                    existing_def["default_unit_of_measure"] != unit or
                    bool(existing_def["default_visible"]) != visible or
                    existing_def["default_description"] != description):
                    print(f"  Details differ. Updating definition ID {definition_id}...")
                    try:
                        update_indicator_definition_in_template(
                            definition_id=definition_id, # Pass the definition ID
                            template_id=template_id, # Pass template_id for context
                            indicator_name=indicator_name,
                            calc_type=calc_type,
                            unit=unit,
                            visible=visible,
                            description=description
                        ) # This will in turn call _propagate
                        return # Propagation is handled by update function
                    except Exception as e_update_def:
                        print(f"ERROR: Failed to update existing definition '{indicator_name}' in template {template_id}. Details: {e_update_def}")
                        raise
                else:
                    print(f"  Existing definition ID {definition_id} matches. No update needed, but will ensure propagation.")
                    # Fall through to propagate to ensure consistency if subgroups were linked later.
            else:
                print(f"ERROR: IntegrityError for definition '{indicator_name}' in template {template_id}, "
                      "but could not find existing entry. This is unexpected.")
                raise # Re-raise the original IntegrityError

    # If new or updated, propagate the change
    if definition_id:
        try:
            _propagate_template_indicator_change(template_id, definition_details, "add_or_update")
        except Exception as e_prop:
            print(f"ERROR: Failed to propagate addition/update of definition '{indicator_name}' for template {template_id}. Details: {e_prop}")
            # Consider implications: definition is in template, but not in linked subgroups.

def update_indicator_definition_in_template(
    definition_id: int, template_id:int, # Added template_id for context
    indicator_name: str, calc_type: str, unit: str,
    visible: bool, description: str
):
    """Updates an indicator definition within a template and propagates the change."""
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    if not isinstance(db_kpi_templates_path, Path) or not db_kpi_templates_path.parent.exists():
        raise ConnectionError(f"DB_KPI_TEMPLATES is not properly configured ({db_kpi_templates_path}). Cannot update definition.")
    if not _data_retriever_available:
        print("WARNING (update_def): data_retriever not available. Cannot fetch current definition for comparison.")


    current_def_dict = None
    if _data_retriever_available:
        current_def_row = get_template_indicator_definition_by_id(definition_id)
        if not current_def_row:
            print(f"ERROR: Indicator definition with ID {definition_id} not found. Cannot update.")
            raise ValueError(f"Indicator definition with ID {definition_id} not found.")
        current_def_dict = dict(current_def_row)
        if current_def_dict["indicator_name_in_template"] != indicator_name:
            print(f"WARN: Modifying name of indicator definition ID {definition_id} "
                  f"(from '{current_def_dict['indicator_name_in_template']}' to '{indicator_name}'). "
                  "This could orphan indicators in subgroups if not handled carefully by propagation "
                  "(propagation will attempt to add new and remove old if name changes significantly).")
    else: # If data_retriever mocked, we can't do the pre-check easily
        print(f"WARNING: Cannot fetch current definition ID {definition_id} for pre-update checks.")


    with sqlite3.connect(db_kpi_templates_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE template_defined_indicators SET
                   indicator_name_in_template = ?, default_description = ?,
                   default_calculation_type = ?, default_unit_of_measure = ?, default_visible = ?
                   WHERE id = ?""",
                (indicator_name, description, calc_type, unit, 1 if visible else 0, definition_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                # Should have been caught by pre-check if data_retriever was available
                print(f"ERROR: Definition ID {definition_id} not found during UPDATE. This is unexpected.")
                raise ValueError(f"Definition ID {definition_id} disappeared during update.")
            print(f"INFO: Updated definition ID {definition_id} in template.")
        except sqlite3.IntegrityError as e: # e.g. UNIQUE constraint if name changed to existing in same template
            print(f"ERROR: Could not update definition ID {definition_id}. New name '{indicator_name}' "
                  f"might already exist in template {template_id}. Details: {e}")
            raise
        except sqlite3.Error as e_general:
            print(f"ERROR: Database error updating definition ID {definition_id}. Details: {e_general}")
            raise

    updated_definition_details = {
        "id": definition_id,
        "template_id": template_id, # Crucial: use the template_id passed to this function
        "indicator_name_in_template": indicator_name,
        "default_description": description,
        "default_calculation_type": calc_type,
        "default_unit_of_measure": unit,
        "default_visible": 1 if visible else 0,
    }
    try:
        _propagate_template_indicator_change(template_id, updated_definition_details, "add_or_update")
    except Exception as e_prop:
        print(f"ERROR: Failed to propagate update of definition ID {definition_id} for template {template_id}. Details: {e_prop}")


def remove_indicator_definition_from_template(definition_id: int):
    """Removes an indicator definition from a template and propagates the removal."""
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    if not isinstance(db_kpi_templates_path, Path) or not db_kpi_templates_path.parent.exists():
        raise ConnectionError(f"DB_KPI_TEMPLATES is not properly configured ({db_kpi_templates_path}). Cannot remove definition.")
    if not _data_retriever_available:
        print("WARNING (remove_def): data_retriever not available. Cannot fetch definition details for propagation.")
        # This is problematic as _propagate needs the definition details.
        # For a robust mock, you'd need a way to provide these.

    definition_to_delete_dict = None
    if _data_retriever_available:
        definition_to_delete_row = get_template_indicator_definition_by_id(definition_id)
        if not definition_to_delete_row:
            print(f"INFO: Indicator definition with ID {definition_id} not found. No removal needed.")
            return
        definition_to_delete_dict = dict(definition_to_delete_row)
    else:
        # Cannot get full definition for _propagate if data_retriever is mocked.
        # _propagate might fail or use incomplete info.
        # A minimal mock might assume structure, but it's risky.
        print(f"WARNING: Proceeding to delete definition ID {definition_id} from template, "
              "but propagation may be incomplete due to missing data_retriever.")
        # Construct a minimal dict for propagation if absolutely necessary for mock to run
        # This is a HACK for testing without full data_retriever
        definition_to_delete_dict = {"id": definition_id, "indicator_name_in_template": f"Unknown_Def_{definition_id}", "template_id": -1}
        # Attempt to get template_id if possible
        with sqlite3.connect(db_kpi_templates_path) as conn_get_tpl_id:
            tpl_id_row = conn_get_tpl_id.execute("SELECT template_id FROM template_defined_indicators WHERE id=?", (definition_id,)).fetchone()
            if tpl_id_row:
                definition_to_delete_dict["template_id"] = tpl_id_row[0]


    template_id_of_definition = definition_to_delete_dict.get("template_id")
    if template_id_of_definition is None or template_id_of_definition == -1 : # Check if we got a valid template_id
        print(f"ERROR: Could not determine template_id for definition ID {definition_id}. Cannot reliably propagate removal.")
        # Proceed to delete from template only if this is acceptable
        # return # Or raise error

    with sqlite3.connect(db_kpi_templates_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM template_defined_indicators WHERE id = ?", (definition_id,))
            conn.commit()
            if cursor.rowcount == 0:
                print(f"INFO: Definition ID {definition_id} not found during DELETE (already removed or never existed).")
                return # No propagation needed if it wasn't there
            print(f"INFO: Removed definition ID {definition_id} from template table.")
        except sqlite3.Error as e:
            print(f"ERROR: Database error removing definition ID {definition_id}: {e}")
            raise

    # If successfully removed from template table, and we have the definition details & template_id:
    if definition_to_delete_dict and template_id_of_definition is not None and template_id_of_definition != -1:
        try:
            _propagate_template_indicator_change(template_id_of_definition, definition_to_delete_dict, "remove")
        except Exception as e_prop:
            print(f"ERROR: Failed to propagate removal of definition ID {definition_id} (was for template {template_id_of_definition}). Details: {e_prop}")
    else:
        print(f"INFO: Skipped propagation for definition ID {definition_id} due to missing details or template ID.")


if __name__ == "__main__":
    print("--- Running kpi_management/templates.py for testing ---")
    # This requires kpi_indicator_templates, template_defined_indicators,
    # kpi_subgroups, kpi_indicators, kpis tables to exist for full propagation tests.

    template_id_created = None
    definition_id_created = None

    def setup_minimal_tables_for_templates_module(db_templates_path, db_kpis_path):
        # Setup in DB_KPI_TEMPLATES
        with sqlite3.connect(db_templates_path) as conn_tpl:
            cur_tpl = conn_tpl.cursor()
            cur_tpl.execute("CREATE TABLE IF NOT EXISTS kpi_indicator_templates (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT);")
            cur_tpl.execute(f"""CREATE TABLE IF NOT EXISTS template_defined_indicators (id INTEGER PRIMARY KEY AUTOINCREMENT, template_id INTEGER NOT NULL,
                               indicator_name_in_template TEXT NOT NULL, default_description TEXT,
                               default_calculation_type TEXT NOT NULL CHECK(default_calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}')),
                               default_unit_of_measure TEXT, default_visible BOOLEAN DEFAULT 1,
                               FOREIGN KEY (template_id) REFERENCES kpi_indicator_templates(id) ON DELETE CASCADE,
                               UNIQUE (template_id, indicator_name_in_template));""")
            conn_tpl.commit()

        # Setup in DB_KPIS (for propagation)
        with sqlite3.connect(db_kpis_path) as conn_kpis:
            cur_kpis = conn_kpis.cursor()
            cur_kpis.execute("CREATE TABLE IF NOT EXISTS kpi_groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);")
            cur_kpis.execute("INSERT OR IGNORE INTO kpi_groups (id, name) VALUES (1, 'Test Group for Template Propagation')")
            cur_kpis.execute("""CREATE TABLE IF NOT EXISTS kpi_subgroups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, group_id INTEGER NOT NULL,
                               indicator_template_id INTEGER,
                               FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE,
                               FOREIGN KEY (indicator_template_id) REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL, -- Assuming kpi_indicator_templates is in another DB, this FK might not be enforceable by SQLite directly across DBs.
                               UNIQUE (name, group_id));""")
            # Create a test subgroup that might be linked
            cur_kpis.execute("INSERT OR IGNORE INTO kpi_subgroups (id, name, group_id) VALUES (10, 'Subgroup For Template Test', 1)")

            cur_kpis.execute("""CREATE TABLE IF NOT EXISTS kpi_indicators (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subgroup_id INTEGER NOT NULL,
                               FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE, UNIQUE (name, subgroup_id));""")
            cur_kpis.execute(f"""CREATE TABLE IF NOT EXISTS kpis (id INTEGER PRIMARY KEY AUTOINCREMENT, indicator_id INTEGER NOT NULL UNIQUE, description TEXT,
                               calculation_type TEXT NOT NULL CHECK(calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}')),
                               unit_of_measure TEXT, visible BOOLEAN DEFAULT 1,
                               FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE);""")
            conn_kpis.commit()
        print(f"INFO: Minimal tables for templates module testing ensured/created in {db_templates_path} and {db_kpis_path}")

    test_db_file_tpl = "test_module_templates_db.sqlite"
    test_db_file_kpis = "test_module_templates_kpis_db.sqlite"
    # Save original app_config settings for database paths
    original_db_base_dir = app_config.SETTINGS["database_base_dir"]

    # Create dummy DB files for testing if they don't exist
    if not Path(test_db_file_tpl).exists():
        Path(test_db_file_tpl).touch()
    if not Path(test_db_file_kpis).exists():
        Path(test_db_file_kpis).touch()

    # Temporarily set app_config to use the test files' directory
    app_config.SETTINGS["database_base_dir"] = str(Path(test_db_file_tpl).parent)

    # Setup minimal tables for templates module
    setup_minimal_tables_for_templates_module(app_config.get_database_path("db_kpi_templates.db"), app_config.get_database_path("db_kpis.db"))

    TEST_SUBGROUP_ID_FOR_PROPAGATION = 10

    try:
        print("\nTest 1: Add new KPI Indicator Template 'Customer Service KPIs'")
        template_id_created = add_kpi_indicator_template("Customer Service KPIs", "Standard metrics for customer service.")
        assert isinstance(template_id_created, int)
        print(f"  SUCCESS: Added template with ID {template_id_created}")

        print(f"\nTest 2: Add indicator definition 'Response Time' to template {template_id_created}")
        # Link subgroup to template for propagation test
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_link_sg:
            conn_link_sg.execute("UPDATE kpi_subgroups SET indicator_template_id = ? WHERE id = ?", (template_id_created, TEST_SUBGROUP_ID_FOR_PROPAGATION))
            conn_link_sg.commit()
            print(f"  Linked subgroup {TEST_SUBGROUP_ID_FOR_PROPAGATION} to template {template_id_created} for propagation test.")

        if not _data_retriever_available or not _indicators_module_available or not _specs_module_available:
            print("  SKIPPING propagation part of Test 2 due to missing dependencies.")
            # Add definition without full propagation test
            with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
                cursor = conn.cursor()
                cursor.execute("""INSERT INTO template_defined_indicators (template_id, indicator_name_in_template, default_calculation_type, default_unit_of_measure)
                                VALUES (?, 'Response Time', ?, 'Hours')""", (template_id_created, CALC_TYPE_MEDIA))
                conn.commit()
                definition_id_created = cursor.lastrowid
            print(f"  Definition 'Response Time' added to template (propagation skipped). Def ID: {definition_id_created}")

        else:
            add_indicator_definition_to_template(
                template_id_created, "Response Time", CALC_TYPE_MEDIA, "Hours", True, "Avg time to respond."
            )
            # Verification:
            with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn: # Check in template DB
                def_row = conn.execute("SELECT id FROM template_defined_indicators WHERE template_id=? AND indicator_name_in_template=?",
                                       (template_id_created, "Response Time")).fetchone()
                assert def_row is not None, "Definition not added to template."
                definition_id_created = def_row[0]
            with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn: # Check propagation to subgroup
                ind_row = conn.execute("SELECT id FROM kpi_indicators WHERE subgroup_id=? AND name=?",
                                       (TEST_SUBGROUP_ID_FOR_PROPAGATION, "Response Time")).fetchone()
                assert ind_row is not None, "Indicator 'Response Time' not propagated to subgroup."
            print(f"  SUCCESS: Added definition 'Response Time' (ID {definition_id_created}) and propagated.")


        print(f"\nTest 3: Update definition '{definition_id_created}' (Response Time)")
        if not definition_id_created or not _data_retriever_available or not _indicators_module_available or not _specs_module_available:
            print("  SKIPPING Test 3 due to missing definition_id_created or dependencies.")
        else:
            update_indicator_definition_in_template(
                definition_id_created, template_id_created, "Avg Response Time", CALC_TYPE_MEDIA, "Minutes", False, "Average response time in minutes."
            )
            # Verification
            with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
                def_row = conn.execute("SELECT indicator_name_in_template, default_unit_of_measure, default_visible FROM template_defined_indicators WHERE id=?",
                                       (definition_id_created,)).fetchone()
                assert def_row and def_row[0] == "Avg Response Time" and def_row[1] == "Minutes" and def_row[2] == 0
            with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn: # Check propagation of name change
                ind_row = conn.execute("SELECT id FROM kpi_indicators WHERE subgroup_id=? AND name=?",
                                       (TEST_SUBGROUP_ID_FOR_PROPAGATION, "Avg Response Time")).fetchone()
                assert ind_row is not None, "Indicator name change not propagated."
                # Old named indicator should be gone if propagation worked correctly (removed old, added new)
                old_ind_row = conn.execute("SELECT id FROM kpi_indicators WHERE subgroup_id=? AND name=?",
                                       (TEST_SUBGROUP_ID_FOR_PROPAGATION, "Response Time")).fetchone()
                assert old_ind_row is None, "Old named indicator 'Response Time' not removed after name change propagation."

            print(f"  SUCCESS: Updated definition {definition_id_created} and propagated changes.")


        print(f"\nTest 4: Remove definition '{definition_id_created}' (Avg Response Time)")
        if not definition_id_created or not _data_retriever_available or not _indicators_module_available: # Specs not needed for remove
            print("  SKIPPING Test 4 due to missing definition_id_created or dependencies for propagation.")
        else:
            remove_indicator_definition_from_template(definition_id_created)
            # Verification
            with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
                def_row = conn.execute("SELECT id FROM template_defined_indicators WHERE id=?", (definition_id_created,)).fetchone()
                assert def_row is None, "Definition not removed from template."
            with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
                ind_row = conn.execute("SELECT id FROM kpi_indicators WHERE subgroup_id=? AND name=?",
                                       (TEST_SUBGROUP_ID_FOR_PROPAGATION, "Avg Response Time")).fetchone()
                assert ind_row is None, "Indicator 'Avg Response Time' not removed from subgroup upon template definition removal."
            print(f"  SUCCESS: Removed definition {definition_id_created} and propagated removal.")
            definition_id_created = None # Mark as deleted


        print(f"\nTest 5: Delete template {template_id_created}")
        # Re-add a definition to test its removal during template deletion
        if _data_retriever_available and template_id_created: # Only if template still exists
            add_indicator_definition_to_template(template_id_created, "Resolution Rate", CALC_TYPE_MEDIA, "%", True)
            # Ensure it's propagated to check if delete_kpi_indicator_template cleans it up
            if _indicators_module_available and _specs_module_available:
                 with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn: # Check propagation to subgroup
                    ind_row_res = conn.execute("SELECT id FROM kpi_indicators WHERE subgroup_id=? AND name=?",
                                        (TEST_SUBGROUP_ID_FOR_PROPAGATION, "Resolution Rate")).fetchone()
                    assert ind_row_res is not None, "Indicator 'Resolution Rate' not propagated before template delete test."
                    print("  'Resolution Rate' propagated for delete template test.")


        if not template_id_created or not _data_retriever_available or not _indicators_module_available: # Specs not needed for remove
             print("  SKIPPING Test 5 due to missing template_id_created or dependencies for full delete cascade.")
        else:
            delete_kpi_indicator_template(template_id_created)
            # Verification
            with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
                tpl_row = conn.execute("SELECT id FROM kpi_indicator_templates WHERE id=?", (template_id_created,)).fetchone()
                assert tpl_row is None, "Template not deleted."
                defs_left = conn.execute("SELECT id FROM template_defined_indicators WHERE template_id=?", (template_id_created,)).fetchall()
                assert not defs_left, "Definitions not deleted with template (cascade failed or direct delete failed)."
            with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn: # Check if subgroup was unlinked and indicators removed
                sg_row = conn.execute("SELECT indicator_template_id FROM kpi_subgroups WHERE id = ?", (TEST_SUBGROUP_ID_FOR_PROPAGATION,)).fetchone()
                assert sg_row and sg_row[0] is None, "Subgroup not unlinked from deleted template."
                ind_row_res_after_del = conn.execute("SELECT id FROM kpi_indicators WHERE subgroup_id=? AND name=?",
                                       (TEST_SUBGROUP_ID_FOR_PROPAGATION, "Resolution Rate")).fetchone()
                assert ind_row_res_after_del is None, "Indicator 'Resolution Rate' from deleted template not removed from subgroup."

            print(f"  SUCCESS: Deleted template {template_id_created} and propagated changes (unlink, indicator removal).")
            template_id_created = None # Mark as deleted

        print("\n--- All kpi_management.templates tests passed (basic execution) ---")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED DURING TESTING (kpi_management.templates) ---")
        print(str(e))
        print(traceback.format_exc())
    finally:
        # Restore original app_config setting
        app_config.SETTINGS["database_base_dir"] = original_db_base_dir
        if Path(test_db_file_tpl).exists():
            import os
            try:
                os.remove(test_db_file_tpl)
                print(f"INFO: Cleaned up test file: {test_db_file_tpl}")
            except OSError as e_clean:
                print(f"ERROR: Could not clean up test file {test_db_file_tpl}: {e_clean}")
        if Path(test_db_file_kpis).exists():
            import os
            try:
                os.remove(test_db_file_kpis)
                print(f"INFO: Cleaned up test file: {test_db_file_kpis}")
            except OSError as e_clean:
                print(f"ERROR: Could not clean up test file {test_db_file_kpis}: {e_clean}")