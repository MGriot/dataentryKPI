# database_manager.py
import sqlite3
import json

# from pathlib import Path # No longer needed directly for DB paths
import datetime
import calendar
import numpy as np
import export_manager
import data_retriever

# Import configurations from app_config.py
from app_config import (
    DB_KPIS,
    DB_STABILIMENTI,
    DB_TARGETS,
    DB_KPI_DAYS,
    DB_KPI_WEEKS,
    DB_KPI_MONTHS,
    DB_KPI_QUARTERS,
    DB_KPI_TEMPLATES,
    CSV_EXPORT_BASE_PATH,
)

from app_config import *
# --- Funzioni Helper Generiche (remain the same) ---
def get_weighted_proportions(
    num_periods, initial_factor=1.5, final_factor=0.5, decreasing=True
):
    if num_periods <= 0:
        return []
    if num_periods == 1:
        return [1.0]
    if not decreasing:
        initial_factor, final_factor = final_factor, initial_factor
    raw_weights = (
        np.linspace(initial_factor, final_factor, num_periods).tolist()
        if initial_factor != final_factor
        else [1.0] * num_periods
    )
    min_raw_weight = min(raw_weights)
    if min_raw_weight <= 0:
        shift = abs(min_raw_weight) + 1e-9 # Ensure positive shift
        raw_weights = [w + shift for w in raw_weights]
    total_weight = sum(raw_weights)
    return (
        [w / total_weight for w in raw_weights]
        if total_weight != 0
        else [1.0 / num_periods] * num_periods # Fallback for zero total_weight
    )


def get_parabolic_proportions(num_periods, peak_at_center=True, min_value_epsilon=1e-9):
    if num_periods <= 0:
        return []
    if num_periods == 1:
        return [1.0]
    raw_weights = np.zeros(num_periods)
    mid_point_idx = (num_periods - 1) / 2.0
    for i in range(num_periods):
        raw_weights[i] = (i - mid_point_idx) ** 2
    if peak_at_center:
        raw_weights = np.max(raw_weights) - raw_weights # Invert to make center the peak
    raw_weights += min_value_epsilon # Ensure all weights are positive
    total_weight = np.sum(raw_weights)
    return (
        (raw_weights / total_weight).tolist()
        if total_weight != 0
        else [1.0 / num_periods] * num_periods # Fallback
    )

def get_sinusoidal_proportions(num_periods, amplitude=0.5, phase_offset=0, min_value_epsilon=1e-9):
    if num_periods <= 0: return []
    if num_periods == 1: return [1.0]
    x = np.linspace(0, 2 * np.pi, num_periods, endpoint=False)
    raw_weights = 1 + amplitude * np.sin(x + phase_offset)
    raw_weights = np.maximum(raw_weights, min_value_epsilon) # Ensure positive
    total_weight = np.sum(raw_weights)
    return (raw_weights / total_weight).tolist() if total_weight > 0 else [1.0 / num_periods] * num_periods

def get_date_ranges_for_quarters(year):
    q_ranges = {}
    q_ranges[1] = (datetime.date(year, 1, 1), datetime.date(year, 3, 31))
    q_ranges[2] = (datetime.date(year, 4, 1), datetime.date(year, 6, 30))
    q_ranges[3] = (datetime.date(year, 7, 1), datetime.date(year, 9, 30))
    q_end_month = 12
    q_end_day = calendar.monthrange(year, q_end_month)[1]
    q_ranges[4] = (datetime.date(year, 10, 1), datetime.date(year, q_end_month, q_end_day))
    return q_ranges

# --- Setup Database ---
def setup_databases():
    print("Inizio setup_databases...")
    CSV_EXPORT_BASE_PATH.mkdir(parents=True, exist_ok=True)

    # --- DB_KPIS Setup ---
    with sqlite3.connect(DB_KPIS) as conn:
        cursor = conn.cursor()
        print(f"Setup tabelle in {DB_KPIS}...")
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS kpi_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS kpi_subgroups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                group_id INTEGER NOT NULL,
                indicator_template_id INTEGER,
                FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE,
                FOREIGN KEY (indicator_template_id) REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL,
                UNIQUE (name, group_id) )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS kpi_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subgroup_id INTEGER NOT NULL,
                FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE, UNIQUE (name, subgroup_id) )"""
        )
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS kpis (
                id INTEGER PRIMARY KEY AUTOINCREMENT, indicator_id INTEGER NOT NULL, description TEXT,
                calculation_type TEXT NOT NULL CHECK(calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}')),
                unit_of_measure TEXT, visible BOOLEAN NOT NULL DEFAULT 1,
                FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE,
                UNIQUE (indicator_id) )"""
        )
        
        # Add 'indicator_template_id' to 'kpi_subgroups' if not exists
        cursor.execute("PRAGMA table_info(kpi_subgroups)")
        subgroup_columns = {col[1] for col in cursor.fetchall()}
        if "indicator_template_id" not in subgroup_columns:
            try:
                cursor.execute("ALTER TABLE kpi_subgroups ADD COLUMN indicator_template_id INTEGER REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL")
                print("Aggiunta colonna 'indicator_template_id' a 'kpi_subgroups'.")
            except sqlite3.OperationalError as e:
                print(f"WARN: Could not add 'indicator_template_id' to 'kpi_subgroups', might exist or other issue: {e}")

        # Add 'unit_of_measure' to 'kpis' if not exists
        cursor.execute("PRAGMA table_info(kpis)")
        kpi_columns_set = {col[1] for col in cursor.fetchall()}
        if "unit_of_measure" not in kpi_columns_set:
            try:
                cursor.execute("ALTER TABLE kpis ADD COLUMN unit_of_measure TEXT")
                print("Aggiunta colonna 'unit_of_measure' a 'kpis'.")
            except sqlite3.OperationalError:
                pass # Column might already exist

        # NEW: kpi_master_sub_links table
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS kpi_master_sub_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_kpi_spec_id INTEGER NOT NULL, -- Refers to kpis.id
                sub_kpi_spec_id INTEGER NOT NULL,    -- Refers to kpis.id
                FOREIGN KEY (master_kpi_spec_id) REFERENCES kpis(id) ON DELETE CASCADE,
                FOREIGN KEY (sub_kpi_spec_id) REFERENCES kpis(id) ON DELETE CASCADE,
                UNIQUE (master_kpi_spec_id, sub_kpi_spec_id)
            )"""
        )
        conn.commit()
        print(f"Setup tabelle in {DB_KPIS} completato.")

    # --- DB_KPI_TEMPLATES Setup ---
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        cursor = conn.cursor()
        print(f"Setup tabelle in {DB_KPI_TEMPLATES}...")
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS kpi_indicator_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            )"""
        )
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS template_defined_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                indicator_name_in_template TEXT NOT NULL,
                default_description TEXT,
                default_calculation_type TEXT NOT NULL CHECK(default_calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}')),
                default_unit_of_measure TEXT,
                default_visible BOOLEAN NOT NULL DEFAULT 1,
                FOREIGN KEY (template_id) REFERENCES kpi_indicator_templates(id) ON DELETE CASCADE,
                UNIQUE (template_id, indicator_name_in_template)
            )"""
        )
        conn.commit()
        print(f"Setup tabelle in {DB_KPI_TEMPLATES} completato.")

    # --- DB_STABILIMENTI Setup ---
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        print(f"Setup tabelle in {DB_STABILIMENTI}...")
        conn.cursor().execute(
            """CREATE TABLE IF NOT EXISTS stabilimenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                visible BOOLEAN NOT NULL DEFAULT 1 )"""
        )
        conn.commit()
        print(f"Setup tabelle in {DB_STABILIMENTI} completato.")

    # --- DB_TARGETS Setup (Annual Targets) ---
    with sqlite3.connect(DB_TARGETS) as conn:
        cursor = conn.cursor()
        print(f"Setup tabelle in {DB_TARGETS}...")
        # Try to create with new columns first
        try:
            cursor.execute(
                 """ CREATE TABLE annual_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, stabilimento_id INTEGER NOT NULL, kpi_id INTEGER NOT NULL,
                    annual_target1 REAL NOT NULL DEFAULT 0, annual_target2 REAL NOT NULL DEFAULT 0,
                    repartition_logic TEXT NOT NULL,
                    repartition_values TEXT NOT NULL,
                    distribution_profile TEXT NOT NULL DEFAULT 'annual_progressive',
                    profile_params TEXT,
                    is_target1_manual BOOLEAN NOT NULL DEFAULT 0,
                    is_target2_manual BOOLEAN NOT NULL DEFAULT 0,
                    UNIQUE(year, stabilimento_id, kpi_id))"""
            )
        except sqlite3.OperationalError as e:
            if "table annual_targets already exists" not in str(e).lower():
                raise # Reraise if it's not the "already exists" error

        # Check and add new columns if they don't exist (idempotent ALTER TABLE)
        cursor.execute("PRAGMA table_info(annual_targets)")
        target_columns_info = {col[1].lower(): col for col in cursor.fetchall()}

        columns_to_add = {
            "profile_params": "TEXT",
            "is_target1_manual": "BOOLEAN NOT NULL DEFAULT 0",
            "is_target2_manual": "BOOLEAN NOT NULL DEFAULT 0"
        }

        for col_name, col_def in columns_to_add.items():
            if col_name not in target_columns_info:
                try:
                    cursor.execute(f"ALTER TABLE annual_targets ADD COLUMN {col_name} {col_def}")
                    print(f"Aggiunta colonna '{col_name}' a 'annual_targets'.")
                except sqlite3.OperationalError as e_alter:
                    # This might happen if another process added it, or if default value constraint fails on existing NULLs
                    # For BOOLEAN NOT NULL DEFAULT 0, this should be fine for new columns.
                    print(f"WARN: Impossibile aggiungere colonna '{col_name}' a 'annual_targets': {e_alter}")
        
        conn.commit()
        print(f"Setup tabelle in {DB_TARGETS} completato.")

    # --- Setup Tabelle Periodiche ---
    db_configs_periods = [
        (DB_KPI_DAYS, "daily_targets", "date_value TEXT NOT NULL"),
        (DB_KPI_WEEKS, "weekly_targets", "week_value TEXT NOT NULL"),
        (DB_KPI_MONTHS, "monthly_targets", "month_value TEXT NOT NULL"),
        (DB_KPI_QUARTERS, "quarterly_targets", "quarter_value TEXT NOT NULL"),
    ]
    for db_path, table_name, period_col_def in db_configs_periods:
        print(f"Setup tabella '{table_name}' in {db_path}...")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            period_col_name_for_unique = period_col_def.split()[0]
            cursor.execute(
                f""" CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    stabilimento_id INTEGER NOT NULL,
                    kpi_id INTEGER NOT NULL, -- This is kpis.id (kpi_spec_id)
                    target_number INTEGER NOT NULL CHECK(target_number IN (1, 2)),
                    {period_col_def.replace(' UNIQUE', '')}, -- Remove UNIQUE if present to avoid conflict with table constraint
                    target_value REAL NOT NULL,
                    UNIQUE(year, stabilimento_id, kpi_id, target_number, {period_col_name_for_unique})
                )"""
            )
            conn.commit()
        print(f"Setup tabella '{table_name}' in {db_path} completato.")
    print("Controllo e setup database completato.")


# --- Gestione Gruppi KPI (CRUD operations remain in database_manager.py) ---
def add_kpi_group(name):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO kpi_groups (name) VALUES (?)", (name,))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Gruppo '{name}' già esistente.")
            raise

def update_kpi_group(group_id, new_name):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute("UPDATE kpi_groups SET name = ? WHERE id = ?", (new_name, group_id))
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento del gruppo: Nome '{new_name}' potrebbe già esistere.")
            raise e

def delete_kpi_group(group_id):
    indicators_to_delete_ids = []
    # Use data_retriever for reading subgroup details
    subgroups_in_group = data_retriever.get_kpi_subgroups_by_group_revised(group_id)
    
    # Still need a connection to read indicators within those subgroups if not in data_retriever
    with sqlite3.connect(DB_KPIS) as conn_kpis_read:
        conn_kpis_read.row_factory = sqlite3.Row
        for sg_dict in subgroups_in_group: # sg_dict already has 'id'
            indicators = conn_kpis_read.execute("SELECT id FROM kpi_indicators WHERE subgroup_id = ?", (sg_dict["id"],)).fetchall()
            for ind_row in indicators:
                indicators_to_delete_ids.append(ind_row["id"])

    for ind_id in indicators_to_delete_ids:
        delete_kpi_indicator(ind_id) # This handles deleting kpi_spec and all related data

    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("DELETE FROM kpi_groups WHERE id = ?", (group_id,)) # This will cascade to subgroups
        conn.commit()

# --- Gestione Template Indicatori KPI (CRUD) ---
def add_kpi_indicator_template(name, description=""):
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_indicator_templates (name, description) VALUES (?,?)",
                (name, description)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Template '{name}' già esistente.")
            raise

def update_kpi_indicator_template(template_id, name, description):
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        try:
            conn.execute(
                "UPDATE kpi_indicator_templates SET name = ?, description = ? WHERE id = ?",
                (name, description, template_id)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"Errore: Nome template '{name}' potrebbe già esistere.")
            raise

def delete_kpi_indicator_template(template_id):
    linked_subgroup_ids = []
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        rows = conn_kpis.execute("SELECT id FROM kpi_subgroups WHERE indicator_template_id = ?", (template_id,)).fetchall()
        linked_subgroup_ids = [row['id'] for row in rows]

    definitions_in_template = data_retriever.get_template_defined_indicators(template_id)

    with sqlite3.connect(DB_KPI_TEMPLATES) as conn_tpl:
        conn_tpl.execute("DELETE FROM kpi_indicator_templates WHERE id = ?", (template_id,)) # Cascades to template_defined_indicators
        conn_tpl.commit()

    if linked_subgroup_ids and definitions_in_template:
        for def_to_remove in definitions_in_template:
            # Propagate removal to linked subgroups
            _propagate_template_indicator_change(template_id, def_to_remove, "remove", specific_subgroup_ids=linked_subgroup_ids)

    # Finally, unlink subgroups: Set indicator_template_id to NULL
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.execute("UPDATE kpi_subgroups SET indicator_template_id = NULL WHERE indicator_template_id = ?", (template_id,))
        conn_kpis.commit()


def add_indicator_definition_to_template(template_id, indicator_name, calc_type, unit, visible=True, description=""):
    definition_details = {
        "indicator_name_in_template": indicator_name,
        "default_description": description,
        "default_calculation_type": calc_type,
        "default_unit_of_measure": unit,
        "default_visible": visible,
    }
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO template_defined_indicators
                   (template_id, indicator_name_in_template, default_description, default_calculation_type, default_unit_of_measure, default_visible)
                   VALUES (?,?,?,?,?,?)""",
                (template_id, indicator_name, description, calc_type, unit, visible)
            )
            conn.commit()
            definition_details["id"] = cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Definizione indicatore '{indicator_name}' già esistente nel template ID {template_id}.")
            # Try to get existing to update if properties changed
            existing_def = data_retriever.get_template_indicator_definition_by_name(template_id, indicator_name)
            if existing_def:
                definition_details["id"] = existing_def["id"] # Use existing ID for propagation
                # Trigger update if it already exists and parameters are different
                if (existing_def["default_calculation_type"] != calc_type or
                    existing_def["default_unit_of_measure"] != unit or
                    bool(existing_def["default_visible"]) != visible or # Ensure bool comparison
                    existing_def["default_description"] != description):
                    update_indicator_definition_in_template(
                        existing_def["id"], indicator_name, calc_type, unit, visible, description
                    ) # This will trigger its own propagation
            else: # Should not happen if integrity error was for this unique constraint
                raise
            return # Exit after handling existing or re-raising

    _propagate_template_indicator_change(template_id, definition_details, "add_or_update")


def update_indicator_definition_in_template(definition_id, indicator_name, calc_type, unit, visible, description):
    current_def = data_retriever.get_template_indicator_definition_by_id(definition_id)
    if not current_def:
        print(f"Definizione indicatore con ID {definition_id} non trovata.")
        return

    if current_def["indicator_name_in_template"] != indicator_name:
        print(f"WARN: Modifica del nome dell'indicatore nel template (da '{current_def['indicator_name_in_template']}' a '{indicator_name}'). "
              f"Questo potrebbe creare un nuovo indicatore nei sottogruppi collegati e lasciare orfano il vecchio.")

    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.execute(
            """UPDATE template_defined_indicators SET
               indicator_name_in_template = ?, default_description = ?, default_calculation_type = ?,
               default_unit_of_measure = ?, default_visible = ?
               WHERE id = ?""",
            (indicator_name, description, calc_type, unit, visible, definition_id)
        )
        conn.commit()

    # Prepare details for propagation using the potentially new name
    updated_definition_details = {
        "id": definition_id,
        "template_id": current_def["template_id"],
        "indicator_name_in_template": indicator_name, # Use the new name for propagation
        "default_description": description,
        "default_calculation_type": calc_type,
        "default_unit_of_measure": unit,
        "default_visible": visible,
    }
    _propagate_template_indicator_change(current_def["template_id"], updated_definition_details, "add_or_update")

def remove_indicator_definition_from_template(definition_id):
    definition_to_delete = data_retriever.get_template_indicator_definition_by_id(definition_id)
    if not definition_to_delete:
        print(f"Definizione indicatore con ID {definition_id} non trovata per la rimozione.")
        return

    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.execute("DELETE FROM template_defined_indicators WHERE id = ?", (definition_id,))
        conn.commit()

    _propagate_template_indicator_change(definition_to_delete["template_id"], definition_to_delete, "remove")


def _propagate_template_indicator_change(template_id, indicator_definition, action, specific_subgroup_ids=None):
    subgroups_to_update = []
    # This read can stay direct as it's internal to this module's logic flow
    with sqlite3.connect(DB_KPIS) as conn_kpis_read:
        conn_kpis_read.row_factory = sqlite3.Row
        if specific_subgroup_ids:
            placeholders = ','.join('?' for _ in specific_subgroup_ids)
            query_sg = f"SELECT id FROM kpi_subgroups WHERE indicator_template_id = ? AND id IN ({placeholders})"
            params_sg = [template_id] + specific_subgroup_ids
            subgroups_to_update = conn_kpis_read.execute(query_sg, params_sg).fetchall()
        else:
            subgroups_to_update = conn_kpis_read.execute(
                "SELECT id FROM kpi_subgroups WHERE indicator_template_id = ?", (template_id,)
            ).fetchall()

    if not subgroups_to_update: return

    with sqlite3.connect(DB_KPIS) as conn_kpis_action:
        conn_kpis_action.row_factory = sqlite3.Row
        conn_kpis_action.execute("PRAGMA foreign_keys = ON;")

        for sg_row in subgroups_to_update:
            subgroup_id = sg_row["id"]
            indicator_name_in_subgroup = indicator_definition["indicator_name_in_template"]

            # Check for existing indicator in this subgroup
            existing_indicator = conn_kpis_action.execute(
                "SELECT id FROM kpi_indicators WHERE name = ? AND subgroup_id = ?",
                (indicator_name_in_subgroup, subgroup_id)
            ).fetchone()

            if action == "add_or_update":
                actual_indicator_id = None
                if not existing_indicator:
                    try:
                        cursor_add_ind = conn_kpis_action.cursor()
                        cursor_add_ind.execute(
                            "INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)",
                            (indicator_name_in_subgroup, subgroup_id)
                        )
                        actual_indicator_id = cursor_add_ind.lastrowid
                    except sqlite3.IntegrityError: # Should be caught by 'if not existing_indicator'
                        existing_indicator = conn_kpis_action.execute( # Re-fetch
                            "SELECT id FROM kpi_indicators WHERE name = ? AND subgroup_id = ?",
                            (indicator_name_in_subgroup, subgroup_id)
                        ).fetchone()
                        if existing_indicator: actual_indicator_id = existing_indicator["id"]
                        else: continue # Error
                else:
                    actual_indicator_id = existing_indicator["id"]
                
                if actual_indicator_id:
                    # Check for existing kpi_spec for this indicator_id
                    kpi_spec = conn_kpis_action.execute("SELECT id FROM kpis WHERE indicator_id = ?", (actual_indicator_id,)).fetchone()
                    desc = indicator_definition["default_description"]
                    calc = indicator_definition["default_calculation_type"]
                    unit = indicator_definition["default_unit_of_measure"]
                    vis = bool(indicator_definition["default_visible"])

                    if not kpi_spec:
                        conn_kpis_action.execute(
                                """INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible)
                                   VALUES (?,?,?,?,?)""", (actual_indicator_id, desc, calc, unit, vis) )
                    else: # Update existing kpi_spec
                        conn_kpis_action.execute(
                            """UPDATE kpis SET description=?, calculation_type=?, unit_of_measure=?, visible=?
                               WHERE id=?""", (desc, calc, unit, vis, kpi_spec["id"]) ) # Use kpi_spec["id"] which is kpis.id

            elif action == "remove":
                if existing_indicator:
                    indicator_id_to_delete = existing_indicator["id"] # This is kpi_indicators.id
                    # delete_kpi_indicator handles deleting the kpi spec (kpis table entry)
                    # and all associated targets and master/sub links.
                    delete_kpi_indicator(indicator_id_to_delete)
        conn_kpis_action.commit()


# --- Gestione Sottogruppi KPI (CRUD) ---
def add_kpi_subgroup(name, group_id, indicator_template_id=None):
    subgroup_id = None
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_subgroups (name, group_id, indicator_template_id) VALUES (?,?,?)",
                (name, group_id, indicator_template_id),
            )
            subgroup_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"Sottogruppo '{name}' già esistente in questo gruppo.")
            raise

    if subgroup_id and indicator_template_id:
        template_indicators = data_retriever.get_template_defined_indicators(indicator_template_id)
        for ind_def in template_indicators:
            _apply_template_indicator_to_new_subgroup(subgroup_id, ind_def)
    return subgroup_id

def _apply_template_indicator_to_new_subgroup(subgroup_id, indicator_definition):
    indicator_name = indicator_definition["indicator_name_in_template"]
    desc = indicator_definition["default_description"]
    calc = indicator_definition["default_calculation_type"]
    unit = indicator_definition["default_unit_of_measure"]
    vis = bool(indicator_definition["default_visible"])

    with sqlite3.connect(DB_KPIS) as conn_apply:
        conn_apply.execute("PRAGMA foreign_keys = ON;")
        actual_indicator_id = None
        try:
            cursor_ind = conn_apply.cursor()
            cursor_ind.execute(
                "INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)",
                (indicator_name, subgroup_id)
            )
            actual_indicator_id = cursor_ind.lastrowid
        except sqlite3.IntegrityError: # Indicator might already exist if manually added before template link
            existing_ind_row = conn_apply.execute("SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?", (indicator_name, subgroup_id)).fetchone()
            if existing_ind_row: actual_indicator_id = existing_ind_row[0]
            else: print(f"Errore Critico ApplyTpl: Impossibile creare o trovare Indicatore '{indicator_name}' per SG {subgroup_id}."); return

        if actual_indicator_id:
            try: # Add kpi spec
                conn_apply.execute(
                    "INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible) VALUES (?,?,?,?,?)",
                    (actual_indicator_id, desc, calc, unit, vis)
                )
            except sqlite3.IntegrityError: # KPI spec for this indicator_id already exists (UNIQUE constraint on kpis.indicator_id)
                 conn_apply.execute( # Update existing kpi spec
                     "UPDATE kpis SET description=?, calculation_type=?, unit_of_measure=?, visible=? WHERE indicator_id=?",
                     (desc, calc, unit, vis, actual_indicator_id)
                )
        conn_apply.commit()

def update_kpi_subgroup(subgroup_id, new_name, group_id, new_template_id=None):
    current_subgroup_info = None
    with sqlite3.connect(DB_KPIS) as conn_read:
        conn_read.row_factory = sqlite3.Row
        current_subgroup_info = conn_read.execute("SELECT indicator_template_id, name FROM kpi_subgroups WHERE id = ?", (subgroup_id,)).fetchone()

    if not current_subgroup_info:
        print(f"Errore: Sottogruppo con ID {subgroup_id} non trovato.")
        return

    old_template_id = current_subgroup_info["indicator_template_id"]

    with sqlite3.connect(DB_KPIS) as conn_update:
        try:
            conn_update.execute("UPDATE kpi_subgroups SET name = ?, group_id = ?, indicator_template_id = ? WHERE id = ?",
                               (new_name, group_id, new_template_id, subgroup_id))
            conn_update.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento del sottogruppo: Nome '{new_name}' potrebbe già esistere in questo gruppo.")
            raise e

    if old_template_id != new_template_id:
        print(f"Template per sottogruppo {subgroup_id} ('{new_name}') cambiato da {old_template_id} a {new_template_id}.")
        if old_template_id is not None:
            old_template_definitions = data_retriever.get_template_defined_indicators(old_template_id)
            for old_def in old_template_definitions:
                _propagate_template_indicator_change(old_template_id, old_def, "remove", specific_subgroup_ids=[subgroup_id])
        if new_template_id is not None:
            new_template_definitions = data_retriever.get_template_defined_indicators(new_template_id)
            for new_def in new_template_definitions:
                 _apply_template_indicator_to_new_subgroup(subgroup_id, new_def)
            print(f"Indicatori del nuovo template {new_template_id} applicati/aggiornati per il sottogruppo {subgroup_id}.")


def delete_kpi_subgroup(subgroup_id):
    indicators_in_subgroup_ids = []
    # Direct read for efficiency as it's part of a delete operation.
    with sqlite3.connect(DB_KPIS) as conn_kpis_read:
        conn_kpis_read.row_factory = sqlite3.Row
        indicators = conn_kpis_read.execute("SELECT id FROM kpi_indicators WHERE subgroup_id = ?", (subgroup_id,)).fetchall()
        indicators_in_subgroup_ids = [ind_row["id"] for ind_row in indicators]

    for ind_id in indicators_in_subgroup_ids:
        delete_kpi_indicator(ind_id)

    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("DELETE FROM kpi_subgroups WHERE id = ?", (subgroup_id,))
        conn.commit()


# --- Gestione Indicatori KPI (CRUD) ---
def add_kpi_indicator(name, subgroup_id):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)",
                (name, subgroup_id),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # If it already exists, fetch and return its ID
            existing_id_row = conn.execute("SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?", (name, subgroup_id)).fetchone()
            if existing_id_row: return existing_id_row[0]
            raise # Reraise if not found after integrity error (should not happen for UNIQUE)

def update_kpi_indicator(indicator_id, new_name, subgroup_id):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute("UPDATE kpi_indicators SET name = ?, subgroup_id = ? WHERE id = ?", (new_name, subgroup_id, indicator_id))
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento dell'indicatore: Nome '{new_name}' potrebbe già esistere in questo sottogruppo.")
            raise e

def delete_kpi_indicator(indicator_id): # indicator_id is kpi_indicators.id
    kpi_spec_id_to_delete = None
    # Get the kpi_spec_id (kpis.id) associated with this kpi_indicator.id
    with sqlite3.connect(DB_KPIS) as conn_kpis_read:
        kpi_spec_row = conn_kpis_read.execute("SELECT id FROM kpis WHERE indicator_id = ?", (indicator_id,)).fetchone()
        if kpi_spec_row:
            kpi_spec_id_to_delete = kpi_spec_row[0]

    if kpi_spec_id_to_delete:
        print(f"Eliminazione dati associati a kpi_spec_id: {kpi_spec_id_to_delete} (da indicatore {indicator_id})")
        # Delete from kpi_master_sub_links where this kpi_spec_id is master or sub
        with sqlite3.connect(DB_KPIS) as conn_links:
            conn_links.execute("DELETE FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? OR sub_kpi_spec_id = ?",
                               (kpi_spec_id_to_delete, kpi_spec_id_to_delete))
            conn_links.commit()

        # Delete associated annual targets
        with sqlite3.connect(DB_TARGETS) as conn_targets:
            conn_targets.execute("DELETE FROM annual_targets WHERE kpi_id = ?", (kpi_spec_id_to_delete,))
            conn_targets.commit()

        # Delete associated periodic targets
        periodic_dbs_info = [
            (DB_KPI_DAYS, "daily_targets"), (DB_KPI_WEEKS, "weekly_targets"),
            (DB_KPI_MONTHS, "monthly_targets"), (DB_KPI_QUARTERS, "quarterly_targets"),
        ]
        for db_path_del, table_name_del in periodic_dbs_info:
            with sqlite3.connect(db_path_del) as conn_periodic:
                conn_periodic.execute(f"DELETE FROM {table_name_del} WHERE kpi_id = ?", (kpi_spec_id_to_delete,))
                conn_periodic.commit()
    
    # Deleting the kpi_indicator will cascade to delete the kpis spec entry in DB_KPIS
    with sqlite3.connect(DB_KPIS) as conn_kpis_delete:
        conn_kpis_delete.execute("PRAGMA foreign_keys = ON;") # Ensure cascade delete is active
        conn_kpis_delete.execute("DELETE FROM kpi_indicators WHERE id = ?", (indicator_id,))
        conn_kpis_delete.commit()


# --- Gestione Specifiche KPI (tabella `kpis`) (CRUD) ---
def add_kpi_spec(indicator_id, description, calculation_type, unit_of_measure, visible):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpis (indicator_id,description,calculation_type,unit_of_measure,visible) VALUES (?,?,?,?,?)",
                (indicator_id, description, calculation_type, unit_of_measure, visible),
            )
            conn.commit()
            return cursor.lastrowid # This is kpis.id (the kpi_spec_id)
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kpis.indicator_id" in str(e):
                # KPI spec for this indicator_id already exists, so update it.
                print(f"KPI Spec for indicator_id {indicator_id} already exists. Attempting to update.")
                existing_kpi_row = conn.execute("SELECT id FROM kpis WHERE indicator_id=?", (indicator_id,)).fetchone()
                if existing_kpi_row:
                    existing_kpi_spec_id = existing_kpi_row[0]
                    update_kpi_spec(existing_kpi_spec_id, indicator_id, description, calculation_type, unit_of_measure, visible)
                    return existing_kpi_spec_id # Return the ID of the updated/existing spec
                else: # Should not happen if IntegrityError was due to kpis.indicator_id
                    print(f"IntegrityError for indicator_id {indicator_id}, but could not find existing kpi_spec to update.")
                    raise e
            else: # Some other integrity error
                raise e

def update_kpi_spec(kpi_spec_id, indicator_id, description, calculation_type, unit_of_measure, visible):
    with sqlite3.connect(DB_KPIS) as conn:
        try: # Ensure indicator_id is not changed to one that already has a spec, unless it's its own.
            conn.execute(
                "UPDATE kpis SET indicator_id=?,description=?,calculation_type=?,unit_of_measure=?,visible=? WHERE id=?",
                (indicator_id, description, calculation_type, unit_of_measure, visible, kpi_spec_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as e: # indicator_id might clash if changed to an existing one
            raise e

# --- Gestione Stabilimenti (CRUD) ---
def add_stabilimento(name, visible):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO stabilimenti (name,visible) VALUES (?,?)", (name, visible))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e: raise e

def update_stabilimento(stabilimento_id, name, visible):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        try:
            conn.execute("UPDATE stabilimenti SET name=?,visible=? WHERE id=?", (name, visible, stabilimento_id))
            conn.commit()
        except sqlite3.IntegrityError as e: raise e


# --- Gestione Master/Sub KPI Links (NEW CRUD) ---
def add_master_sub_kpi_link(master_kpi_spec_id, sub_kpi_spec_id):
    """Adds a link between a master KPI and a sub KPI."""
    if master_kpi_spec_id == sub_kpi_spec_id:
        raise ValueError("Un KPI non può essere master e sub di se stesso.")
    # Optional: Check if sub_kpi_spec_id is already a master of other KPIs
    # if data_retriever.get_sub_kpis_for_master(sub_kpi_spec_id):
    #     raise ValueError(f"KPI {sub_kpi_spec_id} è già master di altri KPIs e non può diventare un sub.")
    # Optional: Check if sub_kpi_spec_id is already a sub of another master
    # existing_master = data_retriever.get_master_kpi_for_sub(sub_kpi_spec_id)
    # if existing_master and existing_master != master_kpi_spec_id:
    #     raise ValueError(f"KPI {sub_kpi_spec_id} è già sub di un altro master (ID: {existing_master}).")

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute(
                "INSERT INTO kpi_master_sub_links (master_kpi_spec_id, sub_kpi_spec_id) VALUES (?, ?)",
                (master_kpi_spec_id, sub_kpi_spec_id)
            )
            conn.commit()
            print(f"Collegato Master KPI {master_kpi_spec_id} a Sub KPI {sub_kpi_spec_id}")
        except sqlite3.IntegrityError:
            print(f"Link tra Master KPI {master_kpi_spec_id} e Sub KPI {sub_kpi_spec_id} già esistente o kpi_spec_id non validi.")
            # Don't raise here, let UI handle if needed, or just log
            # raise

def remove_master_sub_kpi_link(master_kpi_spec_id, sub_kpi_spec_id):
    """Removes a specific link between a master and a sub KPI."""
    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute(
            "DELETE FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?",
            (master_kpi_spec_id, sub_kpi_spec_id)
        )
        conn.commit()
        print(f"Scollegato Sub KPI {sub_kpi_spec_id} da Master KPI {master_kpi_spec_id}")

def remove_all_links_for_kpi(kpi_spec_id):
    """Removes a KPI from all link roles (either as master or sub). Used when deleting a KPI spec."""
    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute("DELETE FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? OR sub_kpi_spec_id = ?", (kpi_spec_id, kpi_spec_id))
        conn.commit()
        print(f"Rimossi tutti i link master/sub per KPI Spec ID {kpi_spec_id}")


# --- Gestione Target Annuali ---
def save_annual_targets(year, stabilimento_id, targets_data_map,
                        initiator_kpi_spec_id=None, # Helps in targeted updates
                        is_recursive_call=False): # Prevents infinite loops

    if not targets_data_map:
        print("Nessun dato target da salvare.")
        return

    print(f"Inizio save_annual_targets per Anno: {year}, Stab: {stabilimento_id}. Initiator: {initiator_kpi_spec_id}, Recursive: {is_recursive_call}")
    print(f"Dati input: {targets_data_map}")

    # Step 1: Save explicitly provided/changed targets and their manual flags first.
    # Collect all KPIs that will need their repartitions recalculated.
    kpis_needing_repartition_update = set()

    with sqlite3.connect(DB_TARGETS) as conn:
        cursor = conn.cursor()
        for kpi_spec_id_str, data_dict in targets_data_map.items():
            try:
                current_kpi_spec_id = int(kpi_spec_id_str)
            except ValueError:
                print(f"Skipping invalid kpi_spec_id: {kpi_spec_id_str}"); continue

            record = data_retriever.get_annual_target_entry(year, stabilimento_id, current_kpi_spec_id)

            # Get values from input data_dict, fall back to record or defaults
            annual_t1 = float(data_dict.get("annual_target1", record["annual_target1"] if record else 0.0) or 0.0)
            annual_t2 = float(data_dict.get("annual_target2", record["annual_target2"] if record else 0.0) or 0.0)
            repart_logic = data_dict.get("repartition_logic", record["repartition_logic"] if record else REPARTITION_LOGIC_ANNO)
            repart_values_json = json.dumps(data_dict.get("repartition_values", json.loads(record["repartition_values"] or "{}") if record else {}))
            dist_profile = data_dict.get("distribution_profile", record["distribution_profile"] if record else PROFILE_ANNUAL_PROGRESSIVE)
            profile_params_json = json.dumps(data_dict.get("profile_params", json.loads(record["profile_params"] or "{}") if record else {}))
            
            # Manual flags are crucial and come from the input if present, otherwise from record.
            # If it's a new record, assume manual unless specified otherwise (or derived later if subKPI).
            is_manual1 = bool(data_dict.get("is_target1_manual", record["is_target1_manual"] if record else True))
            is_manual2 = bool(data_dict.get("is_target2_manual", record["is_target2_manual"] if record else True))

            if record:
                cursor.execute(
                    """UPDATE annual_targets SET annual_target1=?, annual_target2=?, repartition_logic=?,
                       repartition_values=?, distribution_profile=?, profile_params=?,
                       is_target1_manual=?, is_target2_manual=? WHERE id=?""",
                    (annual_t1, annual_t2, repart_logic, repart_values_json, dist_profile, profile_params_json,
                     is_manual1, is_manual2, record["id"]))
            else:
                cursor.execute(
                    """INSERT INTO annual_targets (year,stabilimento_id,kpi_id,annual_target1,annual_target2,
                       repartition_logic,repartition_values,distribution_profile,profile_params,
                       is_target1_manual, is_target2_manual) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (year, stabilimento_id, current_kpi_spec_id, annual_t1, annual_t2, repart_logic,
                     repart_values_json, dist_profile, profile_params_json, is_manual1, is_manual2))
            kpis_needing_repartition_update.add(current_kpi_spec_id)
            print(f"  KPI {current_kpi_spec_id} salvato/aggiornato. T1: {annual_t1} (Man: {is_manual1}), T2: {annual_t2} (Man: {is_manual2})")
        conn.commit()

    # Step 2: Handle Master KPI distribution logic.
    # Identify all unique Master KPIs affected by the current changes.
    # An affected master is either one whose target was directly in targets_data_map,
    # or one whose subKPI was in targets_data_map (and thus might have changed its manual status or value).
    masters_to_re_evaluate = set()
    if initiator_kpi_spec_id:
        role_info = data_retriever.get_kpi_role_details(initiator_kpi_spec_id)
        if role_info['role'] == 'master':
            masters_to_re_evaluate.add(initiator_kpi_spec_id)
        elif role_info['role'] == 'sub' and role_info['master_id']:
            masters_to_re_evaluate.add(role_info['master_id'])
    
    # Also add any masters that were directly in the input data
    for kpi_spec_id_str in targets_data_map.keys():
        kpi_id = int(kpi_spec_id_str)
        role_info = data_retriever.get_kpi_role_details(kpi_id)
        if role_info['role'] == 'master':
            masters_to_re_evaluate.add(kpi_id)


    for master_kpi_id in masters_to_re_evaluate:
        print(f"  Valutazione Master KPI: {master_kpi_id}")
        master_target_entry = data_retriever.get_annual_target_entry(year, stabilimento_id, master_kpi_id)
        if not master_target_entry:
            print(f"    WARN: Nessun target annuale trovato per Master KPI {master_kpi_id}. Salto distribuzione.")
            continue

        sub_kpi_ids_of_this_master = data_retriever.get_sub_kpis_for_master(master_kpi_id)
        if not sub_kpi_ids_of_this_master:
            print(f"    Master KPI {master_kpi_id} non ha SubKPI collegati.")
            continue
        
        print(f"    Master KPI {master_kpi_id} ha SubKPIs: {sub_kpi_ids_of_this_master}")

        for target_num_to_process in [1, 2]: # Process Target 1 and Target 2
            master_target_value = master_target_entry[f"annual_target{target_num_to_process}"]
            
            sum_of_manual_sub_targets = 0.0
            non_manual_sub_kpis_for_this_target = []

            for sub_kpi_id in sub_kpi_ids_of_this_master:
                sub_target_entry = data_retriever.get_annual_target_entry(year, stabilimento_id, sub_kpi_id)
                sub_is_manual_this_target = False
                sub_target_value_this_target = 0.0

                if sub_target_entry:
                    sub_is_manual_this_target = bool(sub_target_entry[f"is_target{target_num_to_process}_manual"])
                    sub_target_value_this_target = sub_target_entry[f"annual_target{target_num_to_process}"]
                # If sub_target_entry is None, it means the subKPI has no target record yet.
                # It will be treated as non-manual by default and get a derived value.

                if sub_is_manual_this_target:
                    sum_of_manual_sub_targets += sub_target_value_this_target
                else:
                    non_manual_sub_kpis_for_this_target.append(sub_kpi_id)
            
            remaining_target_for_distribution = master_target_value - sum_of_manual_sub_targets
            num_non_manual_subs = len(non_manual_sub_kpis_for_this_target)
            
            print(f"    Target {target_num_to_process} per Master {master_kpi_id}: Val={master_target_value}, SommaManSub={sum_of_manual_sub_targets}, Rimanente={remaining_target_for_distribution}, NumNonManSub={num_non_manual_subs}")

            if num_non_manual_subs > 0:
                value_per_non_manual_sub = remaining_target_for_distribution / num_non_manual_subs
                
                with sqlite3.connect(DB_TARGETS) as conn_update_subs: # New connection for this specific sub-update loop
                    cursor_update_subs = conn_update_subs.cursor()
                    for sub_kpi_id_to_derive in non_manual_sub_kpis_for_this_target:
                        sub_record_derive = data_retriever.get_annual_target_entry(year, stabilimento_id, sub_kpi_id_to_derive)
                        
                        target_col_to_update = f"annual_target{target_num_to_process}"
                        manual_flag_col_to_update = f"is_target{target_num_to_process}_manual"

                        if sub_record_derive:
                            # Update existing record for this subKPI
                            cursor_update_subs.execute(
                                f"""UPDATE annual_targets SET {target_col_to_update}=?, {manual_flag_col_to_update}=?
                                    WHERE id=?""",
                                (value_per_non_manual_sub, False, sub_record_derive["id"])
                            )
                        else:
                            # Insert new record for this subKPI with derived value
                            # Default other properties or fetch from kpis table if necessary (e.g. default profile/logic)
                            # For simplicity, using some defaults here. A full implementation might fetch these.
                            default_repart_logic = REPARTITION_LOGIC_ANNO
                            default_repart_values = "{}"
                            default_dist_profile = PROFILE_ANNUAL_PROGRESSIVE
                            default_profile_params = "{}"
                            
                            # Determine values for the *other* target and its manual flag
                            other_target_num = 1 if target_num_to_process == 2 else 2
                            other_target_val = 0.0 # Default if no record
                            other_manual_flag = True # Default if no record

                            cursor_update_subs.execute(
                                """INSERT INTO annual_targets 
                                   (year, stabilimento_id, kpi_id, annual_target1, annual_target2, 
                                    repartition_logic, repartition_values, distribution_profile, profile_params,
                                    is_target1_manual, is_target2_manual) 
                                   VALUES (?,?,?, ?,?, ?,?,?,?, ?,?)""",
                                (year, stabilimento_id, sub_kpi_id_to_derive,
                                 value_per_non_manual_sub if target_num_to_process == 1 else other_target_val,
                                 value_per_non_manual_sub if target_num_to_process == 2 else other_target_val,
                                 default_repart_logic, default_repart_values, default_dist_profile, default_profile_params,
                                 False if target_num_to_process == 1 else other_manual_flag,
                                 False if target_num_to_process == 2 else other_manual_flag
                                 )
                            )
                        kpis_needing_repartition_update.add(sub_kpi_id_to_derive)
                        print(f"      SubKPI {sub_kpi_id_to_derive} Target {target_num_to_process} derivato: {value_per_non_manual_sub}")
                    conn_update_subs.commit()

    # Step 3: Recalculate repartitions for ALL kpis that were touched (initial save or derived)
    print(f"  KPIs che necessitano ricalcolo ripartizione: {kpis_needing_repartition_update}")
    for kpi_id_recalc in kpis_needing_repartition_update:
        calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_recalc, 1)
        calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_recalc, 2)

    # Step 4: Export CSVs
    try:
        if hasattr(export_manager, 'export_all_data_to_global_csvs'):
            export_manager.export_all_data_to_global_csvs(str(CSV_EXPORT_BASE_PATH))
        else: print("Funzione export_manager.export_all_data_to_global_csvs non trovata.")
    except Exception as e: print(f"ERRORE CRITICO durante la generazione dei CSV globali: {e}")
    print(f"Fine save_annual_targets per Anno: {year}, Stab: {stabilimento_id}")


# --- Logica di Ripartizione e Calcolo (Refined) ---
# _get_period_allocations, _get_raw_daily_values_for_repartition, _apply_event_adjustments_to_daily_values,
# _aggregate_and_save_periodic_targets remain largely the same, using data_retriever where appropriate.

def _get_period_allocations(annual_target, user_repartition_logic, user_repartition_values, year, kpi_calc_type, all_dates_in_year):
    """
    Helper to determine target sums/multipliers for primary repartition periods (month, quarter, week).
    For Incremental: period_allocations stores {period_key: target_sum_for_that_period}
    For Media: period_allocations stores {period_key: multiplier_for_that_period}
               (where period_key for MESE/TRIMESTRE is month_idx_0_based for consistency)
    """
    period_allocations = {}

    if kpi_calc_type == CALC_TYPE_INCREMENTALE:
        if user_repartition_logic == REPARTITION_LOGIC_MESE:
            # Ensure percentages are handled correctly (e.g., sum to 100 or normalized)
            raw_proportions = [user_repartition_values.get(calendar.month_name[i + 1], 0) for i in range(12)]
            total_user_prop = sum(p for p in raw_proportions if isinstance(p, (int, float))) / 100.0

            final_proportions = []
            if abs(total_user_prop - 1.0) > 0.01 and total_user_prop > 1e-9: # Normalize if not summing to 1 (or 100%)
                final_proportions = [(p / 100.0) / total_user_prop for p in raw_proportions]
            elif total_user_prop < 1e-9: # No user input or all zeros, distribute evenly
                final_proportions = [1.0 / 12.0] * 12
            else: # User input sums to 100% (or close enough)
                final_proportions = [p / 100.0 for p in raw_proportions]

            for i in range(12): # month_idx_0_based
                period_allocations[i] = annual_target * final_proportions[i]

        elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
            raw_proportions = [user_repartition_values.get(f"Q{i + 1}", 0) for i in range(4)]
            total_user_prop = sum(p for p in raw_proportions if isinstance(p, (int, float))) / 100.0
            final_proportions = []
            if abs(total_user_prop - 1.0) > 0.01 and total_user_prop > 1e-9:
                final_proportions = [(p / 100.0) / total_user_prop for p in raw_proportions]
            elif total_user_prop < 1e-9:
                final_proportions = [1.0 / 4.0] * 4
            else:
                final_proportions = [p / 100.0 for p in raw_proportions]
            for i in range(4): # quarter_idx_0_based
                period_allocations[i] = annual_target * final_proportions[i]

        elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
            # user_repartition_values is like {"2024-W01": 2.5, "2024-W02": 3.0} (percentages)
            total_prop_sum_user = sum(float(v) for v in user_repartition_values.values() if isinstance(v, (int, float, str)) and str(v).replace('.', '', 1).isdigit()) / 100.0

            if not user_repartition_values or total_prop_sum_user < 1e-9 : # Default to even distribution among all ISO weeks in the year
                unique_weeks_in_year = sorted(list(set(f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}" for d in all_dates_in_year)))
                num_iso_weeks_in_year = len(unique_weeks_in_year)
                default_prop_per_week = 1.0 / num_iso_weeks_in_year if num_iso_weeks_in_year > 0 else 0
                for wk_key in unique_weeks_in_year:
                    period_allocations[wk_key] = annual_target * default_prop_per_week
            else: # Use user-defined proportions, normalizing if necessary
                for week_str, prop_val_str in user_repartition_values.items():
                    try:
                        prop_val_perc = float(prop_val_str)
                        datetime.datetime.strptime(week_str + '-1', "%Y-W%W-%w") # Validate week format
                        normalized_prop = (prop_val_perc / 100.0)
                        if abs(total_prop_sum_user - 1.0) > 0.01 and total_prop_sum_user > 1e-9: # Normalize
                            normalized_prop = (prop_val_perc / 100.0) / total_prop_sum_user
                        period_allocations[week_str] = annual_target * normalized_prop
                    except (ValueError, TypeError):
                        print(f"Attenzione (Inc): Formato settimana o valore proporzione non valido per '{week_str}': '{prop_val_str}', saltato.")
                        # Fallback for this specific week - could be 0 or even split of remaining
                        # For simplicity, if invalid, it gets 0 allocation from user input.

    elif kpi_calc_type == CALC_TYPE_MEDIA:
        # For Media, user_repartition_values are target values or multipliers (e.g., if value is 80, it means target * 0.8)
        # The period_allocations will store these multipliers relative to the annual_target.
        if user_repartition_logic == REPARTITION_LOGIC_MESE:
            for i in range(12): # month_idx_0_based
                # Assuming user_repartition_values for Media/Month are direct target values for the month
                # To make it a multiplier: user_repartition_values.get(calendar.month_name[i+1], annual_target) / annual_target if annual_target else 1.0
                # Current logic implies they are percentages of the annual_target for that month.
                period_allocations[i] = float(user_repartition_values.get(calendar.month_name[i+1], 100.0))/100.0

        elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
            q_map_month_indices = [[0,1,2], [3,4,5], [6,7,8], [9,10,11]] # month_idx_0_based
            for q_idx_0based in range(4): # quarter_idx_0_based
                # Value for quarter is a percentage multiplier for months in that quarter
                q_multiplier_perc = float(user_repartition_values.get(f"Q{q_idx_0based+1}", 100.0))
                for month_idx_in_year_0based in q_map_month_indices[q_idx_0based]:
                    period_allocations[month_idx_in_year_0based] = q_multiplier_perc / 100.0

        elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
            # Values are percentage multipliers for each week
            for week_str, mult_val_str in user_repartition_values.items():
                try:
                    mult_val_perc = float(mult_val_str)
                    datetime.datetime.strptime(week_str + '-1', "%Y-W%W-%w") # Validate week format
                    period_allocations[week_str] = mult_val_perc / 100.0
                except (ValueError, TypeError):
                    print(f"Attenzione (Media): Formato settimana o valore moltiplicatore non valido per '{week_str}': '{mult_val_str}', saltato.")
                    # Fallback for this specific week
                    # period_allocations[week_str] = 1.0 # Default to annual average for this week
    return period_allocations

def _get_raw_daily_values_for_repartition(
    year, annual_target, kpi_calc_type, distribution_profile, profile_params,
    user_repartition_logic, period_allocations_map, all_dates_in_year
):
    # This function's logic remains largely the same as in the original problem description.
    # It calculates raw daily values based on the distribution profile and period allocations.
    days_in_year = len(all_dates_in_year)
    raw_daily_values = np.zeros(days_in_year)

    # --- INCREMENTAL KPI ---
    if kpi_calc_type == CALC_TYPE_INCREMENTALE:
        if distribution_profile == PROFILE_EVEN:
            if user_repartition_logic == REPARTITION_LOGIC_ANNO or not period_allocations_map:
                daily_val = annual_target / days_in_year if days_in_year > 0 else 0
                raw_daily_values.fill(daily_val)
            else:
                for d_idx, date_val in enumerate(all_dates_in_year):
                    target_sum_for_this_day_period = 0
                    num_days_in_this_day_period = 0
                    if user_repartition_logic == REPARTITION_LOGIC_MESE:
                        target_sum_for_this_day_period = period_allocations_map.get(date_val.month - 1, 0)
                        _, num_days_in_this_day_period = calendar.monthrange(year, date_val.month)
                    elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
                        q_idx_0_based = (date_val.month - 1) // 3
                        target_sum_for_this_day_period = period_allocations_map.get(q_idx_0_based, 0)
                        q_ranges = get_date_ranges_for_quarters(year)
                        q_start, q_end = q_ranges[q_idx_0_based + 1]
                        num_days_in_this_day_period = (q_end - q_start).days + 1
                    elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
                        iso_y, iso_w, _ = date_val.isocalendar()
                        wk_key = f"{iso_y}-W{iso_w:02d}"
                        target_sum_for_this_day_period = period_allocations_map.get(wk_key, 0)
                        num_days_in_this_day_period = sum(1 for d_in_wk in all_dates_in_year if d_in_wk.isocalendar()[0] == iso_y and d_in_wk.isocalendar()[1] == iso_w)
                    raw_daily_values[d_idx] = target_sum_for_this_day_period / num_days_in_this_day_period if num_days_in_this_day_period > 0 else 0
        # ... (all other Incremental profiles: ANNUAL_PROGRESSIVE, TRUE_ANNUAL_SINUSOIDAL, etc.)
        elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE:
            props = get_weighted_proportions(days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
            raw_daily_values = np.array([annual_target * p for p in props])
        elif distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
            amp = profile_params.get("sine_amplitude", SINE_AMPLITUDE_INCREMENTAL)
            phase = profile_params.get("sine_phase", SINE_PHASE_OFFSET)
            props = get_sinusoidal_proportions(days_in_year, amp, phase)
            raw_daily_values = np.array([annual_target * p for p in props])
        elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
            base_props = get_weighted_proportions(days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
            adj_props = np.array([base_props[i] * (WEEKDAY_BIAS_FACTOR_INCREMENTAL if all_dates_in_year[i].weekday() >= 5 else 1.0) for i in range(days_in_year)])
            current_sum_adj = np.sum(adj_props)
            final_props_adj = (adj_props / current_sum_adj) if current_sum_adj > 1e-9 else ([1.0 / days_in_year] * days_in_year if days_in_year > 0 else [])
            raw_daily_values = np.array([annual_target * p for p in final_props_adj])
        elif distribution_profile in [PROFILE_MONTHLY_SINUSOIDAL, PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE, PROFILE_QUARTERLY_PROGRESSIVE, PROFILE_QUARTERLY_SINUSOIDAL]:
            if user_repartition_logic == REPARTITION_LOGIC_MESE or \
               (user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE and distribution_profile in [PROFILE_MONTHLY_SINUSOIDAL, PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE]):
                monthly_target_sums_final = [0.0] * 12
                if user_repartition_logic == REPARTITION_LOGIC_MESE:
                    for m_idx_0based in range(12): monthly_target_sums_final[m_idx_0based] = period_allocations_map.get(m_idx_0based, 0)
                elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
                    q_map_month_indices = [[0,1,2], [3,4,5], [6,7,8], [9,10,11]]
                    for q_idx_0based, months_in_q_indices in enumerate(q_map_month_indices):
                        q_total_sum = period_allocations_map.get(q_idx_0based, 0)
                        num_months_in_q = len(months_in_q_indices)
                        month_weights_in_q = get_weighted_proportions(num_months_in_q, 1, 1) # Default even split
                        if distribution_profile == PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE:
                            month_weights_in_q = get_weighted_proportions(num_months_in_q, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
                        for i, month_idx_in_year_0based in enumerate(months_in_q_indices):
                            monthly_target_sums_final[month_idx_in_year_0based] = q_total_sum * month_weights_in_q[i]
                for month_idx_0based, month_sum_val in enumerate(monthly_target_sums_final):
                    current_month_1based = month_idx_0based + 1
                    num_days_in_month_val = calendar.monthrange(year, current_month_1based)[1]
                    if num_days_in_month_val == 0 or abs(month_sum_val) < 1e-9: continue
                    day_props_in_month_list = [1.0/num_days_in_month_val] * num_days_in_month_val
                    if distribution_profile == PROFILE_MONTHLY_SINUSOIDAL: day_props_in_month_list = get_parabolic_proportions(num_days_in_month_val, peak_at_center=True)
                    elif distribution_profile == PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE: day_props_in_month_list = get_weighted_proportions(num_days_in_month_val, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
                    month_start_day_idx_of_year = (datetime.date(year, current_month_1based, 1) - datetime.date(year, 1, 1)).days
                    for day_of_month_idx, prop in enumerate(day_props_in_month_list):
                        raw_daily_values[month_start_day_idx_of_year + day_of_month_idx] = month_sum_val * prop
            elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE and distribution_profile in [PROFILE_QUARTERLY_PROGRESSIVE, PROFILE_QUARTERLY_SINUSOIDAL]:
                q_date_ranges = get_date_ranges_for_quarters(year)
                for q_idx_0based in range(4):
                    q_total_sum = period_allocations_map.get(q_idx_0based, 0)
                    if abs(q_total_sum) < 1e-9: continue
                    q_start_date, q_end_date = q_date_ranges[q_idx_0based + 1]
                    num_days_in_q_val = (q_end_date - q_start_date).days + 1
                    day_props_in_q_list = [1.0/num_days_in_q_val] * num_days_in_q_val
                    if distribution_profile == PROFILE_QUARTERLY_PROGRESSIVE: day_props_in_q_list = get_weighted_proportions(num_days_in_q_val, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
                    elif distribution_profile == PROFILE_QUARTERLY_SINUSOIDAL: day_props_in_q_list = get_parabolic_proportions(num_days_in_q_val, peak_at_center=True)
                    q_start_day_idx_of_year = (q_start_date - datetime.date(year, 1, 1)).days
                    for day_of_q_idx, prop in enumerate(day_props_in_q_list):
                        raw_daily_values[q_start_day_idx_of_year + day_of_q_idx] = q_total_sum * prop
        else: # Fallback for unhandled incremental profile
            props = get_weighted_proportions(days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
            raw_daily_values = np.array([annual_target * p for p in props])

    # --- MEDIA KPI ---
    elif kpi_calc_type == CALC_TYPE_MEDIA:
        for d_idx, date_val in enumerate(all_dates_in_year):
            base_avg_for_day_from_repart = annual_target
            if user_repartition_logic == REPARTITION_LOGIC_MESE: base_avg_for_day_from_repart = annual_target * period_allocations_map.get(date_val.month - 1, 1.0)
            elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE: base_avg_for_day_from_repart = annual_target * period_allocations_map.get(date_val.month - 1, 1.0) # Uses month index for quarterly multipliers too
            elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
                iso_y, iso_w, _ = date_val.isocalendar(); wk_key = f"{iso_y}-W{iso_w:02d}"
                base_avg_for_day_from_repart = annual_target * period_allocations_map.get(wk_key, 1.0)
            
            # ... (all Media profiles: EVEN, ANNUAL_PROGRESSIVE, TRUE_ANNUAL_SINUSOIDAL, etc.)
            if distribution_profile == PROFILE_EVEN: raw_daily_values[d_idx] = base_avg_for_day_from_repart
            elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE:
                factors_prog = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year)
                deviation = factors_prog[d_idx] - 1.0
                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (1 + deviation * DEVIATION_SCALE_FACTOR_AVG)
            elif distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
                amp = profile_params.get("sine_amplitude", SINE_AMPLITUDE_MEDIA)
                phase = profile_params.get("sine_phase", SINE_PHASE_OFFSET)
                x_annual_sin = np.linspace(0, 2 * np.pi, days_in_year, endpoint=False)
                sine_mod = amp * np.sin(x_annual_sin[d_idx] + phase)
                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (1 + sine_mod)
            elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
                factors_bias = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year)
                deviation_bias = factors_bias[d_idx] - 1.0
                day_target_val_bias = base_avg_for_day_from_repart * (1 + deviation_bias * DEVIATION_SCALE_FACTOR_AVG)
                if date_val.weekday() >= 5: day_target_val_bias *= WEEKDAY_BIAS_FACTOR_MEDIA
                raw_daily_values[d_idx] = day_target_val_bias
            elif distribution_profile in [PROFILE_MONTHLY_SINUSOIDAL, PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE, PROFILE_QUARTERLY_PROGRESSIVE, PROFILE_QUARTERLY_SINUSOIDAL]:
                num_days_mod_period, day_idx_mod_period = 0,0
                if distribution_profile in [PROFILE_MONTHLY_SINUSOIDAL, PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE]:
                    num_days_mod_period = calendar.monthrange(year, date_val.month)[1]; day_idx_mod_period = date_val.day - 1
                elif distribution_profile in [PROFILE_QUARTERLY_PROGRESSIVE, PROFILE_QUARTERLY_SINUSOIDAL]:
                    q_idx_0based = (date_val.month - 1) // 3; q_ranges_mod = get_date_ranges_for_quarters(year)
                    q_start_mod, q_end_mod = q_ranges_mod[q_idx_0based + 1]
                    num_days_mod_period = (q_end_mod - q_start_mod).days + 1; day_idx_mod_period = (date_val - q_start_mod).days
                if num_days_mod_period == 0: raw_daily_values[d_idx] = base_avg_for_day_from_repart; continue
                modulation_factor_val = 0.0
                if distribution_profile in [PROFILE_MONTHLY_SINUSOIDAL, PROFILE_QUARTERLY_SINUSOIDAL]: # Parabolic / Sinusoidal within period
                    par_weights_mod = np.zeros(num_days_mod_period); mid_idx_mod = (num_days_mod_period - 1) / 2.0
                    for i_mod in range(num_days_mod_period): par_weights_mod[i_mod] = (i_mod - mid_idx_mod)**2
                    par_weights_mod = np.max(par_weights_mod) - par_weights_mod
                    mean_w_mod = np.mean(par_weights_mod) if num_days_mod_period > 1 else par_weights_mod[0]
                    norm_mod_val_calc = par_weights_mod[day_idx_mod_period] - mean_w_mod
                    max_abs_dev_mod = np.max(np.abs(par_weights_mod - mean_w_mod)) if num_days_mod_period > 1 else (abs(par_weights_mod[0]-mean_w_mod) if num_days_mod_period == 1 else 0)
                    if max_abs_dev_mod > 1e-9: norm_mod_val_calc /= max_abs_dev_mod
                    modulation_factor_val = norm_mod_val_calc * DEVIATION_SCALE_FACTOR_AVG
                elif distribution_profile in [PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE, PROFILE_QUARTERLY_PROGRESSIVE]: # Progressive within period
                    factors_period_mod = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, num_days_mod_period)
                    deviation_period_mod = factors_period_mod[day_idx_mod_period] - 1.0
                    modulation_factor_val = deviation_period_mod * DEVIATION_SCALE_FACTOR_AVG
                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (1 + modulation_factor_val)
            else: # Fallback for unhandled media profile
                raw_daily_values[d_idx] = base_avg_for_day_from_repart
    else:
        print(f"Tipo calcolo KPI sconosciuto: {kpi_calc_type}")
    return raw_daily_values


def _apply_event_adjustments_to_daily_values(raw_daily_values_input, event_data_list, kpi_calc_type, annual_target_for_norm, all_dates_in_year):
    # This function's logic remains the same.
    if not event_data_list: return raw_daily_values_input
    adjusted_daily_values = np.copy(raw_daily_values_input)
    for event in event_data_list:
        try:
            start_event_date_obj = datetime.datetime.strptime(event['start_date'], '%Y-%m-%d').date()
            end_event_date_obj = datetime.datetime.strptime(event['end_date'], '%Y-%m-%d').date()
            multiplier_event = float(event.get('multiplier', 1.0))
            addition_event = float(event.get('addition', 0.0))
            for d_idx_event, date_val_event_loop in enumerate(all_dates_in_year):
                if start_event_date_obj <= date_val_event_loop <= end_event_date_obj:
                    if kpi_calc_type == CALC_TYPE_MEDIA:
                        adjusted_daily_values[d_idx_event] = adjusted_daily_values[d_idx_event] * multiplier_event + addition_event
                    elif kpi_calc_type == CALC_TYPE_INCREMENTALE:
                        adjusted_daily_values[d_idx_event] *= multiplier_event
                        if abs(addition_event) > 1e-9: adjusted_daily_values[d_idx_event] += addition_event
        except (ValueError, KeyError, TypeError) as e_event_proc:
            print(f"Attenzione: Dati evento non validi o errore elaborazione, saltato. Dettagli: {event}, Errore: {e_event_proc}")
            continue
    if kpi_calc_type == CALC_TYPE_INCREMENTALE:
        current_total_after_events_val = np.sum(adjusted_daily_values)
        if abs(annual_target_for_norm) < 1e-9: adjusted_daily_values.fill(0.0)
        elif abs(current_total_after_events_val) > 1e-9 : adjusted_daily_values = (adjusted_daily_values / current_total_after_events_val) * annual_target_for_norm
    return adjusted_daily_values


def _aggregate_and_save_periodic_targets(
    daily_targets_list_of_tuples, year, stabilimento_id, kpi_spec_id, target_number, kpi_calc_type
):
    # This function's logic remains the same (saving to daily, weekly, monthly, quarterly DBs).
    if not daily_targets_list_of_tuples: return

    with sqlite3.connect(DB_KPI_DAYS) as conn:
        conn.executemany(
            "INSERT INTO daily_targets (year,stabilimento_id,kpi_id,target_number,date_value,target_value) VALUES (?,?,?,?,?,?)",
            [(year, stabilimento_id, kpi_spec_id, target_number, d.isoformat(), t) for d, t in daily_targets_list_of_tuples])
        conn.commit()

    weekly_agg_data = {}
    for date_val, daily_target_val in daily_targets_list_of_tuples:
        iso_y_cal, iso_w_num, _ = date_val.isocalendar(); week_key_str = f"{iso_y_cal}-W{iso_w_num:02d}"
        if week_key_str not in weekly_agg_data: weekly_agg_data[week_key_str] = []
        weekly_agg_data[week_key_str].append(daily_target_val)
    db_week_recs = []
    for wk_key, tgts_in_wk_list in sorted(weekly_agg_data.items()):
        if not tgts_in_wk_list: continue
        wt_val = sum(tgts_in_wk_list) if kpi_calc_type == CALC_TYPE_INCREMENTALE else (sum(tgts_in_wk_list) / len(tgts_in_wk_list) if tgts_in_wk_list else 0)
        db_week_recs.append((year, stabilimento_id, kpi_spec_id, target_number, wk_key, wt_val))
    if db_week_recs:
        with sqlite3.connect(DB_KPI_WEEKS) as conn:
            conn.executemany("INSERT INTO weekly_targets (year,stabilimento_id,kpi_id,target_number,week_value,target_value) VALUES (?,?,?,?,?,?)", db_week_recs)
            conn.commit()

    monthly_agg_data_map = {i: [] for i in range(12)}
    for date_val, daily_target_val in daily_targets_list_of_tuples:
        if date_val.year == year: monthly_agg_data_map[date_val.month - 1].append(daily_target_val)
    db_month_recs = []
    for month_idx_0based in range(12):
        tgts_in_m_list = monthly_agg_data_map[month_idx_0based]; month_name_str = calendar.month_name[month_idx_0based + 1]; mt_val = 0.0
        if tgts_in_m_list: mt_val = sum(tgts_in_m_list) if kpi_calc_type == CALC_TYPE_INCREMENTALE else (sum(tgts_in_m_list) / len(tgts_in_m_list) if tgts_in_m_list else 0)
        db_month_recs.append((year, stabilimento_id, kpi_spec_id, target_number, month_name_str, mt_val))
    if db_month_recs:
        with sqlite3.connect(DB_KPI_MONTHS) as conn:
            conn.executemany("INSERT INTO monthly_targets (year,stabilimento_id,kpi_id,target_number,month_value,target_value) VALUES (?,?,?,?,?,?)", db_month_recs)
            conn.commit()

    quarterly_agg_data_map = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
    actual_monthly_tgts_for_q_calc = {rec[4]: rec[5] for rec in db_month_recs} # month_name: target_value
    month_to_q_map_val = {calendar.month_name[i]: f"Q{((i-1)//3)+1}" for i in range(1, 13)}
    for mn_name_str, mt_val_for_q in actual_monthly_tgts_for_q_calc.items():
        if mn_name_str in month_to_q_map_val: quarterly_agg_data_map[month_to_q_map_val[mn_name_str]].append(mt_val_for_q)
    db_quarter_recs = []
    for qn_str in ["Q1", "Q2", "Q3", "Q4"]:
        tgts_in_q_list = quarterly_agg_data_map[qn_str]; qt_val = 0.0
        if tgts_in_q_list: qt_val = sum(tgts_in_q_list) if kpi_calc_type == CALC_TYPE_INCREMENTALE else (sum(tgts_in_q_list) / len(tgts_in_q_list) if tgts_in_q_list else 0)
        db_quarter_recs.append((year, stabilimento_id, kpi_spec_id, target_number, qn_str, qt_val))
    if db_quarter_recs:
        with sqlite3.connect(DB_KPI_QUARTERS) as conn:
            conn.executemany("INSERT INTO quarterly_targets (year,stabilimento_id,kpi_id,target_number,quarter_value,target_value) VALUES (?,?,?,?,?,?)", db_quarter_recs)
            conn.commit()


def calculate_and_save_all_repartitions(
    year, stabilimento_id, kpi_spec_id, target_number
):
    """
    Calculates and saves daily, weekly, monthly, and quarterly repartitions
    for a given annual target of a specific KPI.

    Args:
        year (int): The year for which to calculate targets.
        stabilimento_id (int): The ID of the stabilimento.
        kpi_spec_id (int): The ID of the KPI specification (kpis.id).
        target_number (int): The target number (1 or 2) to process.
    """
    target_info = data_retriever.get_annual_target_entry(
        year, stabilimento_id, kpi_spec_id
    )
    if not target_info:
        # Optional: Log this, but often it's normal for not all KPIs to have targets
        # print(f"INFO: Nessun target annuale trovato per KPI {kpi_spec_id}, Anno {year}, Stab {stabilimento_id}, TargetNum {target_number}. Salto ripartizione.")
        return

    kpi_details = data_retriever.get_kpi_detailed_by_id(kpi_spec_id)
    if not kpi_details:
        print(f"ERRORE: Dettagli KPI ID {kpi_spec_id} non trovati. Salto ripartizione.")
        return

    annual_target_to_use = None
    if target_number == 1:
        # Ensure 'annual_target1' key exists before accessing
        annual_target_to_use = (
            target_info["annual_target1"]
            if "annual_target1" in target_info.keys()
            else None
        )
    elif target_number == 2:
        # Ensure 'annual_target2' key exists before accessing
        annual_target_to_use = (
            target_info["annual_target2"]
            if "annual_target2" in target_info.keys()
            else None
        )
    else:
        print(
            f"ERRORE: Numero target non valido ({target_number}) per KPI {kpi_spec_id}. Salto ripartizione."
        )
        return

    if annual_target_to_use is None:
        # This means the column might be missing or its value is None.
        # If the target is genuinely not set (None), we clear periodic data.
        # If the target is 0, repartitions will still be calculated (resulting in 0s).
        print(
            f"INFO: Target annuale {target_number} per KPI {kpi_spec_id}, Anno {year}, Stab {stabilimento_id} non impostato (None). Pulizia dati periodici."
        )
        dbs_to_clear = [
            (DB_KPI_DAYS, "daily_targets"),
            (DB_KPI_WEEKS, "weekly_targets"),
            (DB_KPI_MONTHS, "monthly_targets"),
            (DB_KPI_QUARTERS, "quarterly_targets"),
        ]
        for db_path, table_name in dbs_to_clear:
            with sqlite3.connect(db_path) as conn:
                conn.cursor().execute(
                    f"DELETE FROM {table_name} WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                    (year, stabilimento_id, kpi_spec_id, target_number),
                )
                conn.commit()
        return

    # Safely access other required columns from target_info (sqlite3.Row)
    user_repart_logic = (
        target_info["repartition_logic"]
        if "repartition_logic" in target_info.keys()
        else REPARTITION_LOGIC_ANNO
    )  # Default if missing
    distribution_profile = (
        target_info["distribution_profile"]
        if "distribution_profile" in target_info.keys()
        else PROFILE_ANNUAL_PROGRESSIVE
    )  # Default if missing

    user_repart_values = {}
    try:
        repart_values_str = (
            target_info["repartition_values"]
            if "repartition_values" in target_info.keys()
            else "{}"
        )
        user_repart_values = json.loads(
            repart_values_str or "{}"
        )  # Ensure "or {}" for None case
    except json.JSONDecodeError:
        repart_values_str_for_log = (
            target_info["repartition_values"]
            if "repartition_values" in target_info.keys()
            else "COLONNA MANCANTE"
        )
        print(
            f"WARN: JSON repartition_values non valido per KPI {kpi_spec_id}. Stringa: '{repart_values_str_for_log}'. Uso default ({{}})."
        )
    except KeyError:
        print(
            f"WARN: Colonna 'repartition_values' mancante per KPI {kpi_spec_id}. Uso default ({{}})."
        )

    profile_params = {}
    profile_params_str_for_log = "COLONNA MANCANTE O VALORE NON IMPOSTATO"
    try:
        if "profile_params" in target_info.keys():
            profile_params_json_str = target_info["profile_params"]
            profile_params_str_for_log = (
                profile_params_json_str
                if profile_params_json_str is not None
                else "None (valore effettivo)"
            )
            if profile_params_json_str:
                profile_params = json.loads(profile_params_json_str)
        else:
            # If column doesn't exist in the row (e.g., older DB row before ALTER), profile_params remains {}
            pass  # print(f"INFO: Colonna 'profile_params' non presente per KPI {kpi_spec_id}. Uso default ({{}}).")
    except json.JSONDecodeError:
        print(
            f"WARN: JSON profile_params non valido per KPI {kpi_spec_id}. Stringa: '{profile_params_str_for_log}'. Uso default ({{}})."
        )
    except KeyError:  # Should be caught by 'in target_info.keys()'
        print(
            f"WARN: Colonna 'profile_params' mancante (KeyError) per KPI {kpi_spec_id}. Uso default ({{}})."
        )

    # Safely access kpi_calc_type from kpi_details (sqlite3.Row)
    kpi_calc_type = (
        kpi_details["calculation_type"]
        if "calculation_type" in kpi_details.keys()
        else CALC_TYPE_INCREMENTALE
    )  # Default if missing

    # Clear existing periodic data for this specific target number before recalculating
    for db_path_clear, table_name_clear in [
        (DB_KPI_DAYS, "daily_targets"),
        (DB_KPI_WEEKS, "weekly_targets"),
        (DB_KPI_MONTHS, "monthly_targets"),
        (DB_KPI_QUARTERS, "quarterly_targets"),
    ]:
        with sqlite3.connect(db_path_clear) as conn_clear:
            conn_clear.cursor().execute(
                f"DELETE FROM {table_name_clear} WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                (year, stabilimento_id, kpi_spec_id, target_number),
            )
            conn_clear.commit()

    # Proceed with calculations
    days_in_year_count = (
        datetime.date(year, 12, 31) - datetime.date(year, 1, 1)
    ).days + 1
    all_dates_in_year_list = [
        datetime.date(year, 1, 1) + datetime.timedelta(days=i)
        for i in range(days_in_year_count)
    ]

    period_allocations_map = _get_period_allocations(
        annual_target_to_use,
        user_repart_logic,
        user_repart_values,
        year,
        kpi_calc_type,
        all_dates_in_year_list,
    )

    raw_daily_target_values = _get_raw_daily_values_for_repartition(
        year,
        annual_target_to_use,
        kpi_calc_type,
        distribution_profile,
        profile_params,
        user_repart_logic,
        period_allocations_map,
        all_dates_in_year_list,
    )

    # .get() on profile_params (which is now a Python dict) is safe
    event_data_from_params = profile_params.get("events", [])
    if event_data_from_params:
        raw_daily_target_values = _apply_event_adjustments_to_daily_values(
            raw_daily_target_values,
            event_data_from_params,
            kpi_calc_type,
            annual_target_to_use,
            all_dates_in_year_list,
        )

    daily_targets_to_save = [
        (all_dates_in_year_list[i], raw_daily_target_values[i])
        for i in range(days_in_year_count)
    ]

    _aggregate_and_save_periodic_targets(
        daily_targets_to_save,
        year,
        stabilimento_id,
        kpi_spec_id,
        target_number,
        kpi_calc_type,
    )

    # Safe access for display values from kpi_details (sqlite3.Row)
    group_name_disp = (
        kpi_details["group_name"] if "group_name" in kpi_details.keys() else "N/A"
    )
    subgroup_name_disp = (
        kpi_details["subgroup_name"] if "subgroup_name" in kpi_details.keys() else "N/A"
    )
    indicator_name_disp = (
        kpi_details["indicator_name"]
        if "indicator_name" in kpi_details.keys()
        else "N/A"
    )
    kpi_full_name_display = (
        f"{group_name_disp}>{subgroup_name_disp}>{indicator_name_disp}"
    )


# --- Main Test Block ---
if __name__ == "__main__":
    print("Esecuzione di database_manager.py come script principale (per setup/test).")
    setup_databases()

    def _ensure_kpi_for_test(group_name, subgroup_name, indicator_name, calc_type, unit, subgroup_template_id=None):
        try: group_id = add_kpi_group(group_name)
        except sqlite3.IntegrityError: group_id = next((g['id'] for g in data_retriever.get_kpi_groups() if g['name'] == group_name), None)
        if not group_id: raise Exception(f"Failed to get group_id for {group_name}")

        try: subgroup_id = add_kpi_subgroup(subgroup_name, group_id, subgroup_template_id)
        except sqlite3.IntegrityError:
            sgs = data_retriever.get_kpi_subgroups_by_group_revised(group_id)
            subgroup_id = next((sg['id'] for sg in sgs if sg['name'] == subgroup_name), None)
        if not subgroup_id: raise Exception(f"Failed to get subgroup_id for {subgroup_name}")

        actual_indicator_id = None
        if not subgroup_template_id:
            try: actual_indicator_id = add_kpi_indicator(indicator_name, subgroup_id)
            except sqlite3.IntegrityError:
                inds = data_retriever.get_kpi_indicators_by_subgroup(subgroup_id)
                actual_indicator_id = next((i['id'] for i in inds if i['name'] == indicator_name), None)
        else:
            inds_from_template_subgroup = data_retriever.get_kpi_indicators_by_subgroup(subgroup_id)
            actual_indicator_id = next((i['id'] for i in inds_from_template_subgroup if i['name'] == indicator_name), None)
        if not actual_indicator_id: raise Exception(f"Failed to get/ensure indicator_id for {indicator_name}")
        
        try: kpi_spec_id = add_kpi_spec(actual_indicator_id, f"{indicator_name} ({calc_type})", calc_type, unit, True)
        except Exception: # Covers IntegrityError from add_kpi_spec if already exists and update is called
             kpi_spec_row = None
             with sqlite3.connect(DB_KPIS) as conn:
                 kpi_spec_row = conn.execute("SELECT id FROM kpis WHERE indicator_id = ?", (actual_indicator_id,)).fetchone()
             kpi_spec_id = kpi_spec_row[0] if kpi_spec_row else None
        if not kpi_spec_id: raise Exception(f"Failed to ensure kpi_spec_id for {indicator_name}")
        return kpi_spec_id


    def _ensure_stabilimento_for_test(name):
        try: return add_stabilimento(name, True)
        except sqlite3.IntegrityError: return next((s['id'] for s in data_retriever.get_all_stabilimenti() if s['name'] == name), None)

    print("\n--- Inizio Test Logica Template KPI ---")
    try:
        # ... (template test logic from original file, using data_retriever for gets)
        template_name_test = "Standard Customer KPIs"
        try: customer_template_id = add_kpi_indicator_template(template_name_test, "A standard set.")
        except sqlite3.IntegrityError:
            tpls = data_retriever.get_kpi_indicator_templates()
            customer_template_id = next((t['id'] for t in tpls if t['name'] == template_name_test), None)
            if customer_template_id: # Clear for clean test
                defs_to_clear = data_retriever.get_template_defined_indicators(customer_template_id)
                for d_clear in defs_to_clear: remove_indicator_definition_from_template(d_clear['id'])
        if not customer_template_id: raise Exception("Failed to create/find template for test")
        
        add_indicator_definition_to_template(customer_template_id, "Official Claim Information", CALC_TYPE_INCREMENTALE, "Count", True, "Num official claims.")
        add_indicator_definition_to_template(customer_template_id, "Logistic Claim", CALC_TYPE_INCREMENTALE, "Count", True, "Num logistic claims.")
        
        group_name_tpl_test = "Customer Relations Test Dept"
        subgroup_name_retail_test = "Retail Customers Test"
        try: test_group_id_tpl = add_kpi_group(group_name_tpl_test)
        except sqlite3.IntegrityError: test_group_id_tpl = next((g['id'] for g in data_retriever.get_kpi_groups() if g['name'] == group_name_tpl_test), None)

        retail_subgroup_id_test = add_kpi_subgroup(subgroup_name_retail_test, test_group_id_tpl, customer_template_id)
        retail_indicators_after_creation = data_retriever.get_kpi_indicators_by_subgroup(retail_subgroup_id_test)
        print(f"Indicatori in '{subgroup_name_retail_test}': {[i['name'] for i in retail_indicators_after_creation]}")
        # assert len(retail_indicators_after_creation) == 2 # This might fail if previous runs left data
        print("\n--- Fine Test Logica Template KPI ---")
    except Exception as e: print(f"ERRORE durante il test dei template KPI: {e}")


    # Test Master/Sub Link & Target Distribution
    master_kpi_id_test = _ensure_kpi_for_test("Finance", "Overall Profit", "Total Profit EUR", CALC_TYPE_INCREMENTALE, "EUR")
    sub_kpi1_id_test = _ensure_kpi_for_test("Finance", "Product Profit", "Profit Product A", CALC_TYPE_INCREMENTALE, "EUR")
    sub_kpi2_id_test = _ensure_kpi_for_test("Finance", "Product Profit", "Profit Product B", CALC_TYPE_INCREMENTALE, "EUR")
    sub_kpi3_id_test = _ensure_kpi_for_test("Finance", "Service Profit", "Profit Services", CALC_TYPE_INCREMENTALE, "EUR")
    stab_id_main_test = _ensure_stabilimento_for_test("Main Plant Test")
    current_year_test = datetime.datetime.now().year

    if master_kpi_id_test and sub_kpi1_id_test and sub_kpi2_id_test and sub_kpi3_id_test and stab_id_main_test:
        print("\n--- Test Master/Sub KPI Logic & Target Distribution ---")
        try:
            add_master_sub_kpi_link(master_kpi_id_test, sub_kpi1_id_test)
            add_master_sub_kpi_link(master_kpi_id_test, sub_kpi2_id_test)
            add_master_sub_kpi_link(master_kpi_id_test, sub_kpi3_id_test)
            print(f"Linked Master {master_kpi_id_test} to Subs: {sub_kpi1_id_test}, {sub_kpi2_id_test}, {sub_kpi3_id_test}")
        except ValueError as ve: # Catch custom errors from add_master_sub_kpi_link
            print(f"Error linking KPIs: {ve}")
        except sqlite3.IntegrityError:
            print("Links potrebbero già esistere.")

        # Scenario: Master target 10000. SubKPI1 manual 2000. SubKPI2 manual 3000. SubKPI3 derived.
        targets_to_set = {
            str(master_kpi_id_test): {
                "annual_target1": 10000.0, "annual_target2": 0.0,
                "repartition_logic": REPARTITION_LOGIC_ANNO, "repartition_values": {},
                "distribution_profile": PROFILE_EVEN, "profile_params": {},
                "is_target1_manual": True, "is_target2_manual": True
            },
            str(sub_kpi1_id_test): {
                "annual_target1": 2000.0, "annual_target2": 0.0,
                "repartition_logic": REPARTITION_LOGIC_ANNO, "repartition_values": {},
                "distribution_profile": PROFILE_EVEN, "profile_params": {},
                "is_target1_manual": True, "is_target2_manual": True
            },
            str(sub_kpi2_id_test): {
                "annual_target1": 3000.0, "annual_target2": 0.0,
                "repartition_logic": REPARTITION_LOGIC_ANNO, "repartition_values": {},
                "distribution_profile": PROFILE_EVEN, "profile_params": {},
                "is_target1_manual": True, "is_target2_manual": True
            },
            # SubKPI3 is NOT in targets_to_set, its target1 should be derived (10000 - 2000 - 3000 = 5000)
            # Its is_target1_manual should become False.
        }
        print(f"Salvataggio targets con Master {master_kpi_id_test} e SubKPIs manuali {sub_kpi1_id_test}, {sub_kpi2_id_test}...")
        save_annual_targets(current_year_test, stab_id_main_test, targets_to_set, initiator_kpi_spec_id=master_kpi_id_test)
        
        print("\nVerifica Target SubKPIs:")
        for sub_id, expected_t1, expected_manual1 in [
            (sub_kpi1_id_test, 2000.0, True),
            (sub_kpi2_id_test, 3000.0, True),
            (sub_kpi3_id_test, 5000.0, False) # Derived
        ]:
            entry = data_retriever.get_annual_target_entry(current_year_test, stab_id_main_test, sub_id)
            if entry:
                actual_t1 = entry['annual_target1']
                actual_manual1 = entry['is_target1_manual']
                status = "CORRECT" if abs(actual_t1 - expected_t1) < 0.01 and actual_manual1 == expected_manual1 else "INCORRECT"
                print(f"  SubKPI {sub_id}: Target1={actual_t1} (Exp: {expected_t1}), Manual1={actual_manual1} (Exp: {expected_manual1}) -> {status}")
            else:
                print(f"  SubKPI {sub_id}: NESSUN TARGET TROVATO - INCORRECT")
    else:
        print("Skipping Master/Sub test avanzato a causa di fallimento setup KPI/Stabilimento.")

    print("\n--- Test database_manager.py completato ---")
