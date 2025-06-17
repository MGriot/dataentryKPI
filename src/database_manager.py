# database_manager.py
import sqlite3
import json
from pathlib import Path
import datetime
import calendar
import numpy as np
import export_manager # Assuming this exists and is correctly set up

# --- CONFIGURAZIONE DATABASE ---
BASE_DIR = Path(__file__).parent
DB_KPIS = BASE_DIR / "db_kpis.db"
DB_STABILIMENTI = BASE_DIR / "db_stabilimenti.db"
DB_TARGETS = BASE_DIR / "db_kpi_targets.db"

DB_KPI_DAYS = BASE_DIR / "db_kpi_days.db"
DB_KPI_WEEKS = BASE_DIR / "db_kpi_weeks.db"
DB_KPI_MONTHS = BASE_DIR / "db_kpi_months.db"
DB_KPI_QUARTERS = BASE_DIR / "db_kpi_quarters.db"

# --- NUOVI DATABASE PER TEMPLATE ---
DB_KPI_TEMPLATES = BASE_DIR / "db_kpi_templates.db"


CSV_EXPORT_BASE_PATH = BASE_DIR / "csv_exports"

# --- COSTANTI DI RIPARTIZIONE ---
WEIGHT_INITIAL_FACTOR_INC = 1.5
WEIGHT_FINAL_FACTOR_INC = 0.5
WEIGHT_INITIAL_FACTOR_AVG = 1.2 # Represents a deviation, e.g. target * (1 - factor) -> actual target * (1 - (1-factor))
WEIGHT_FINAL_FACTOR_AVG = 0.8   # Represents a deviation, e.g. target * (1 + (factor-1))
DEVIATION_SCALE_FACTOR_AVG = 0.2 # General scalar for how much media KPIs deviate from base

# Sinusoidal defaults (could be made configurable via DB in the future, e.g. in profile_params)
SINE_AMPLITUDE_INCREMENTAL = 0.5 # Affects peak-to-trough for proportions before normalization
SINE_AMPLITUDE_MEDIA = 0.1 # e.g. +/- 10% deviation for Media KPIs from base
SINE_PHASE_OFFSET = -np.pi / 2 # Starts at the trough for a typical annual cycle (e.g. winter low, summer high for demand)

WEEKDAY_BIAS_FACTOR_INCREMENTAL = 0.5 # Weekend day gets this fraction of a weekday's value before normalization
WEEKDAY_BIAS_FACTOR_MEDIA = 0.8 # Weekend day target is this multiplier of the weekday target's base


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
    if min_raw_weight <= 0: # Ensure weights are positive before normalization
        shift = abs(min_raw_weight) + 1e-9 # Add a small epsilon to avoid zero if min_raw_weight was 0
        raw_weights = [w + shift for w in raw_weights]
    total_weight = sum(raw_weights)
    return (
        [w / total_weight for w in raw_weights]
        if total_weight != 0
        else [1.0 / num_periods] * num_periods
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
        raw_weights = np.max(raw_weights) - raw_weights # Makes it a peak
    # else: it's a valley shape
    raw_weights += min_value_epsilon # Ensure positive weights
    total_weight = np.sum(raw_weights)
    return (
        (raw_weights / total_weight).tolist()
        if total_weight != 0
        else [1.0 / num_periods] * num_periods
    )

def get_sinusoidal_proportions(num_periods, amplitude=0.5, phase_offset=0, min_value_epsilon=1e-9):
    if num_periods <= 0: return []
    if num_periods == 1: return [1.0]
    x = np.linspace(0, 2 * np.pi, num_periods, endpoint=False) # endpoint=False for better annual cycle continuity if wrapped
    # Base is 1, so raw_weights will be > 0 if amplitude < 1
    raw_weights = 1 + amplitude * np.sin(x + phase_offset)
    # Ensure positive weights, especially if amplitude >= 1
    raw_weights = np.maximum(raw_weights, min_value_epsilon)
    total_weight = np.sum(raw_weights)
    return (raw_weights / total_weight).tolist() if total_weight > 0 else [1.0 / num_periods] * num_periods


def get_date_ranges_for_quarters(year):
    q_ranges = {}
    q_ranges[1] = (datetime.date(year, 1, 1), datetime.date(year, 3, 31))
    q_ranges[2] = (datetime.date(year, 4, 1), datetime.date(year, 6, 30))
    q_ranges[3] = (datetime.date(year, 7, 1), datetime.date(year, 9, 30))
    # Adjust for leap year for Q4 end date if necessary, though monthrange handles it
    q_end_month = 12
    q_end_day = calendar.monthrange(year, q_end_month)[1]
    q_ranges[4] = (datetime.date(year, 10, 1), datetime.date(year, q_end_month, q_end_day))
    return q_ranges


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
                indicator_template_id INTEGER, /* NUOVA COLONNA */
                FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE,
                FOREIGN KEY (indicator_template_id) REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL, /* NUOVO FK */
                UNIQUE (name, group_id) )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS kpi_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, subgroup_id INTEGER NOT NULL,
                FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE, UNIQUE (name, subgroup_id) )"""
        )
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS kpis (
                id INTEGER PRIMARY KEY AUTOINCREMENT, indicator_id INTEGER NOT NULL, description TEXT,
                calculation_type TEXT NOT NULL CHECK(calculation_type IN ('Incrementale', 'Media')),
                unit_of_measure TEXT, visible BOOLEAN NOT NULL DEFAULT 1,
                FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE,
                UNIQUE (indicator_id) )"""
        )
        # Check and add indicator_template_id to kpi_subgroups if not exists
        cursor.execute("PRAGMA table_info(kpi_subgroups)")
        subgroup_columns = {col[1] for col in cursor.fetchall()}
        if "indicator_template_id" not in subgroup_columns:
            try:
                cursor.execute("ALTER TABLE kpi_subgroups ADD COLUMN indicator_template_id INTEGER REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL")
                print("Aggiunta colonna 'indicator_template_id' a 'kpi_subgroups'.")
            except sqlite3.OperationalError as e:
                print(f"WARN: Could not add 'indicator_template_id' to 'kpi_subgroups', might exist or other issue: {e}")
                pass


        cursor.execute("PRAGMA table_info(kpis)")
        kpi_columns_set = {col[1] for col in cursor.fetchall()}
        if "unit_of_measure" not in kpi_columns_set:
            try:
                cursor.execute("ALTER TABLE kpis ADD COLUMN unit_of_measure TEXT")
                print("Aggiunta colonna 'unit_of_measure' a 'kpis'.")
            except sqlite3.OperationalError:
                pass # Column might already exist
        conn.commit()
        print(f"Setup tabelle in {DB_KPIS} completato.")

    # --- DB_KPI_TEMPLATES Setup (Nuovo Database per i template) ---
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
            """CREATE TABLE IF NOT EXISTS template_defined_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                indicator_name_in_template TEXT NOT NULL,
                default_description TEXT,
                default_calculation_type TEXT NOT NULL CHECK(default_calculation_type IN ('Incrementale', 'Media')),
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
        cursor.execute(
             """ CREATE TABLE IF NOT EXISTS annual_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, stabilimento_id INTEGER NOT NULL, kpi_id INTEGER NOT NULL,
                annual_target1 REAL NOT NULL DEFAULT 0, annual_target2 REAL NOT NULL DEFAULT 0,
                repartition_logic TEXT NOT NULL, /* Mese, Trimestre, Settimana, Anno */
                repartition_values TEXT NOT NULL, /* JSON: {"Gen": 10, ...} or {"Q1": 25,...} or {"2024-W01": 2, ...} or {} for Anno */
                distribution_profile TEXT NOT NULL DEFAULT 'annual_progressive', /* e.g. annual_progressive, monthly_sinusoidal, even_distribution, true_annual_sinusoidal etc. */
                profile_params TEXT, /* JSON for profile specific parameters, e.g. for events, sinusoidal params */
                FOREIGN KEY (kpi_id) REFERENCES kpis(id) ON DELETE CASCADE, /* Assicurati che esista kpis(id) o rimuovi FK se non garantito */
                UNIQUE(year, stabilimento_id, kpi_id))"""
        )
        # Check and add 'profile_params' if it doesn't exist
        cursor.execute("PRAGMA table_info(annual_targets)")
        target_columns = {col[1] for col in cursor.fetchall()}
        if "profile_params" not in target_columns:
            try:
                cursor.execute("ALTER TABLE annual_targets ADD COLUMN profile_params TEXT")
                print("Aggiunta colonna 'profile_params' a 'annual_targets'.")
            except sqlite3.OperationalError:
                cursor.execute("PRAGMA table_info(annual_targets)")
                if "profile_params" not in {col[1] for col in cursor.fetchall()}:
                    print("ERRORE: Impossibile aggiungere la colonna 'profile_params' a 'annual_targets'.")
                else:
                    print("Colonna 'profile_params' ora presente in 'annual_targets'.")

        if not {"annual_target1", "annual_target2", "distribution_profile", "repartition_logic", "repartition_values"}.issubset(target_columns):
            print("Tabella 'annual_targets' con schema obsoleto, tentativo di ricreazione...")
            cursor.execute("DROP TABLE IF EXISTS annual_targets") 
            cursor.execute(
                """ CREATE TABLE annual_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, stabilimento_id INTEGER NOT NULL, kpi_id INTEGER NOT NULL,
                    annual_target1 REAL NOT NULL DEFAULT 0, annual_target2 REAL NOT NULL DEFAULT 0,
                    repartition_logic TEXT NOT NULL,
                    repartition_values TEXT NOT NULL,
                    distribution_profile TEXT NOT NULL DEFAULT 'annual_progressive',
                    profile_params TEXT,
                    FOREIGN KEY (kpi_id) REFERENCES kpis(id) ON DELETE CASCADE,
                    UNIQUE(year, stabilimento_id, kpi_id))"""
            )
            print("Tabella 'annual_targets' ricreata con nuovo schema.")
        conn.commit()
        print(f"Setup tabelle in {DB_TARGETS} completato.")


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
            # Ensure FOREIGN KEY kpi_id references kpis(id) ON DELETE CASCADE
            # This requires kpis table to be in the same database or handled carefully.
            # For simplicity with separate DBs, direct FK might not be strictly enforced by SQLite across files.
            # The cascade delete for targets is handled when kpi_spec is deleted via delete_kpi_indicator.
            cursor.execute(
                f""" CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    stabilimento_id INTEGER NOT NULL,
                    kpi_id INTEGER NOT NULL, 
                    target_number INTEGER NOT NULL CHECK(target_number IN (1, 2)),
                    {period_col_def.replace(' UNIQUE', '')},
                    target_value REAL NOT NULL,
                    UNIQUE(year, stabilimento_id, kpi_id, target_number, {period_col_name_for_unique})
                )"""
            )
            conn.commit()
        print(f"Setup tabella '{table_name}' in {db_path} completato.")
    print("Controllo e setup database completato.")


def add_kpi_group(name):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute("INSERT INTO kpi_groups (name) VALUES (?)", (name,))
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite3.IntegrityError:
            print(f"Gruppo '{name}' già esistente.")
            raise

def get_kpi_groups():
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_groups ORDER BY name").fetchall()

def update_kpi_group(group_id, new_name):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute("UPDATE kpi_groups SET name = ? WHERE id = ?", (new_name, group_id))
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento del gruppo: Nome '{new_name}' potrebbe già esistere.")
            raise e

def delete_kpi_group(group_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute("DELETE FROM kpi_groups WHERE id = ?", (group_id,)) # Cascades to subgroups
        conn.commit()

# --- Funzioni per la gestione dei Template KPI ---

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


def add_kpi(indicator_id, description, calculation_type, unit_of_measure, visible):
    with sqlite3.connect(DB_KPIS) as conn:  # Connection 'conn' is established here
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpis (indicator_id,description,calculation_type,unit_of_measure,visible) VALUES (?,?,?,?,?)",
                (indicator_id, description, calculation_type, unit_of_measure, visible),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            # Check if the error is specifically about the UNIQUE constraint on indicator_id
            if "UNIQUE constraint failed: kpis.indicator_id" in str(e):
                print(
                    f"KPI Spec for indicator_id {indicator_id} already exists. Attempting to update."
                )
                try:
                    # Get the kpis.id (spec_id) for this indicator_id using the current connection
                    cursor_select = conn.cursor()
                    existing_kpi_row = cursor_select.execute(
                        "SELECT id FROM kpis WHERE indicator_id=?", (indicator_id,)
                    ).fetchone()
                    if existing_kpi_row:
                        existing_kpi_id = existing_kpi_row[
                            0
                        ]  # This is kpis.id (the spec ID)

                        # Perform the update using the current 'conn'
                        cursor_update = conn.cursor()
                        cursor_update.execute(
                            "UPDATE kpis SET description=?, calculation_type=?, unit_of_measure=?, visible=? WHERE id=?",
                            (
                                description,
                                calculation_type,
                                unit_of_measure,
                                visible,
                                existing_kpi_id,
                            ),
                        )
                        conn.commit()  # Commit the update
                        print(
                            f"Successfully updated existing KPI Spec ID {existing_kpi_id} for indicator_id {indicator_id}."
                        )
                        return existing_kpi_id  # Return the ID of the updated spec
                    else:
                        # This case is unlikely if the IntegrityError was due to kpis.indicator_id constraint
                        print(
                            f"IntegrityError for indicator_id {indicator_id}, but could not find existing kpi_spec to update."
                        )
                        raise e  # Re-raise original error
                except Exception as update_e:
                    print(
                        f"Error during attempt to update existing KPI spec for indicator_id {indicator_id}: {update_e}"
                    )
                    # Rollback any changes within this specific transaction if an error occurs during update attempt.
                    # The 'with' statement handles rollback on unhandled exceptions at its level.
                    raise update_e  # Re-raise the error encountered during update
            else:
                # Some other integrity error not related to the UNIQUE indicator_id constraint
                raise e


def get_kpi_indicator_templates():
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_indicator_templates ORDER BY name").fetchall()

def get_kpi_indicator_template_by_id(template_id):
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_indicator_templates WHERE id = ?", (template_id,)).fetchone()

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
    # Subgroups linked will have indicator_template_id set to NULL due to ON DELETE SET NULL.
    # Defined indicators in template_defined_indicators will be deleted due to ON DELETE CASCADE.
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.execute("DELETE FROM kpi_indicator_templates WHERE id = ?", (template_id,))
        conn.commit()
    # Note: This does not automatically remove indicators from subgroups that were using this template.
    # That would require iterating through linked subgroups and removing indicators if desired.
    # The current behavior is to unlink them.

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
            definition_details["id"] = cursor.lastrowid # Store ID for propagation
        except sqlite3.IntegrityError:
            print(f"Definizione indicatore '{indicator_name}' già esistente nel template ID {template_id}.")
            # If it already exists, we might want to trigger an update propagation
            existing_def = get_template_indicator_definition_by_name(template_id, indicator_name)
            if existing_def:
                definition_details["id"] = existing_def["id"] # Use existing ID
                # Update the existing definition if values differ - or rely on a separate update function
                update_indicator_definition_in_template(
                    existing_def["id"],
                    indicator_name, # name usually not changed here, but other defaults
                    calc_type,
                    unit,
                    visible,
                    description
                ) # This will trigger its own propagation
            else:
                raise # Should not happen if integrity error was due to this
            return # Exit after handling existing or re-raising

    # Propagate addition to linked subgroups
    _propagate_template_indicator_change(template_id, definition_details, "add_or_update")


def get_template_defined_indicators(template_id):
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM template_defined_indicators WHERE template_id = ? ORDER BY indicator_name_in_template",
            (template_id,)
        ).fetchall()

def get_template_indicator_definition_by_name(template_id, indicator_name):
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM template_defined_indicators WHERE template_id = ? AND indicator_name_in_template = ?",
            (template_id, indicator_name)
        ).fetchone()

def get_template_indicator_definition_by_id(definition_id):
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM template_defined_indicators WHERE id = ?",
            (definition_id,)
        ).fetchone()


def update_indicator_definition_in_template(definition_id, indicator_name, calc_type, unit, visible, description):
    # Here, indicator_name changing is complex. Assume for now it means the conceptual indicator might change.
    # If indicator_name_in_template changes, it's safer to treat as remove old + add new.
    # For this function, let's assume indicator_name_in_template does NOT change, or if it does, the propagation
    # might need to find by ID and then update name.
    # For now, if name changes, it might create a new one if not handled carefully.
    
    current_def = get_template_indicator_definition_by_id(definition_id)
    if not current_def:
        print(f"Definizione indicatore con ID {definition_id} non trovata.")
        return

    # If name changes, it's a bit more complex for propagation.
    # The _propagate_template_indicator_change function will handle finding/creating by new name.
    # If the old name needs to be explicitly removed, that's an extra step.
    # For now, we assume _propagate finds by new name, and if old name items are orphaned, they are not auto-deleted by this update.
    # A more robust solution for name change is remove_old_definition -> add_new_definition

    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.execute(
            """UPDATE template_defined_indicators SET
               indicator_name_in_template = ?, default_description = ?, default_calculation_type = ?,
               default_unit_of_measure = ?, default_visible = ?
               WHERE id = ?""",
            (indicator_name, description, calc_type, unit, visible, definition_id)
        )
        conn.commit()

    updated_definition_details = {
        "id": definition_id,
        "template_id": current_def["template_id"], # Get template_id from current_def
        "indicator_name_in_template": indicator_name,
        "default_description": description,
        "default_calculation_type": calc_type,
        "default_unit_of_measure": unit,
        "default_visible": visible,
    }
    _propagate_template_indicator_change(current_def["template_id"], updated_definition_details, "add_or_update")
    # If indicator_name_in_template changed, we might need to remove indicators matching current_def['indicator_name_in_template']
    # if they are not the same as `indicator_name`. This is complex.
    # For now, this will update or create based on the *new* name.


def remove_indicator_definition_from_template(definition_id):
    # Get definition details BEFORE deleting, to know the name for propagation
    definition_to_delete = get_template_indicator_definition_by_id(definition_id)
    if not definition_to_delete:
        print(f"Definizione indicatore con ID {definition_id} non trovata per la rimozione.")
        return

    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.execute("DELETE FROM template_defined_indicators WHERE id = ?", (definition_id,))
        conn.commit()
    
    _propagate_template_indicator_change(definition_to_delete["template_id"], definition_to_delete, "remove")


def _propagate_template_indicator_change(template_id, indicator_definition, action):
    """
    Propagates changes from a template's indicator definition to all linked subgroups.
    Action can be 'add_or_update' or 'remove'.
    indicator_definition is a dictionary-like object with the definition's details.
    """
    subgroups_to_update = []
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        subgroups_to_update = conn_kpis.execute(
            "SELECT id FROM kpi_subgroups WHERE indicator_template_id = ?", (template_id,)
        ).fetchall()

    for sg_row in subgroups_to_update:
        subgroup_id = sg_row["id"]
        indicator_name = indicator_definition["indicator_name_in_template"]

        with sqlite3.connect(DB_KPIS) as conn_kpis_action: # New connection for actions
            conn_kpis_action.row_factory = sqlite3.Row
            # Find existing indicator in this subgroup by name
            existing_indicator = conn_kpis_action.execute(
                "SELECT id FROM kpi_indicators WHERE name = ? AND subgroup_id = ?",
                (indicator_name, subgroup_id)
            ).fetchone()

            if action == "add_or_update":
                actual_indicator_id = None
                if not existing_indicator:
                    try:
                        cursor_add_ind = conn_kpis_action.cursor()
                        cursor_add_ind.execute(
                            "INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)",
                            (indicator_name, subgroup_id)
                        )
                        actual_indicator_id = cursor_add_ind.lastrowid
                        conn_kpis_action.commit() # Commit insert indicator
                        print(f"Propagated: Added indicator '{indicator_name}' to subgroup ID {subgroup_id}.")
                    except sqlite3.IntegrityError: # Should be caught by 'if not existing_indicator'
                        existing_indicator = conn_kpis_action.execute( # Re-fetch just in case of race, unlikely here
                            "SELECT id FROM kpi_indicators WHERE name = ? AND subgroup_id = ?",
                            (indicator_name, subgroup_id)
                        ).fetchone()
                        if existing_indicator: actual_indicator_id = existing_indicator["id"]
                        else: 
                            print(f"Error propagating add for '{indicator_name}' to subgroup {subgroup_id}: Could not create or find.")
                            continue # Skip this subgroup
                else:
                    actual_indicator_id = existing_indicator["id"]

                if actual_indicator_id:
                    # Now ensure KPI spec exists and is updated
                    kpi_spec = conn_kpis_action.execute(
                        "SELECT id FROM kpis WHERE indicator_id = ?", (actual_indicator_id,)
                    ).fetchone()
                    
                    desc = indicator_definition["default_description"]
                    calc = indicator_definition["default_calculation_type"]
                    unit = indicator_definition["default_unit_of_measure"]
                    vis = bool(indicator_definition["default_visible"])

                    if not kpi_spec:
                        try:
                            conn_kpis_action.execute(
                                """INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible)
                                   VALUES (?,?,?,?,?)""",
                                (actual_indicator_id, desc, calc, unit, vis)
                            )
                            conn_kpis_action.commit() # Commit insert kpi spec
                            print(f"Propagated: Added KPI spec for indicator ID {actual_indicator_id} ('{indicator_name}') in subgroup ID {subgroup_id}.")
                        except sqlite3.IntegrityError as e_add_kpi: # Should not happen if kpi_spec was None
                             print(f"Error adding KPI spec for IndID {actual_indicator_id} in SG {subgroup_id}: {e_add_kpi}")
                    else: # KPI spec exists, update it
                        conn_kpis_action.execute(
                            """UPDATE kpis SET description=?, calculation_type=?, unit_of_measure=?, visible=?
                               WHERE id=?""",
                            (desc, calc, unit, vis, kpi_spec["id"])
                        )
                        conn_kpis_action.commit() # Commit update kpi spec
                        print(f"Propagated: Updated KPI spec for indicator ID {actual_indicator_id} ('{indicator_name}') in subgroup ID {subgroup_id}.")

            elif action == "remove":
                if existing_indicator:
                    # delete_kpi_indicator handles deleting the kpi spec and targets via cascades
                    # Need to call it with its own connection context if it manages its own.
                    # For simplicity here, assuming we can execute delete directly.
                    # WARNING: delete_kpi_indicator opens its own connections. Calling it repeatedly in a loop might be inefficient.
                    # It's better to perform the direct deletions here.
                    indicator_id_to_delete = existing_indicator["id"]
                    
                    # 1. Get kpi_spec_id for this indicator_id
                    kpi_spec_id_row = conn_kpis_action.execute("SELECT id FROM kpis WHERE indicator_id = ?", (indicator_id_to_delete,)).fetchone()
                    
                    if kpi_spec_id_row:
                        kpi_spec_id_val = kpi_spec_id_row["id"]
                        # 2. Delete from annual_targets
                        with sqlite3.connect(DB_TARGETS) as conn_targets_del:
                            conn_targets_del.execute("DELETE FROM annual_targets WHERE kpi_id = ?", (kpi_spec_id_val,))
                            conn_targets_del.commit()
                        # 3. Delete from periodic targets
                        periodic_dbs_info_del = [
                            (DB_KPI_DAYS, "daily_targets"), (DB_KPI_WEEKS, "weekly_targets"),
                            (DB_KPI_MONTHS, "monthly_targets"), (DB_KPI_QUARTERS, "quarterly_targets"),
                        ]
                        for db_path_del, table_name_del in periodic_dbs_info_del:
                            with sqlite3.connect(db_path_del) as conn_periodic_del:
                                conn_periodic_del.execute(f"DELETE FROM {table_name_del} WHERE kpi_id = ?", (kpi_spec_id_val,))
                                conn_periodic_del.commit()
                    
                    # 4. Delete from kpis (will be cascaded from kpi_indicators)
                    # 5. Delete from kpi_indicators
                    conn_kpis_action.execute("DELETE FROM kpi_indicators WHERE id = ?", (indicator_id_to_delete,))
                    conn_kpis_action.commit() # Commit delete indicator (cascades to kpis spec)
                    print(f"Propagated: Removed indicator '{indicator_name}' (ID: {indicator_id_to_delete}) and its data from subgroup ID {subgroup_id}.")
                else:
                    print(f"Propagate remove: Indicator '{indicator_name}' not found in subgroup ID {subgroup_id}, no action taken.")


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
            raise # Re-raise the exception

    if subgroup_id and indicator_template_id:
        # Apply template indicators
        template_indicators = get_template_defined_indicators(indicator_template_id)
        for ind_def in template_indicators:
            # This will use the same logic as propagation (add or update)
            _propagate_template_indicator_change(indicator_template_id, ind_def, "add_or_update")
            # The above might be slightly off as _propagate iterates all subgroups.
            # More direct approach for NEW subgroup:
            # try:
            #     indicator_id = add_kpi_indicator(ind_def["indicator_name_in_template"], subgroup_id) # This needs its own conn
            #     # Check if add_kpi_indicator returns ID or raises. Assume it returns ID.
            #     if indicator_id:
            #          add_kpi( # This also needs its own conn
            #              indicator_id,
            #              ind_def["default_description"],
            #              ind_def["default_calculation_type"],
            #              ind_def["default_unit_of_measure"],
            #              bool(ind_def["default_visible"])
            #          )
            # except sqlite3.IntegrityError:
            #     print(f"Indicatore '{ind_def['indicator_name_in_template']}' già presente nel nuovo sottogruppo {subgroup_id} durante applicazione template.")
            # except Exception as e:
            #     print(f"Errore applicando indicatore template '{ind_def['indicator_name_in_template']}' a sottogruppo {subgroup_id}: {e}")
            # The _synchronize_subgroup_with_template_indicator would be better here.

            # Using a refined direct application for a new subgroup:
            _apply_template_indicator_to_new_subgroup(subgroup_id, ind_def)
    return subgroup_id


def _apply_template_indicator_to_new_subgroup(subgroup_id, indicator_definition):
    """
    Directly applies a single indicator definition to a newly created subgroup.
    This avoids iterating all subgroups as _propagate_template_indicator_change does.
    """
    indicator_name = indicator_definition["indicator_name_in_template"]
    desc = indicator_definition["default_description"]
    calc = indicator_definition["default_calculation_type"]
    unit = indicator_definition["default_unit_of_measure"]
    vis = bool(indicator_definition["default_visible"])

    try:
        # Connect to DB_KPIS to add indicator and kpi spec
        with sqlite3.connect(DB_KPIS) as conn_apply:
            # Add KPI Indicator
            cursor_ind = conn_apply.cursor()
            try:
                cursor_ind.execute(
                    "INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)",
                    (indicator_name, subgroup_id)
                )
                actual_indicator_id = cursor_ind.lastrowid
            except sqlite3.IntegrityError: # Should ideally not happen for a brand new subgroup
                print(f"Warning: Indicator '{indicator_name}' already exists in new subgroup {subgroup_id} during template application.")
                existing_ind_row = conn_apply.execute("SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?", (indicator_name, subgroup_id)).fetchone()
                if not existing_ind_row: return # Failed to create or find
                actual_indicator_id = existing_ind_row[0]
            
            # Add KPI Specification
            if actual_indicator_id:
                try:
                    conn_apply.execute(
                        "INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible) VALUES (?,?,?,?,?)",
                        (actual_indicator_id, desc, calc, unit, vis)
                    )
                except sqlite3.IntegrityError: # KPI spec for this indicator_id already exists
                    print(f"Warning: KPI spec for indicator '{indicator_name}' (ID: {actual_indicator_id}) already exists in new subgroup {subgroup_id}.")
                    # Optionally, update it if it exists
                    conn_apply.execute(
                         "UPDATE kpis SET description=?, calculation_type=?, unit_of_measure=?, visible=? WHERE indicator_id=?",
                         (desc, calc, unit, vis, actual_indicator_id) # Assuming UNIQUE(indicator_id)
                    )
            conn_apply.commit()
            # print(f"Template Applied: Indicator '{indicator_name}' and its KPI spec to new subgroup ID {subgroup_id}.")

    except Exception as e:
        print(f"Error applying template indicator '{indicator_name}' to new subgroup {subgroup_id}: {e}")


def get_kpi_subgroups_by_group(group_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT sg.*, t.name as template_name FROM kpi_subgroups sg LEFT JOIN kpi_indicator_templates t ON sg.indicator_template_id = t.id WHERE sg.group_id = ? ORDER BY sg.name", (group_id,) # Connect to DB_KPI_TEMPLATES for name
        ).fetchall() # This will fail as kpi_indicator_templates is in a different DB file.

def get_kpi_subgroups_by_group_revised(group_id):
    subgroups = []
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        subgroups_raw = conn_kpis.execute(
            "SELECT * FROM kpi_subgroups WHERE group_id = ? ORDER BY name", (group_id,)
        ).fetchall()

    templates_info = {}
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn_templates:
        conn_templates.row_factory = sqlite3.Row
        all_templates = conn_templates.execute("SELECT id, name FROM kpi_indicator_templates").fetchall()
        for t in all_templates:
            templates_info[t["id"]] = t["name"]
            
    for sg_raw in subgroups_raw:
        sg_dict = dict(sg_raw) # Convert Row to dict
        sg_dict["template_name"] = templates_info.get(sg_raw["indicator_template_id"])
        subgroups.append(sg_dict)
    return subgroups


def update_kpi_subgroup(subgroup_id, new_name, group_id, new_template_id=None): # group_id might not be needed if not changing group
    # If template_id changes, existing indicators managed by the old template are NOT automatically removed by this function.
    # And new ones from the new_template_id are NOT automatically added.
    # This would require more complex logic (unlink old, apply new).
    # For now, this just updates the link. User must manage indicator changes separately if template changes.
    # Or, we can add logic here.
    
    current_subgroup_info = None
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        current_subgroup_info = conn.execute("SELECT indicator_template_id FROM kpi_subgroups WHERE id = ?", (subgroup_id,)).fetchone()

    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute("UPDATE kpi_subgroups SET name = ?, group_id = ?, indicator_template_id = ? WHERE id = ?", (new_name, group_id, new_template_id, subgroup_id))
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento del sottogruppo: Nome '{new_name}' potrebbe già esistere in questo gruppo.")
            raise e

    if new_template_id is not None and (current_subgroup_info is None or current_subgroup_info["indicator_template_id"] != new_template_id):
        print(f"Sottogruppo {subgroup_id} collegato al nuovo template {new_template_id}. Riapplicazione degli indicatori...")
        # 1. Get all indicators from the NEW template
        new_template_indicators = get_template_defined_indicators(new_template_id)
        
        # (Optional but recommended for clean switch: Remove indicators that were part of an OLD template and NOT in the NEW template)
        # This part is complex: needs to identify indicators from old template.
        # For simplicity now: just add/update based on the new template. User might end up with extra indicators if old template had different ones.

        for ind_def in new_template_indicators:
            _apply_template_indicator_to_new_subgroup(subgroup_id, ind_def) # Re-uses logic to ensure indicators are present/updated
        print(f"Indicatori del template {new_template_id} applicati/aggiornati per il sottogruppo {subgroup_id}.")


def delete_kpi_subgroup(subgroup_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute("DELETE FROM kpi_subgroups WHERE id = ?", (subgroup_id,)) # Cascades to indicators
        conn.commit()

def add_kpi_indicator(name, subgroup_id):
    # This function is called by template propagation. It should return the ID.
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
            # If it already exists, fetch its ID and return it, so propagation can update the KPI spec.
            # print(f"Indicatore '{name}' già esistente in questo sottogruppo. Non aggiunto di nuovo.")
            existing_id = conn.execute("SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?", (name, subgroup_id)).fetchone()
            if existing_id:
                return existing_id[0]
            raise # Should not happen if IntegrityError was for this.

def get_kpi_indicators_by_subgroup(subgroup_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM kpi_indicators WHERE subgroup_id = ? ORDER BY name",
            (subgroup_id,),
        ).fetchall()

def update_kpi_indicator(indicator_id, new_name, subgroup_id): # subgroup_id might not be needed
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute("UPDATE kpi_indicators SET name = ?, subgroup_id = ? WHERE id = ?", (new_name, subgroup_id, indicator_id))
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento dell'indicatore: Nome '{new_name}' potrebbe già esistere in questo sottogruppo.")
            raise e

def delete_kpi_indicator(indicator_id):
    kpi_spec_id_to_delete = None
    with sqlite3.connect(DB_KPIS) as conn_kpis_read: # Separate read connection
        kpi_spec_row = conn_kpis_read.execute("SELECT id FROM kpis WHERE indicator_id = ?", (indicator_id,)).fetchone()
        if kpi_spec_row:
            kpi_spec_id_to_delete = kpi_spec_row[0]

    if kpi_spec_id_to_delete:
        print(f"Eliminazione target associati a kpi_spec_id: {kpi_spec_id_to_delete} (da indicatore {indicator_id})")
        with sqlite3.connect(DB_TARGETS) as conn_targets:
            conn_targets.execute("DELETE FROM annual_targets WHERE kpi_id = ?", (kpi_spec_id_to_delete,))
            conn_targets.commit()

        periodic_dbs_info = [
            (DB_KPI_DAYS, "daily_targets"), (DB_KPI_WEEKS, "weekly_targets"),
            (DB_KPI_MONTHS, "monthly_targets"), (DB_KPI_QUARTERS, "quarterly_targets"),
        ]
        for db_path_del, table_name_del in periodic_dbs_info:
            with sqlite3.connect(db_path_del) as conn_periodic:
                conn_periodic.execute(f"DELETE FROM {table_name_del} WHERE kpi_id = ?", (kpi_spec_id_to_delete,))
                conn_periodic.commit()
    
    # Deletes kpis spec via cascade FROM kpi_indicators when indicator is deleted
    with sqlite3.connect(DB_KPIS) as conn: 
        conn.execute("PRAGMA foreign_keys = ON;") # Ensure cascade delete is active for this connection
        conn.execute("DELETE FROM kpi_indicators WHERE id = ?", (indicator_id,))
        conn.commit()


def get_kpis(only_visible=False):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        query = """SELECT k.id, g.name as group_name, sg.name as subgroup_name, i.name as indicator_name,
                          k.indicator_id, k.description, k.calculation_type, k.unit_of_measure, k.visible
                   FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id
                   JOIN kpi_subgroups sg ON i.subgroup_id = sg.id JOIN kpi_groups g ON sg.group_id = g.id """
        if only_visible:
            query += " WHERE k.visible = 1"
        query += " ORDER BY g.name, sg.name, i.name"
        return conn.execute(query).fetchall()


def add_kpi(indicator_id, description, calculation_type, unit_of_measure, visible):
    # Called by template propagation. Needs to handle if KPI spec already exists (UNIQUE constraint on indicator_id).
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpis (indicator_id,description,calculation_type,unit_of_measure,visible) VALUES (?,?,?,?,?)",
                (indicator_id, description, calculation_type, unit_of_measure, visible),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e: # Likely UNIQUE constraint on indicator_id
            # print(f"KPI Spec per indicator_id {indicator_id} già esistente. Non aggiunto di nuovo.")
            existing_kpi_id = conn.execute("SELECT id FROM kpis WHERE indicator_id=?", (indicator_id,)).fetchone()
            if existing_kpi_id:
                # If it exists, update it as per template propagation logic
                update_kpi(existing_kpi_id[0], indicator_id, description, calculation_type, unit_of_measure, visible)
                return existing_kpi_id[0]
            raise e


def update_kpi(
    kpi_id, indicator_id, description, calculation_type, unit_of_measure, visible
):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute(
                "UPDATE kpis SET indicator_id=?,description=?,calculation_type=?,unit_of_measure=?,visible=? WHERE id=?",
                (
                    indicator_id,
                    description,
                    calculation_type,
                    unit_of_measure,
                    visible,
                    kpi_id,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as e: # indicator_id might clash if changed to an existing one
            raise e

def get_kpi_by_id(kpi_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        query = """SELECT k.id, g.name as group_name, sg.name as subgroup_name, i.name as indicator_name,
                          i.id as actual_indicator_id, k.indicator_id, k.description, k.calculation_type, k.unit_of_measure, k.visible
                   FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id
                   JOIN kpi_subgroups sg ON i.subgroup_id = sg.id JOIN kpi_groups g ON sg.group_id = g.id
                   WHERE k.id = ?""" # Ensure k.indicator_id is selected, actual_indicator_id refers to i.id
        kpi_info = conn.execute(query, (kpi_id,)).fetchone()
        
        # Add template info if subgroup is templated
        if kpi_info:
            kpi_dict = dict(kpi_info)
            subgroup_details_query = """
                SELECT sg.indicator_template_id, t.name as template_name
                FROM kpi_subgroups sg
                LEFT JOIN kpi_indicator_templates t ON sg.indicator_template_id = t.id
                WHERE sg.name = ? AND sg.group_id = (SELECT id FROM kpi_groups WHERE name = ?)
            """ # This is tricky because kpi_indicator_templates is in another DB.
            # We'd need to fetch group_id and subgroup_id first to query template link.
            # Simpler: just get template_id from subgroup if available.
            
            # This part for template name might need adjustment if DBs are separate
            # For now, let's assume get_kpi_subgroups_by_group_revised structure or similar can provide it if needed elsewhere
            # Here, we only have kpi_id.
            
            # Fetch subgroup_id from the kpi_info
            # indicator_id_from_kpi = kpi_info['indicator_id'] (this is i.id)
            actual_indicator_id = kpi_info['actual_indicator_id'] # This should be i.id from the query
            
            sg_info_q = conn.execute("""
                SELECT sg.indicator_template_id
                FROM kpi_subgroups sg
                JOIN kpi_indicators i ON sg.id = i.subgroup_id
                WHERE i.id = ?
            """, (actual_indicator_id,)).fetchone()

            if sg_info_q and sg_info_q['indicator_template_id']:
                kpi_dict['indicator_template_id'] = sg_info_q['indicator_template_id']
                # Get template name from DB_KPI_TEMPLATES
                with sqlite3.connect(DB_KPI_TEMPLATES) as conn_tpl:
                    conn_tpl.row_factory = sqlite3.Row
                    tpl_name_row = conn_tpl.execute("SELECT name FROM kpi_indicator_templates WHERE id = ?", (sg_info_q['indicator_template_id'],)).fetchone()
                    if tpl_name_row:
                        kpi_dict['template_name'] = tpl_name_row['name']
            return kpi_dict
    return None


# ... (rest of the Stabilimenti, Annual Targets, Calculations, and Repartition functions remain unchanged)
# I will skip pasting the unchanged middle part for brevity, but it's assumed to be here.
# Make sure to re-insert the following functions:
# get_stabilimenti, add_stabilimento, update_stabilimento,
# get_annual_target, save_annual_targets,
# calculate_and_save_all_repartitions, get_ripartiti_data

def get_stabilimenti(only_visible=False):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        conn.row_factory = sqlite3.Row
        query = (
            "SELECT * FROM stabilimenti"
            + (" WHERE visible = 1" if only_visible else "")
            + " ORDER BY name"
        )
        return conn.execute(query).fetchall()


def add_stabilimento(name, visible):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        try:
            conn.execute(
                "INSERT INTO stabilimenti (name,visible) VALUES (?,?)", (name, visible)
            )
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite3.IntegrityError as e:
            raise e


def update_stabilimento(stabilimento_id, name, visible):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        try:
            conn.execute(
                "UPDATE stabilimenti SET name=?,visible=? WHERE id=?",
                (name, visible, stabilimento_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise e


def get_annual_target(year, stabilimento_id, kpi_id):
    with sqlite3.connect(DB_TARGETS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM annual_targets WHERE year=? AND stabilimento_id=? AND kpi_id=?",
            (year, stabilimento_id, kpi_id),
        ).fetchone()


def save_annual_targets(year, stabilimento_id, targets_data):
    if not targets_data:
        print("Nessun dato target da salvare.")
        return

    with sqlite3.connect(DB_TARGETS) as conn:
        cursor = conn.cursor()
        for kpi_id, data in targets_data.items():
            # Ensure kpi_id is an integer
            try:
                current_kpi_id = int(kpi_id)
            except ValueError:
                print(f"Skipping invalid kpi_id: {kpi_id}")
                continue

            record = get_annual_target(year, stabilimento_id, current_kpi_id) # kpi_id must be int
            repartition_values_json = json.dumps(data.get("repartition_values", {}))
            distribution_profile = data.get("distribution_profile", "annual_progressive")
            profile_params_json = json.dumps(data.get("profile_params", {})) 
            annual_target1 = float(data.get("annual_target1", 0.0) or 0.0)
            annual_target2 = float(data.get("annual_target2", 0.0) or 0.0)
            repartition_logic = data.get("repartition_logic", "Anno") 

            if record:
                cursor.execute(
                    """UPDATE annual_targets SET annual_target1=?, annual_target2=?, repartition_logic=?,
                       repartition_values=?, distribution_profile=?, profile_params=? WHERE id=?""",
                    (
                        annual_target1,
                        annual_target2,
                        repartition_logic,
                        repartition_values_json,
                        distribution_profile,
                        profile_params_json,
                        record["id"],
                    ),
                )
            else:
                cursor.execute(
                    """INSERT INTO annual_targets (year,stabilimento_id,kpi_id,annual_target1,annual_target2,
                       repartition_logic,repartition_values,distribution_profile,profile_params) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        year,
                        stabilimento_id,
                        current_kpi_id, # Use int kpi_id
                        annual_target1,
                        annual_target2,
                        repartition_logic,
                        repartition_values_json,
                        distribution_profile,
                        profile_params_json,
                    ),
                )
        conn.commit()

    for kpi_id_saved_str in targets_data.keys():
        try:
            kpi_id_saved = int(kpi_id_saved_str)
            calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved, 1)
            calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved, 2)
        except ValueError:
            print(f"Skipping repartitions for invalid kpi_id during save: {kpi_id_saved_str}")
            continue


    try:
        print(f"Avvio rigenerazione completa dei file CSV globali in: {str(CSV_EXPORT_BASE_PATH)}")
        if hasattr(export_manager, 'export_all_data_to_global_csvs'):
            export_manager.export_all_data_to_global_csvs(str(CSV_EXPORT_BASE_PATH))
        else:
            print("Funzione export_manager.export_all_data_to_global_csvs non trovata.")
    except Exception as e:
        print(f"ERRORE CRITICO durante la generazione dei CSV globali: {e}")
        import traceback
        traceback.print_exc()


def calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id, target_number):
    target_info = get_annual_target(year, stabilimento_id, kpi_id)
    if not target_info:
        return
    kpi_details = get_kpi_by_id(kpi_id) # This now returns a dict or None
    if not kpi_details:
        print(f"Dettagli KPI ID {kpi_id} non trovati")
        return

    annual_target_to_use = (
        target_info["annual_target1"]
        if target_number == 1
        else target_info["annual_target2"]
    )
    if (
        annual_target_to_use is None or abs(annual_target_to_use) < 1e-9
    ):  
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
                    (year, stabilimento_id, kpi_id, target_number),
                )
                conn.commit()
        return

    user_repartition_logic = target_info[
        "repartition_logic"
    ]  
    user_repartition_values_str = target_info["repartition_values"]
    try:
        user_repartition_values = (
            json.loads(user_repartition_values_str)
            if user_repartition_values_str
            else {}
        )
    except json.JSONDecodeError:
        print(
            f"ATTENZIONE: Valori di ripartizione non validi per KPI {kpi_id}, Anno {year}, Stab {stabilimento_id}. Uso default (nessuna ripartizione utente)."
        )
        user_repartition_values = {}

    kpi_calc_type = kpi_details["calculation_type"] # kpi_details is now a dict
    distribution_profile = (
        target_info["distribution_profile"]
        if target_info["distribution_profile"]
        else "annual_progressive"
    )

    profile_params_str = (
        target_info["profile_params"]
        if "profile_params" in target_info # target_info is a Row object, access like a dict
        and target_info["profile_params"] is not None
        else "{}"
    )

    try:
        profile_params = json.loads(profile_params_str) if profile_params_str else {}
    except json.JSONDecodeError:
        print(
            f"ATTENZIONE: Parametri profilo non validi per KPI {kpi_id}. Uso default."
        )
        profile_params = {}

    dbs_to_clear_periodic = [
        (DB_KPI_DAYS, "daily_targets"),
        (DB_KPI_WEEKS, "weekly_targets"),
        (DB_KPI_MONTHS, "monthly_targets"),
        (DB_KPI_QUARTERS, "quarterly_targets"),
    ]
    for db_path, table_name in dbs_to_clear_periodic:
        with sqlite3.connect(db_path) as conn:
            conn.cursor().execute(
                f"DELETE FROM {table_name} WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                (year, stabilimento_id, kpi_id, target_number),
            )
            conn.commit()

    days_in_year = (datetime.date(year, 12, 31) - datetime.date(year, 1, 1)).days + 1
    all_dates_in_year = [datetime.date(year, 1, 1) + datetime.timedelta(days=i) for i in range(days_in_year)]
    raw_daily_values = np.zeros(days_in_year)
    period_allocations = {}

    if kpi_calc_type == "Incrementale":
        if user_repartition_logic == "Mese":
            proportions = [user_repartition_values.get(calendar.month_name[i+1], 0)/100.0 for i in range(12)]
            current_sum = sum(proportions)
            if abs(current_sum - 1.0) > 0.01 and current_sum > 1e-9: 
                proportions = [p / current_sum for p in proportions]
            elif current_sum < 1e-9: 
                proportions = [1.0/12.0] * 12
            for i in range(12): period_allocations[i] = annual_target_to_use * proportions[i]

        elif user_repartition_logic == "Trimestre":
            proportions = [user_repartition_values.get(f"Q{i+1}", 0)/100.0 for i in range(4)]
            current_sum = sum(proportions)
            if abs(current_sum - 1.0) > 0.01 and current_sum > 1e-9:
                proportions = [p / current_sum for p in proportions]
            elif current_sum < 1e-9:
                proportions = [1.0/4.0] * 4
            for i in range(4): period_allocations[i] = annual_target_to_use * proportions[i]

        elif user_repartition_logic == "Settimana":
            total_prop = sum(float(v)/100.0 for v in user_repartition_values.values() if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit())
            num_defined_weeks = len(user_repartition_values)

            if num_defined_weeks == 0: 
                num_iso_weeks_in_year = datetime.date(year, 12, 28).isocalendar()[1]
                default_prop = 1.0 / num_iso_weeks_in_year if num_iso_weeks_in_year > 0 else 0
                temp_period_targets = {}
                for d_val in all_dates_in_year: 
                    iso_y, iso_w, _ = d_val.isocalendar()
                    wk_key = f"{iso_y}-W{iso_w:02d}"
                    if wk_key not in temp_period_targets : temp_period_targets[wk_key] = 0
                for wk_key in temp_period_targets: 
                    period_allocations[wk_key] = annual_target_to_use * default_prop
            else:
                for week_str, prop_val_str in user_repartition_values.items():
                    try:
                        prop_val = float(prop_val_str) / 100.0
                        datetime.datetime.strptime(week_str + '-1', "%Y-W%W-%w") 
                        if abs(total_prop - 1.0) > 0.01 and total_prop > 1e-9: 
                            period_allocations[week_str] = annual_target_to_use * (prop_val / total_prop)
                        else: 
                            period_allocations[week_str] = annual_target_to_use * prop_val
                    except (ValueError, TypeError):
                        print(f"Attenzione: Formato settimana o valore non valido per '{week_str}': '{prop_val_str}', saltato.")
        
    elif kpi_calc_type == "Media": 
        if user_repartition_logic == "Mese":
            for i in range(12):
                period_allocations[i] = user_repartition_values.get(calendar.month_name[i+1], 100.0)/100.0
        elif user_repartition_logic == "Trimestre":
            q_map_indices = [[0,1,2], [3,4,5], [6,7,8], [9,10,11]]
            for q_idx in range(4):
                q_multiplier = user_repartition_values.get(f"Q{q_idx+1}", 100.0)/100.0
                for month_idx_in_year in q_map_indices[q_idx]:
                    period_allocations[month_idx_in_year] = q_multiplier 
        elif user_repartition_logic == "Settimana":
            for week_str, mult_val_str in user_repartition_values.items():
                try:
                    mult_val = float(mult_val_str) / 100.0
                    datetime.datetime.strptime(week_str + '-1', "%Y-W%W-%w")
                    period_allocations[week_str] = mult_val
                except (ValueError, TypeError):
                    print(f"Attenzione: Formato settimana o valore non valido per '{week_str}' in Media: '{mult_val_str}', saltato.")
       
    if kpi_calc_type == "Incrementale":
        if distribution_profile == "even_distribution":
            if user_repartition_logic == "Anno" or not period_allocations:
                daily_val = annual_target_to_use / days_in_year if days_in_year > 0 else 0
                raw_daily_values.fill(daily_val)
            else: 
                for d_idx, date_val in enumerate(all_dates_in_year):
                    target_sum_for_period = 0
                    days_in_current_period = 0
                    if user_repartition_logic == "Mese":
                        target_sum_for_period = period_allocations.get(date_val.month - 1, 0)
                        _, days_in_current_period = calendar.monthrange(year, date_val.month)
                    elif user_repartition_logic == "Trimestre":
                        q_idx = (date_val.month - 1) // 3
                        target_sum_for_period = period_allocations.get(q_idx, 0)
                        q_ranges = get_date_ranges_for_quarters(year)
                        q_start, q_end = q_ranges[(date_val.month-1)//3 + 1]
                        days_in_current_period = (q_end - q_start).days + 1
                    elif user_repartition_logic == "Settimana":
                        iso_y, iso_w, _ = date_val.isocalendar()
                        wk_key = f"{iso_y}-W{iso_w:02d}"
                        target_sum_for_period = period_allocations.get(wk_key, 0)
                        days_in_current_period = sum(1 for d in all_dates_in_year if d.isocalendar()[0]==iso_y and d.isocalendar()[1]==iso_w)

                    raw_daily_values[d_idx] = target_sum_for_period / days_in_current_period if days_in_current_period > 0 else 0

        elif distribution_profile == "annual_progressive":
            props = get_weighted_proportions(days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
            for i in range(days_in_year): raw_daily_values[i] = annual_target_to_use * props[i]

        elif distribution_profile == "true_annual_sinusoidal":
            # Use custom params if provided, else defaults
            amplitude = profile_params.get("sine_amplitude", SINE_AMPLITUDE_INCREMENTAL)
            phase = profile_params.get("sine_phase", SINE_PHASE_OFFSET)
            props = get_sinusoidal_proportions(days_in_year, amplitude, phase)
            for i in range(days_in_year): raw_daily_values[i] = annual_target_to_use * props[i]


        elif distribution_profile == "annual_progressive_weekday_bias":
            base_props = get_weighted_proportions(days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
            adj_props = np.array([base_props[i] * (WEEKDAY_BIAS_FACTOR_INCREMENTAL if all_dates_in_year[i].weekday() >= 5 else 1.0) for i in range(days_in_year)])
            current_sum = np.sum(adj_props)
            final_props = (adj_props / current_sum) if current_sum > 1e-9 else [1.0/days_in_year]*days_in_year
            for i in range(days_in_year): raw_daily_values[i] = annual_target_to_use * final_props[i]

        elif distribution_profile in ["monthly_sinusoidal", "legacy_intra_period_progressive", "quarterly_progressive", "quarterly_sinusoidal"]:
            if (user_repartition_logic == "Mese" or (user_repartition_logic == "Trimestre" and distribution_profile in ["monthly_sinusoidal", "legacy_intra_period_progressive"])) :
                monthly_target_sums_final = [0.0] * 12
                if user_repartition_logic == "Mese":
                    for m_idx in range(12): monthly_target_sums_final[m_idx] = period_allocations.get(m_idx,0)
                elif user_repartition_logic == "Trimestre": 
                    q_map = [[0,1,2], [3,4,5], [6,7,8], [9,10,11]]
                    for q_idx, months_in_q_indices in enumerate(q_map):
                        q_total = period_allocations.get(q_idx, 0)
                        num_m = len(months_in_q_indices)
                        month_weights = get_weighted_proportions(num_m, 1, 1) 
                        if distribution_profile == "legacy_intra_period_progressive": 
                            month_weights = get_weighted_proportions(num_m, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
                        for i, m_idx_year in enumerate(months_in_q_indices):
                            monthly_target_sums_final[m_idx_year] = q_total * month_weights[i]

                for month_idx, month_sum in enumerate(monthly_target_sums_final):
                    current_m = month_idx + 1
                    num_days_m = calendar.monthrange(year, current_m)[1]
                    if num_days_m == 0 or abs(month_sum) < 1e-9: continue

                    day_props_in_month = []
                    if distribution_profile == "monthly_sinusoidal":
                        day_props_in_month = get_parabolic_proportions(num_days_m, peak_at_center=True)
                    elif distribution_profile == "legacy_intra_period_progressive":
                        day_props_in_month = get_weighted_proportions(num_days_m, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
                    else: 
                        day_props_in_month = [1.0/num_days_m] * num_days_m

                    month_start_day_idx_of_year = (datetime.date(year, current_m, 1) - datetime.date(year,1,1)).days
                    for day_of_m_idx, prop in enumerate(day_props_in_month):
                        raw_daily_values[month_start_day_idx_of_year + day_of_m_idx] = month_sum * prop

            elif user_repartition_logic == "Trimestre" and distribution_profile in ["quarterly_progressive", "quarterly_sinusoidal"]:
                q_date_ranges = get_date_ranges_for_quarters(year)
                for q_idx in range(4): 
                    q_total = period_allocations.get(q_idx, 0)
                    if abs(q_total) < 1e-9: continue
                    q_start_date, q_end_date = q_date_ranges[q_idx+1]
                    num_days_q = (q_end_date - q_start_date).days + 1

                    day_props_in_q = []
                    if distribution_profile == "quarterly_progressive":
                        day_props_in_q = get_weighted_proportions(num_days_q, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
                    elif distribution_profile == "quarterly_sinusoidal":
                        day_props_in_q = get_parabolic_proportions(num_days_q, peak_at_center=True)

                    q_start_day_idx_of_year = (q_start_date - datetime.date(year,1,1)).days
                    for day_of_q_idx, prop in enumerate(day_props_in_q):
                        raw_daily_values[q_start_day_idx_of_year + day_of_q_idx] = q_total * prop
        else: 
            print(f"Profilo Incrementale '{distribution_profile}' non gestito specificamente con logica ripartizione '{user_repartition_logic}'. Uso annuale progressivo.")
            props = get_weighted_proportions(days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
            for i in range(days_in_year): raw_daily_values[i] = annual_target_to_use * props[i]

    elif kpi_calc_type == "Media":
        for d_idx, date_val in enumerate(all_dates_in_year):
            base_avg_for_day = annual_target_to_use 
            if user_repartition_logic == "Mese":
                base_avg_for_day = annual_target_to_use * period_allocations.get(date_val.month - 1, 1.0)
            elif user_repartition_logic == "Trimestre": 
                base_avg_for_day = annual_target_to_use * period_allocations.get(date_val.month - 1, 1.0)
            elif user_repartition_logic == "Settimana":
                iso_y, iso_w, _ = date_val.isocalendar()
                wk_key = f"{iso_y}-W{iso_w:02d}"
                base_avg_for_day = annual_target_to_use * period_allocations.get(wk_key, 1.0)

            if distribution_profile == "even_distribution":
                raw_daily_values[d_idx] = base_avg_for_day

            elif distribution_profile == "annual_progressive":
                factors = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year)
                effective_deviation = (factors[d_idx] - 1.0) 
                raw_daily_values[d_idx] = annual_target_to_use * (1 + effective_deviation * DEVIATION_SCALE_FACTOR_AVG)

            elif distribution_profile == "true_annual_sinusoidal":
                # Use custom params if provided, else defaults
                amplitude = profile_params.get("sine_amplitude", SINE_AMPLITUDE_MEDIA)
                phase = profile_params.get("sine_phase", SINE_PHASE_OFFSET)
                x = np.linspace(0, 2 * np.pi, days_in_year, endpoint=False)
                sine_modulation = amplitude * np.sin(x[d_idx] + phase) 
                raw_daily_values[d_idx] = annual_target_to_use * (1 + sine_modulation) 

            elif distribution_profile == "annual_progressive_weekday_bias":
                factors = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year)
                effective_deviation = (factors[d_idx] - 1.0)
                day_target = annual_target_to_use * (1 + effective_deviation * DEVIATION_SCALE_FACTOR_AVG)
                if date_val.weekday() >= 5: day_target *= WEEKDAY_BIAS_FACTOR_MEDIA
                raw_daily_values[d_idx] = day_target

            elif distribution_profile in ["monthly_sinusoidal", "legacy_intra_period_progressive", "quarterly_progressive", "quarterly_sinusoidal"]:
                num_days_in_mod_period = 0
                day_idx_in_mod_period = 0

                if distribution_profile == "monthly_sinusoidal" or distribution_profile == "legacy_intra_period_progressive":
                    num_days_in_mod_period = calendar.monthrange(year, date_val.month)[1]
                    day_idx_in_mod_period = date_val.day -1
                elif distribution_profile == "quarterly_progressive" or distribution_profile == "quarterly_sinusoidal":
                    q_idx_0based = (date_val.month - 1) // 3
                    q_ranges = get_date_ranges_for_quarters(year)
                    q_start, q_end = q_ranges[q_idx_0based + 1]
                    num_days_in_mod_period = (q_end - q_start).days + 1
                    day_idx_in_mod_period = (date_val - q_start).days

                if num_days_in_mod_period == 0:
                    raw_daily_values[d_idx] = base_avg_for_day; continue

                modulation_value = 0 
                if distribution_profile == "monthly_sinusoidal" or distribution_profile == "quarterly_sinusoidal":
                    par_weights = np.zeros(num_days_in_mod_period)
                    mid_idx = (num_days_in_mod_period -1)/2.0
                    for i in range(num_days_in_mod_period): par_weights[i] = (i-mid_idx)**2
                    par_weights = np.max(par_weights) - par_weights 

                    mean_w = np.mean(par_weights) if num_days_in_mod_period > 1 else par_weights[0]
                    norm_mod_factor = (par_weights[day_idx_in_mod_period] - mean_w)
                    max_abs_dev = np.max(np.abs(par_weights - mean_w))
                    if max_abs_dev > 1e-9: norm_mod_factor /= max_abs_dev 
                    modulation_value = norm_mod_factor * DEVIATION_SCALE_FACTOR_AVG

                elif distribution_profile == "legacy_intra_period_progressive" or distribution_profile == "quarterly_progressive":
                    factors_period = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, num_days_in_mod_period)
                    effective_deviation_period = (factors_period[day_idx_in_mod_period] - 1.0) 
                    modulation_value = effective_deviation_period * DEVIATION_SCALE_FACTOR_AVG

                raw_daily_values[d_idx] = base_avg_for_day * (1 + modulation_value)
            else: 
                print(f"Profilo Media '{distribution_profile}' non gestito. Uso valore base del periodo.")
                raw_daily_values[d_idx] = base_avg_for_day
    else:
        print(f"Tipo calcolo KPI sconosciuto: {kpi_calc_type}")
        return

    # Event-based adjustments (conceptual)
    event_data = profile_params.get("events", [])
    if event_data:
        temp_values_for_event_calc = np.copy(raw_daily_values) # Operate on a copy
        for event in event_data:
            try:
                start_event = datetime.datetime.strptime(event['start_date'], '%Y-%m-%d').date()
                end_event = datetime.datetime.strptime(event['end_date'], '%Y-%m-%d').date()
                multiplier = float(event.get('multiplier', 1.0))
                addition = float(event.get('addition', 0.0)) # For Media, addition might be direct; for Incremental, it's tricky post-normalization
                
                for d_idx_event, date_val_event in enumerate(all_dates_in_year):
                    if start_event <= date_val_event <= end_event:
                        if kpi_calc_type == "Media":
                             temp_values_for_event_calc[d_idx_event] = temp_values_for_event_calc[d_idx_event] * multiplier + addition
                        elif kpi_calc_type == "Incrementale":
                             temp_values_for_event_calc[d_idx_event] *= multiplier 
                             # Additions for incremental type need careful handling for total sum, often done pre-normalization or as a fixed amount ADDED to total annual target first
                             # For simplicity, direct additions to daily values for incremental are not typical post-distribution.
                             # If addition means adding a fixed quantity that gets distributed, it should modify 'annual_target_to_use' before distribution.
                             # If it's a value to add to specific days AFTER distribution, then re-normalization is a must.
            except (ValueError, KeyError) as e_event:
                print(f"Attenzione: Dati evento non validi, saltato. Dettagli: {event}, Errore: {e_event}")
        
        if kpi_calc_type == "Incrementale":
            current_total_after_events = np.sum(temp_values_for_event_calc)
            if abs(current_total_after_events) > 1e-9 and abs(annual_target_to_use) > 1e-9:
                raw_daily_values = (temp_values_for_event_calc / current_total_after_events) * annual_target_to_use
            elif abs(annual_target_to_use) < 1e-9 : 
                raw_daily_values.fill(0.0)
            # else: if current_total is zero but target is not, values remain as before events or as modified (could be all zero from multipliers)
            else: # if current_total_after_events is zero and annual_target_to_use is not, this is problematic.
                  # It means events zeroed out everything. Keep raw_daily_values as they were prior to this block if that's desired.
                  # Or, if events can make sum zero, and target is non-zero, then something is off.
                  # For now, if events made sum zero, and target isn't, they will stay zeroed from events.
                  raw_daily_values = temp_values_for_event_calc


        elif kpi_calc_type == "Media":
            raw_daily_values = temp_values_for_event_calc # Direct application for Media is usually fine


    daily_targets_values = [(all_dates_in_year[i], raw_daily_values[i]) for i in range(days_in_year)]

    if daily_targets_values:
        with sqlite3.connect(DB_KPI_DAYS) as conn:
            conn.executemany(
                "INSERT INTO daily_targets (year,stabilimento_id,kpi_id,target_number,date_value,target_value) VALUES (?,?,?,?,?,?)",
                [
                    (year, stabilimento_id, kpi_id, target_number, d.isoformat(), t)
                    for d, t in daily_targets_values
                ],
            )
            conn.commit()

    weekly_agg_data = {} 
    for date_val, daily_target_val in daily_targets_values:
        iso_year_calendar, iso_week_number, _ = date_val.isocalendar()
        week_key = f"{iso_year_calendar}-W{iso_week_number:02d}"
        if week_key not in weekly_agg_data:
            weekly_agg_data[week_key] = []
        weekly_agg_data[week_key].append(daily_target_val)

    db_week_recs = []
    sorted_week_keys = sorted(weekly_agg_data.keys(), key=lambda wk: (int(wk.split('-W')[0]), int(wk.split('-W')[1])))

    for wk in sorted_week_keys:
        tgts_in_wk = weekly_agg_data[wk]
        if not tgts_in_wk: continue 
        wt = (
            sum(tgts_in_wk)
            if kpi_calc_type == "Incrementale"
            else (sum(tgts_in_wk) / len(tgts_in_wk) if tgts_in_wk else 0)
        )
        db_week_recs.append((year, stabilimento_id, kpi_id, target_number, wk, wt))
    if db_week_recs:
        with sqlite3.connect(DB_KPI_WEEKS) as conn:
            conn.executemany(
                "INSERT INTO weekly_targets (year,stabilimento_id,kpi_id,target_number,week_value,target_value) VALUES (?,?,?,?,?,?)",
                db_week_recs,
            )
            conn.commit()

    monthly_agg_data = {i: [] for i in range(12)} 
    for date_val, daily_target_val in daily_targets_values:
        if date_val.year == year: 
            monthly_agg_data[date_val.month - 1].append(daily_target_val)

    db_month_recs = []
    for month_idx in range(12): 
        tgts_in_m = monthly_agg_data[month_idx]
        mn = calendar.month_name[month_idx + 1]
        mt = 0.0
        if tgts_in_m:
            mt = (
                sum(tgts_in_m)
                if kpi_calc_type == "Incrementale"
                else (sum(tgts_in_m) / len(tgts_in_m) if tgts_in_m else 0)
            )
        db_month_recs.append((year, stabilimento_id, kpi_id, target_number, mn, mt))
    if db_month_recs:
        with sqlite3.connect(DB_KPI_MONTHS) as conn:
            conn.executemany(
                "INSERT INTO monthly_targets (year,stabilimento_id,kpi_id,target_number,month_value,target_value) VALUES (?,?,?,?,?,?)",
                db_month_recs,
            )
            conn.commit()

    quarterly_agg_data = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
    actual_monthly_tgts_for_q_calc = {rec[4]: rec[5] for rec in db_month_recs} 

    month_to_q_map = { calendar.month_name[i]: f"Q{((i-1)//3)+1}" for i in range(1, 13) }
    for mn_name, mt_val in actual_monthly_tgts_for_q_calc.items():
        if mn_name in month_to_q_map: 
            quarterly_agg_data[month_to_q_map[mn_name]].append(mt_val)

    db_quarter_recs = []
    for qn in ["Q1", "Q2", "Q3", "Q4"]: 
        tgts_in_q = quarterly_agg_data[qn] 
        qt = 0.0
        if tgts_in_q: 
            qt = (
                sum(tgts_in_q) 
                if kpi_calc_type == "Incrementale"
                else (sum(tgts_in_q) / len(tgts_in_q) if tgts_in_q else 0) 
            )
        db_quarter_recs.append((year, stabilimento_id, kpi_id, target_number, qn, qt))
    if db_quarter_recs:
        with sqlite3.connect(DB_KPI_QUARTERS) as conn:
            conn.executemany(
                "INSERT INTO quarterly_targets (year,stabilimento_id,kpi_id,target_number,quarter_value,target_value) VALUES (?,?,?,?,?,?)",
                db_quarter_recs,
            )
            conn.commit()
    
    # kpi_details is a dict
    group_name_disp = kpi_details.get("group_name", "N/A") if kpi_details else "N/A"
    subgroup_name_disp = kpi_details.get("subgroup_name", "N/A") if kpi_details else "N/A"
    indicator_name_disp = kpi_details.get("indicator_name", "N/A") if kpi_details else "N/A"

    kpi_full_name_display = f"{group_name_disp}>{subgroup_name_disp}>{indicator_name_disp}"
    print(
        f"Ripartizioni per KPI '{kpi_full_name_display}' (ID:{kpi_id}), Target {target_number} "
        f"(Profilo: {distribution_profile}, Logica Rip.: {user_repartition_logic}) calcolate e salvate."
    )


def get_ripartiti_data(year, stabilimento_id, kpi_id, period_type, target_number):
    db_map = {
        "Giorno": (DB_KPI_DAYS, "daily_targets", "date_value"),
        "Settimana": (DB_KPI_WEEKS, "weekly_targets", "week_value"),
        "Mese": (DB_KPI_MONTHS, "monthly_targets", "month_value"),
        "Trimestre": (DB_KPI_QUARTERS, "quarterly_targets", "quarter_value"),
    }
    if period_type not in db_map:
        raise ValueError(f"Tipo periodo non valido: {period_type}")
    db_path, table_name, period_col_name = db_map[period_type]
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        order_clause = f"ORDER BY {period_col_name}" 
        if period_type == "Mese":
            month_order_cases = " ".join([f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1,13)])
            order_clause = f"ORDER BY CASE {period_col_name} {month_order_cases} END"
        elif period_type == "Trimestre":
            quarter_order_cases = " ".join([f"WHEN 'Q{i}' THEN {i}" for i in range(1,5)])
            order_clause = f"ORDER BY CASE {period_col_name} {quarter_order_cases} END"
        elif period_type == "Settimana": 
             order_clause = f"ORDER BY SUBSTR({period_col_name}, 1, 4), CAST(SUBSTR({period_col_name}, INSTR({period_col_name}, '-W') + 2) AS INTEGER)"


        query = (
            f"SELECT {period_col_name} AS Periodo, target_value AS Target FROM {table_name} "
            f"WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=? {order_clause}"
        )
        cursor.execute(query, (year, stabilimento_id, kpi_id, target_number))
        return cursor.fetchall()


if __name__ == "__main__":
    print("Esecuzione di database_manager.py come script principale (per setup/test).")
    setup_databases() # This will now also set up template tables and modify kpi_subgroups

    # --- Utility to add kpi/stabilimento for testing ---
    # (These _ensure functions may need adjustments if they directly use add_kpi_subgroup or add_kpi_indicator,
    # as those functions now might behave differently with templates or have slightly changed signatures/dependencies.)
    # For now, assuming they are basic helpers.
    def _ensure_kpi(conn_kpis_main_path_or_obj, group_name, subgroup_name, indicator_name, calc_type, unit, subgroup_template_id=None):
        is_path = isinstance(conn_kpis_main_path_or_obj, (str, Path))
        conn_kpis = sqlite3.connect(conn_kpis_main_path_or_obj) if is_path else conn_kpis_main_path_or_obj
        
        # We need to use the module's functions to ensure consistency with template logic if subgroup_template_id is used.
        # However, this _ensure_kpi is a low-level helper. For template testing, we'll use module functions directly.
        # This helper will just create manual KPIs if subgroup_template_id is None.
        
        created_kpi_id_final = None
        try:
            with conn_kpis: # Use context manager for auto-commit/rollback on this connection
                cursor = conn_kpis.cursor()
                cursor.execute("SELECT id FROM kpi_groups WHERE name=?", (group_name,))
                group = cursor.fetchone()
                if not group:
                    cursor.execute("INSERT INTO kpi_groups (name) VALUES (?)", (group_name,))
                    group_id = cursor.lastrowid
                else:
                    group_id = group[0]

                cursor.execute("SELECT id FROM kpi_subgroups WHERE name=? AND group_id=?", (subgroup_name, group_id))
                subgroup = cursor.fetchone()
                if not subgroup:
                    # If using this helper to create a subgroup that *should* be templated, this won't apply the template.
                    # This helper is for basic, non-templated KPI setup.
                    cursor.execute("INSERT INTO kpi_subgroups (name, group_id, indicator_template_id) VALUES (?,?,?)", 
                                   (subgroup_name, group_id, subgroup_template_id))
                    subgroup_id = cursor.lastrowid
                else:
                    subgroup_id = subgroup[0]
                    # If subgroup exists and we want to associate a template, it needs update_kpi_subgroup
                
                # If a template is applied to the subgroup, indicators might already exist.
                # This helper is more for ensuring a specific, manually defined indicator.
                if not subgroup_template_id: # Only add indicator manually if not relying on template for this specific call
                    cursor.execute("SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?", (indicator_name, subgroup_id))
                    indicator = cursor.fetchone()
                    indicator_id_to_use = None
                    if not indicator:
                        cursor.execute("INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)", (indicator_name, subgroup_id))
                        indicator_id_to_use = cursor.lastrowid
                    else:
                        indicator_id_to_use = indicator[0]

                    if indicator_id_to_use:
                        cursor.execute("SELECT id FROM kpis WHERE indicator_id=?", (indicator_id_to_use,))
                        kpi = cursor.fetchone()
                        if not kpi:
                            cursor.execute("INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible) VALUES (?,?,?,?,?)",
                                        (indicator_id_to_use, f"{indicator_name} ({calc_type})", calc_type, unit, True))
                            created_kpi_id_final = cursor.lastrowid
                        else:
                            created_kpi_id_final = kpi[0]
                            cursor.execute("UPDATE kpis SET calculation_type=?, unit_of_measure=? WHERE id=?", (calc_type, unit, created_kpi_id_final))
            return created_kpi_id_final # Return the kpi_spec.id
        finally:
            if is_path: conn_kpis.close() # Close only if this function opened it.


    def _ensure_stabilimento(conn_stab_main, name):
        is_path = isinstance(conn_stab_main, (str, Path))
        conn_stab = sqlite3.connect(conn_stab_main) if is_path else conn_stab_main
        try:
            with conn_stab:
                cursor = conn_stab.cursor()
                cursor.execute("SELECT id FROM stabilimenti WHERE name=?", (name,))
                stab = cursor.fetchone()
                if not stab:
                    cursor.execute("INSERT INTO stabilimenti (name, visible) VALUES (?,?)", (name, True))
                    return cursor.lastrowid
                else:
                    return stab[0]
        finally:
            if is_path: conn_stab.close()

    # Use paths for _ensure functions if they manage their own connections
    # For template tests, we will create groups/subgroups using the main functions.

    print("\n--- Inizio Test Logica Template KPI ---")
    try:
        # 1. Create a KPI Indicator Template
        template_name = "Standard Customer KPIs"
        template_desc = "A standard set of indicators for customer-related subgroups."
        try:
            customer_template_id = add_kpi_indicator_template(template_name, template_desc)
            print(f"Creato template '{template_name}' con ID: {customer_template_id}")
        except sqlite3.IntegrityError: # If test run multiple times
            tpl = get_kpi_indicator_templates()
            customer_template_id = next((t['id'] for t in tpl if t['name'] == template_name), None)
            if customer_template_id:
                print(f"Template '{template_name}' già esistente con ID: {customer_template_id}. Svuotamento definizioni per test.")
                # Clear existing definitions for a clean test run
                defs_to_clear = get_template_defined_indicators(customer_template_id)
                for d_clear in defs_to_clear:
                    remove_indicator_definition_from_template(d_clear['id']) # Assumes definition_id is the PK of template_defined_indicators
            else:
                raise Exception(f"Failed to create or find template {template_name}")


        # 2. Add Indicator Definitions to the Template
        add_indicator_definition_to_template(customer_template_id, "Official Claim Information", "Incrementale", "Count", True, "Number of official claims received.")
        add_indicator_definition_to_template(customer_template_id, "Logistic Claim", "Incrementale", "Count", True, "Number of logistic claims.")
        def_ppm_id_obj = add_indicator_definition_to_template(customer_template_id, "Net PPM Resi", "Media", "PPM", True, "Net Parts Per Million for returns.")
        print(f"Aggiunte definizioni al template ID {customer_template_id}.")
        
        template_indicators = get_template_defined_indicators(customer_template_id)
        print(f"Indicatori nel template '{template_name}': {[ti['indicator_name_in_template'] for ti in template_indicators]}")

        # 3. Create a Group and a Subgroup using this Template
        group_name_test = "Customer Relations Dept"
        subgroup_name_retail = "Retail Customers"
        subgroup_name_wholesale = "Wholesale Customers"
        
        try:
            test_group_id = add_kpi_group(group_name_test)
        except sqlite3.IntegrityError:
            groups = get_kpi_groups()
            test_group_id = next((g['id'] for g in groups if g['name'] == group_name_test), None)
            if not test_group_id: raise Exception(f"Failed to create/find group {group_name_test}")


        retail_subgroup_id = add_kpi_subgroup(subgroup_name_retail, test_group_id, customer_template_id)
        print(f"Creato sottogruppo '{subgroup_name_retail}' (ID: {retail_subgroup_id}) usando template ID {customer_template_id}.")
        
        wholesale_subgroup_id = add_kpi_subgroup(subgroup_name_wholesale, test_group_id, customer_template_id)
        print(f"Creato sottogruppo '{subgroup_name_wholesale}' (ID: {wholesale_subgroup_id}) usando template ID {customer_template_id}.")

        # Verify indicators in the new subgroup
        retail_indicators = get_kpi_indicators_by_subgroup(retail_subgroup_id)
        print(f"Indicatori in '{subgroup_name_retail}': {[i['name'] for i in retail_indicators]}")
        assert len(retail_indicators) == 3, "Retail subgroup should have 3 indicators from template."

        wholesale_indicators = get_kpi_indicators_by_subgroup(wholesale_subgroup_id)
        print(f"Indicatori in '{subgroup_name_wholesale}': {[i['name'] for i in wholesale_indicators]}")
        assert len(wholesale_indicators) == 3, "Wholesale subgroup should have 3 indicators from template."

        # 4. Add a new Indicator Definition to the Template and check propagation
        print("\nAggiunta 'Customer Satisfaction Score' al template...")
        add_indicator_definition_to_template(customer_template_id, "Customer Satisfaction Score", "Media", "%", True, "Overall customer satisfaction.")
        
        retail_indicators_after_add = get_kpi_indicators_by_subgroup(retail_subgroup_id)
        print(f"Indicatori in '{subgroup_name_retail}' dopo aggiunta al template: {[i['name'] for i in retail_indicators_after_add]}")
        assert len(retail_indicators_after_add) == 4, "Retail subgroup should now have 4 indicators."
        assert "Customer Satisfaction Score" in [i['name'] for i in retail_indicators_after_add]

        wholesale_indicators_after_add = get_kpi_indicators_by_subgroup(wholesale_subgroup_id)
        print(f"Indicatori in '{subgroup_name_wholesale}' dopo aggiunta al template: {[i['name'] for i in wholesale_indicators_after_add]}")
        assert len(wholesale_indicators_after_add) == 4, "Wholesale subgroup should now have 4 indicators."

        # 5. Remove an Indicator Definition from the Template and check propagation
        print("\nRimozione 'Net PPM Resi' dal template...")
        # Find the definition_id for "Net PPM Resi"
        ppm_def_to_remove = get_template_indicator_definition_by_name(customer_template_id, "Net PPM Resi")
        if ppm_def_to_remove:
            remove_indicator_definition_from_template(ppm_def_to_remove["id"])
            
            retail_indicators_after_remove = get_kpi_indicators_by_subgroup(retail_subgroup_id)
            print(f"Indicatori in '{subgroup_name_retail}' dopo rimozione dal template: {[i['name'] for i in retail_indicators_after_remove]}")
            assert len(retail_indicators_after_remove) == 3, "Retail subgroup should now have 3 indicators."
            assert "Net PPM Resi" not in [i['name'] for i in retail_indicators_after_remove]

            wholesale_indicators_after_remove = get_kpi_indicators_by_subgroup(wholesale_subgroup_id)
            print(f"Indicatori in '{subgroup_name_wholesale}' dopo rimozione dal template: {[i['name'] for i in wholesale_indicators_after_remove]}")
            assert len(wholesale_indicators_after_remove) == 3, "Wholesale subgroup should now have 3 indicators."
        else:
            print("ATTENZIONE: Definizione 'Net PPM Resi' non trovata nel template per la rimozione.")

        # 6. Test updating an indicator definition in template (e.g., change unit)
        print("\nAggiornamento 'Logistic Claim' nel template (cambio unità)...")
        logistic_claim_def = get_template_indicator_definition_by_name(customer_template_id, "Logistic Claim")
        if logistic_claim_def:
            update_indicator_definition_in_template(
                logistic_claim_def["id"],
                logistic_claim_def["indicator_name_in_template"], # Name stays the same
                logistic_claim_def["default_calculation_type"],
                "Cases", # New Unit
                bool(logistic_claim_def["default_visible"]),
                "Number of logistic claim cases reported." # New Description
            )
            # Verify the change in one of the subgroups' KPI spec
            retail_lc_indicator = next((i for i in get_kpi_indicators_by_subgroup(retail_subgroup_id) if i["name"] == "Logistic Claim"), None)
            if retail_lc_indicator:
                # Fetch the kpi spec for this indicator
                with sqlite3.connect(DB_KPIS) as conn:
                    conn.row_factory = sqlite3.Row
                    lc_kpi_spec = conn.execute("SELECT * FROM kpis WHERE indicator_id = ?", (retail_lc_indicator["id"],)).fetchone()
                    if lc_kpi_spec:
                        print(f"KPI Spec per 'Logistic Claim' in Retail: Unit='{lc_kpi_spec['unit_of_measure']}', Desc='{lc_kpi_spec['description']}'")
                        assert lc_kpi_spec['unit_of_measure'] == "Cases"
                        assert lc_kpi_spec['description'] == "Number of logistic claim cases reported."
                    else:
                        print("ATTENZIONE: KPI Spec per 'Logistic Claim' non trovato in Retail dopo l'update.")
            else:
                 print("ATTENZIONE: Indicatore 'Logistic Claim' non trovato in Retail dopo l'update del template.")
        else:
            print("ATTENZIONE: Definizione 'Logistic Claim' non trovata nel template per l'aggiornamento.")


        print("\n--- Fine Test Logica Template KPI ---")

    except Exception as e:
        print(f"ERRORE durante il test dei template KPI: {e}")
        import traceback
        traceback.print_exc()


    # The existing test suite for repartition logic
    kpi_id_inc_test = _ensure_kpi(DB_KPIS, "TestGroupLegacy", "TestSubLegacy", "TestIndicatorIncLegacy", "Incrementale", "Units")
    kpi_id_avg_test = _ensure_kpi(DB_KPIS, "TestGroupLegacy", "TestSubLegacy", "TestIndicatorAvgLegacy", "Media", "%")
    stab_id_test = _ensure_stabilimento(DB_STABILIMENTI, "TestStabLegacy")

    test_year_main = datetime.datetime.now().year if datetime.datetime.now().month < 10 else datetime.datetime.now().year + 1
    
    # Check if kpi_id_inc_test and kpi_id_avg_test were created before proceeding
    if kpi_id_inc_test is None or kpi_id_avg_test is None:
        print("\nATTENZIONE: KPI di test legacy non creati, salto i test di ripartizione.")
    else:
        print("\n--- Inizio Test Logica Database con Nuovi Profili (Legacy KPIs) ---")
        days_this_year_for_test = (datetime.date(test_year_main, 12, 31) - datetime.date(test_year_main, 1, 1)).days + 1
        targets_even_inc = {
            kpi_id_inc_test: { # kpi_id_inc_test is kpi_spec.id
                "annual_target1": float(days_this_year_for_test * 10), "annual_target2": 0, 
                "repartition_logic": "Anno", 
                "repartition_values": {},
                "distribution_profile": "even_distribution"
            }
        }
        save_annual_targets(test_year_main, stab_id_test, targets_even_inc)
        print(f"\nTest Even Inc (Target 1: {targets_even_inc[kpi_id_inc_test]['annual_target1']}) - {test_year_main} - Giorno (Primi 5):")
        daily_data = get_ripartiti_data(test_year_main, stab_id_test, kpi_id_inc_test, "Giorno", 1)
        for row in daily_data[:5]: print(f"  {row['Periodo']}: {row['Target']:.2f}")
        
        # Test 2: True Annual Sinusoidal - Media
        targets_sin_avg = {
            kpi_id_avg_test: {
                "annual_target1": 100, "annual_target2": 0,
                "repartition_logic": "Anno",
                "repartition_values": {},
                "distribution_profile": "true_annual_sinusoidal",
                "profile_params": {"sine_amplitude": 0.15, "sine_phase": -np.pi/2} 
            }
        }
        save_annual_targets(test_year_main, stab_id_test, targets_sin_avg)
        print(f"\nTest True Annual Sinusoidal Media (Target 1: 100) - {test_year_main} - Mese:")
        for row in get_ripartiti_data(test_year_main, stab_id_test, kpi_id_avg_test, "Mese", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")
        print("\n--- Fine Test Logica Database (Legacy KPIs) ---")
