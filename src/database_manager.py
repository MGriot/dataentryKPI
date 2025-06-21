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
WEIGHT_INITIAL_FACTOR_AVG = 1.2
WEIGHT_FINAL_FACTOR_AVG = 0.8
DEVIATION_SCALE_FACTOR_AVG = 0.2

SINE_AMPLITUDE_INCREMENTAL = 0.5
SINE_AMPLITUDE_MEDIA = 0.1
SINE_PHASE_OFFSET = -np.pi / 2

WEEKDAY_BIAS_FACTOR_INCREMENTAL = 0.5
WEEKDAY_BIAS_FACTOR_MEDIA = 0.8

# --- COSTANTI STRINGA ---
CALC_TYPE_INCREMENTALE = "Incrementale"
CALC_TYPE_MEDIA = "Media"

REPARTITION_LOGIC_ANNO = "Anno"
REPARTITION_LOGIC_MESE = "Mese"
REPARTITION_LOGIC_TRIMESTRE = "Trimestre"
REPARTITION_LOGIC_SETTIMANA = "Settimana"

PROFILE_EVEN = "even_distribution"
PROFILE_ANNUAL_PROGRESSIVE = "annual_progressive"
PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS = "annual_progressive_weekday_bias"
PROFILE_TRUE_ANNUAL_SINUSOIDAL = "true_annual_sinusoidal"
PROFILE_MONTHLY_SINUSOIDAL = "monthly_sinusoidal" # Parabolic within month
PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE = "legacy_intra_period_progressive" # Progressive within month/quarter
PROFILE_QUARTERLY_PROGRESSIVE = "quarterly_progressive" # Progressive within quarter
PROFILE_QUARTERLY_SINUSOIDAL = "quarterly_sinusoidal" # Parabolic within quarter
# PROFILE_EVENT_BASED = "event_based_spikes_or_dips" # This seems to be handled by profile_params now


# --- Funzioni Helper Generiche ---
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
        shift = abs(min_raw_weight) + 1e-9
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
        raw_weights = np.max(raw_weights) - raw_weights
    raw_weights += min_value_epsilon
    total_weight = np.sum(raw_weights)
    return (
        (raw_weights / total_weight).tolist()
        if total_weight != 0
        else [1.0 / num_periods] * num_periods
    )

def get_sinusoidal_proportions(num_periods, amplitude=0.5, phase_offset=0, min_value_epsilon=1e-9):
    if num_periods <= 0: return []
    if num_periods == 1: return [1.0]
    x = np.linspace(0, 2 * np.pi, num_periods, endpoint=False)
    raw_weights = 1 + amplitude * np.sin(x + phase_offset)
    raw_weights = np.maximum(raw_weights, min_value_epsilon)
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
        cursor.execute("PRAGMA table_info(kpi_subgroups)")
        subgroup_columns = {col[1] for col in cursor.fetchall()}
        if "indicator_template_id" not in subgroup_columns:
            try:
                cursor.execute("ALTER TABLE kpi_subgroups ADD COLUMN indicator_template_id INTEGER REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL")
                print("Aggiunta colonna 'indicator_template_id' a 'kpi_subgroups'.")
            except sqlite3.OperationalError as e:
                print(f"WARN: Could not add 'indicator_template_id' to 'kpi_subgroups', might exist or other issue: {e}")

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
        cursor.execute(
             """ CREATE TABLE IF NOT EXISTS annual_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, stabilimento_id INTEGER NOT NULL, kpi_id INTEGER NOT NULL,
                annual_target1 REAL NOT NULL DEFAULT 0, annual_target2 REAL NOT NULL DEFAULT 0,
                repartition_logic TEXT NOT NULL,
                repartition_values TEXT NOT NULL,
                distribution_profile TEXT NOT NULL DEFAULT 'annual_progressive',
                profile_params TEXT,
                FOREIGN KEY (kpi_id) REFERENCES kpis(id) ON DELETE CASCADE, /* Non applicato tra DB diversi da SQLite */
                UNIQUE(year, stabilimento_id, kpi_id))"""
        )
        cursor.execute("PRAGMA table_info(annual_targets)")
        target_columns = {col[1] for col in cursor.fetchall()}
        if "profile_params" not in target_columns:
            try:
                cursor.execute("ALTER TABLE annual_targets ADD COLUMN profile_params TEXT")
                print("Aggiunta colonna 'profile_params' a 'annual_targets'.")
            except sqlite3.OperationalError:
                cursor.execute("PRAGMA table_info(annual_targets)") # Re-check
                if "profile_params" not in {col[1] for col in cursor.fetchall()}:
                    print("ERRORE: Impossibile aggiungere la colonna 'profile_params' a 'annual_targets'.")
        # Check for other essential columns
        required_cols = {"annual_target1", "annual_target2", "distribution_profile", "repartition_logic", "repartition_values"}
        if not required_cols.issubset(target_columns):
            print("Tabella 'annual_targets' con schema obsoleto, tentativo di ricreazione...")
            # Potrebbe essere più sicuro fare un backup prima di DROP
            cursor.execute("DROP TABLE IF EXISTS annual_targets")
            cursor.execute( # Ricreazione con lo schema corretto
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


# --- Gestione Gruppi KPI ---
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
    # Cascade delete is handled by SQLite for kpi_subgroups if group_id is deleted.
    # We need to manually handle deletion of kpis specs and their targets
    # that belong to indicators within subgroups of this group.
    indicators_to_delete_ids = []
    with sqlite3.connect(DB_KPIS) as conn_kpis_read:
        conn_kpis_read.row_factory = sqlite3.Row
        subgroups_in_group = conn_kpis_read.execute("SELECT id FROM kpi_subgroups WHERE group_id = ?", (group_id,)).fetchall()
        for sg_row in subgroups_in_group:
            indicators = conn_kpis_read.execute("SELECT id FROM kpi_indicators WHERE subgroup_id = ?", (sg_row["id"],)).fetchall()
            for ind_row in indicators:
                indicators_to_delete_ids.append(ind_row["id"])

    for ind_id in indicators_to_delete_ids:
        # This will trigger cascades for kpis spec and associated targets.
        # delete_kpi_indicator handles this logic internally.
        delete_kpi_indicator(ind_id) # Call the comprehensive delete function

    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("DELETE FROM kpi_groups WHERE id = ?", (group_id,)) # This will cascade to subgroups
        conn.commit()


# --- Gestione Template Indicatori KPI ---
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
    # First, get all subgroups linked to this template to clear their indicators later if needed.
    linked_subgroup_ids = []
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        rows = conn_kpis.execute("SELECT id FROM kpi_subgroups WHERE indicator_template_id = ?", (template_id,)).fetchall()
        linked_subgroup_ids = [row['id'] for row in rows]

    # Get definitions from template BEFORE deleting template, for propagation of removal.
    definitions_in_template = get_template_defined_indicators(template_id)

    with sqlite3.connect(DB_KPI_TEMPLATES) as conn_tpl:
        conn_tpl.execute("DELETE FROM kpi_indicator_templates WHERE id = ?", (template_id,)) # Cascades to template_defined_indicators
        conn_tpl.commit()

    # Now, propagate removal of these indicators from the linked subgroups
    if linked_subgroup_ids and definitions_in_template:
        for def_to_remove in definitions_in_template:
            # Simulate 'remove' action for each definition for each linked subgroup
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
            existing_def = get_template_indicator_definition_by_name(template_id, indicator_name)
            if existing_def:
                definition_details["id"] = existing_def["id"]
                # Trigger update if it already exists and parameters are different
                if (existing_def["default_calculation_type"] != calc_type or
                    existing_def["default_unit_of_measure"] != unit or
                    bool(existing_def["default_visible"]) != visible or
                    existing_def["default_description"] != description):
                    update_indicator_definition_in_template(
                        existing_def["id"], indicator_name, calc_type, unit, visible, description
                    ) # This will trigger its own propagation
            else:
                raise
            return # Exit after handling existing or re-raising

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
    current_def = get_template_indicator_definition_by_id(definition_id)
    if not current_def:
        print(f"Definizione indicatore con ID {definition_id} non trovata.")
        return

    # If the name in template changes, it's more complex. For now, assume this is an update of properties for the SAME conceptual indicator.
    # If indicator_name_in_template needs to change, it's safer to treat it as a remove_old + add_new operation.
    # Here, we will update and propagate. If the name changed, the propagation will attempt to find an indicator
    # by the *new* name in linked subgroups. If it doesn't exist, it will be created.
    # Indicators in subgroups matching the *old* name (if different from new) will NOT be automatically deleted by this function.
    if current_def["indicator_name_in_template"] != indicator_name:
        print(f"WARN: Modifica del nome dell'indicatore nel template (da '{current_def['indicator_name_in_template']}' a '{indicator_name}'). "
              f"Questo potrebbe creare un nuovo indicatore nei sottogruppi collegati e lasciare orfano il vecchio.")
        # To handle this cleanly:
        # 1. Propagate 'remove' for the old definition name.
        # _propagate_template_indicator_change(current_def["template_id"], current_def, "remove")
        # 2. Then proceed to update and propagate 'add_or_update' for the new definition details.
        # This is a complex interaction, for now, we proceed with the simple update.

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
        "template_id": current_def["template_id"],
        "indicator_name_in_template": indicator_name, # Use the new name for propagation
        "default_description": description,
        "default_calculation_type": calc_type,
        "default_unit_of_measure": unit,
        "default_visible": visible,
    }
    _propagate_template_indicator_change(current_def["template_id"], updated_definition_details, "add_or_update")

def remove_indicator_definition_from_template(definition_id):
    definition_to_delete = get_template_indicator_definition_by_id(definition_id)
    if not definition_to_delete:
        print(f"Definizione indicatore con ID {definition_id} non trovata per la rimozione.")
        return

    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.execute("DELETE FROM template_defined_indicators WHERE id = ?", (definition_id,))
        conn.commit()

    _propagate_template_indicator_change(definition_to_delete["template_id"], definition_to_delete, "remove")


def _propagate_template_indicator_change(template_id, indicator_definition, action, specific_subgroup_ids=None):
    subgroups_to_update = []
    with sqlite3.connect(DB_KPIS) as conn_kpis_read: # Connection for reading subgroups
        conn_kpis_read.row_factory = sqlite3.Row
        if specific_subgroup_ids:
            # Create a placeholder string for the IN clause
            placeholders = ','.join('?' for _ in specific_subgroup_ids)
            query_sg = f"SELECT id FROM kpi_subgroups WHERE indicator_template_id = ? AND id IN ({placeholders})"
            params_sg = [template_id] + specific_subgroup_ids
            subgroups_to_update = conn_kpis_read.execute(query_sg, params_sg).fetchall()
        else:
            subgroups_to_update = conn_kpis_read.execute(
                "SELECT id FROM kpi_subgroups WHERE indicator_template_id = ?", (template_id,)
            ).fetchall()

    if not subgroups_to_update:
        # print(f"Propagate Info: Nessun sottogruppo collegato al template ID {template_id} trovato per l'azione '{action}'.")
        return

    # Use a single connection for all actions within this propagation call
    with sqlite3.connect(DB_KPIS) as conn_kpis_action:
        conn_kpis_action.row_factory = sqlite3.Row # Important for fetching existing_indicator
        conn_kpis_action.execute("PRAGMA foreign_keys = ON;") # Ensure cascades if any

        for sg_row in subgroups_to_update:
            subgroup_id = sg_row["id"]
            indicator_name_in_subgroup = indicator_definition["indicator_name_in_template"]

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
                        print(f"Propagated Add: Indicatore '{indicator_name_in_subgroup}' (ID:{actual_indicator_id}) a Sottogruppo ID {subgroup_id}.")
                    except sqlite3.IntegrityError: # Should be caught by 'if not existing_indicator'
                        existing_indicator = conn_kpis_action.execute( # Re-fetch
                            "SELECT id FROM kpi_indicators WHERE name = ? AND subgroup_id = ?",
                            (indicator_name_in_subgroup, subgroup_id)
                        ).fetchone()
                        if existing_indicator: actual_indicator_id = existing_indicator["id"]
                        else:
                            print(f"Errore propagazione Add per '{indicator_name_in_subgroup}' a sottogruppo {subgroup_id}: Impossibile creare o trovare."); continue
                else:
                    actual_indicator_id = existing_indicator["id"]

                if actual_indicator_id:
                    kpi_spec = conn_kpis_action.execute("SELECT id FROM kpis WHERE indicator_id = ?", (actual_indicator_id,)).fetchone()
                    desc = indicator_definition["default_description"]
                    calc = indicator_definition["default_calculation_type"]
                    unit = indicator_definition["default_unit_of_measure"]
                    vis = bool(indicator_definition["default_visible"])

                    if not kpi_spec:
                        try:
                            conn_kpis_action.execute(
                                """INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible)
                                   VALUES (?,?,?,?,?)""", (actual_indicator_id, desc, calc, unit, vis) )
                            print(f"Propagated Add Spec: KPI Spec per Indicatore ID {actual_indicator_id} ('{indicator_name_in_subgroup}') in Sottogruppo ID {subgroup_id}.")
                        except sqlite3.IntegrityError as e_add_kpi:
                             print(f"Errore aggiunta KPI spec per IndID {actual_indicator_id} in SG {subgroup_id}: {e_add_kpi}")
                    else:
                        conn_kpis_action.execute(
                            """UPDATE kpis SET description=?, calculation_type=?, unit_of_measure=?, visible=?
                               WHERE id=?""", (desc, calc, unit, vis, kpi_spec["id"]) )
                        print(f"Propagated Update Spec: KPI Spec per Indicatore ID {actual_indicator_id} ('{indicator_name_in_subgroup}') in Sottogruppo ID {subgroup_id}.")

            elif action == "remove":
                if existing_indicator:
                    indicator_id_to_delete = existing_indicator["id"]
                    # delete_kpi_indicator handles deleting the kpi spec and targets from other DBs.
                    # It manages its own connections for those external DBs.
                    # We only need to delete the kpi_indicator here, and its kpis spec will cascade in DB_KPIS.
                    # The targets associated with kpis.id (from this indicator_id_to_delete) must be handled by delete_kpi_indicator.
                    print(f"Propagated Remove: Indicatore '{indicator_name_in_subgroup}' (ID: {indicator_id_to_delete}) da Sottogruppo ID {subgroup_id}. Chiamata a delete_kpi_indicator...")
                    delete_kpi_indicator(indicator_id_to_delete) # This will handle everything.
                else:
                    print(f"Propagate remove: Indicatore '{indicator_name_in_subgroup}' non trovato in Sottogruppo ID {subgroup_id}, nessuna azione.")
        conn_kpis_action.commit() # Commit all changes for this propagation cycle


# --- Gestione Sottogruppi KPI ---
def add_kpi_subgroup(name, group_id, indicator_template_id=None):
    subgroup_id = None
    with sqlite3.connect(DB_KPIS) as conn: # Connection for adding the subgroup itself
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
        template_indicators = get_template_defined_indicators(indicator_template_id)
        for ind_def in template_indicators:
            # Use _apply_template_indicator_to_new_subgroup which manages its own connection for atomicity of this specific step
            _apply_template_indicator_to_new_subgroup(subgroup_id, ind_def)
    return subgroup_id

def _apply_template_indicator_to_new_subgroup(subgroup_id, indicator_definition):
    indicator_name = indicator_definition["indicator_name_in_template"]
    desc = indicator_definition["default_description"]
    calc = indicator_definition["default_calculation_type"]
    unit = indicator_definition["default_unit_of_measure"]
    vis = bool(indicator_definition["default_visible"])

    with sqlite3.connect(DB_KPIS) as conn_apply: # Manage connection for this specific application
        conn_apply.execute("PRAGMA foreign_keys = ON;")
        actual_indicator_id = None
        try:
            cursor_ind = conn_apply.cursor()
            cursor_ind.execute(
                "INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)",
                (indicator_name, subgroup_id)
            )
            actual_indicator_id = cursor_ind.lastrowid
        except sqlite3.IntegrityError:
            print(f"Warn ApplyTpl: Indicatore '{indicator_name}' già esistente (o errore) in nuovo sottogruppo {subgroup_id} durante applicazione template.")
            # Fetch if it somehow exists
            existing_ind_row = conn_apply.execute("SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?", (indicator_name, subgroup_id)).fetchone()
            if existing_ind_row: actual_indicator_id = existing_ind_row[0]
            else: print(f"Errore Critico ApplyTpl: Impossibile creare o trovare Indicatore '{indicator_name}' per SG {subgroup_id}."); return

        if actual_indicator_id:
            try:
                conn_apply.execute(
                    "INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible) VALUES (?,?,?,?,?)",
                    (actual_indicator_id, desc, calc, unit, vis)
                )
            except sqlite3.IntegrityError: # KPI spec for this indicator_id already exists
                print(f"Warn ApplyTpl: KPI spec per indicatore '{indicator_name}' (ID: {actual_indicator_id}) già esistente in nuovo sottogruppo {subgroup_id}. Aggiornamento.")
                conn_apply.execute(
                     "UPDATE kpis SET description=?, calculation_type=?, unit_of_measure=?, visible=? WHERE indicator_id=?",
                     (desc, calc, unit, vis, actual_indicator_id)
                )
        conn_apply.commit()

def get_kpi_subgroups_by_group_revised(group_id): # Revised to query template names separately
    subgroups = []
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        subgroups_raw = conn_kpis.execute(
            "SELECT * FROM kpi_subgroups WHERE group_id = ? ORDER BY name", (group_id,)
        ).fetchall()

    templates_info = {}
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn_templates: # Separate connection for templates DB
        conn_templates.row_factory = sqlite3.Row
        all_templates = conn_templates.execute("SELECT id, name FROM kpi_indicator_templates").fetchall()
        for t in all_templates:
            templates_info[t["id"]] = t["name"]

    for sg_raw in subgroups_raw:
        sg_dict = dict(sg_raw)
        sg_dict["template_name"] = templates_info.get(sg_raw["indicator_template_id"])
        subgroups.append(sg_dict)
    return subgroups


def update_kpi_subgroup(subgroup_id, new_name, group_id, new_template_id=None):
    current_subgroup_info = None
    with sqlite3.connect(DB_KPIS) as conn_read: # Read current state
        conn_read.row_factory = sqlite3.Row
        current_subgroup_info = conn_read.execute("SELECT indicator_template_id, name FROM kpi_subgroups WHERE id = ?", (subgroup_id,)).fetchone()

    if not current_subgroup_info:
        print(f"Errore: Sottogruppo con ID {subgroup_id} non trovato.")
        return

    old_template_id = current_subgroup_info["indicator_template_id"]

    with sqlite3.connect(DB_KPIS) as conn_update: # Connection for update subgroup
        try:
            conn_update.execute("UPDATE kpi_subgroups SET name = ?, group_id = ?, indicator_template_id = ? WHERE id = ?",
                               (new_name, group_id, new_template_id, subgroup_id))
            conn_update.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento del sottogruppo: Nome '{new_name}' potrebbe già esistere in questo gruppo.")
            raise e

    # Logic for template change
    if old_template_id != new_template_id:
        print(f"Template per sottogruppo {subgroup_id} ('{new_name}') cambiato da {old_template_id} a {new_template_id}.")
        # 1. Remove indicators from the old template (if any)
        if old_template_id is not None:
            old_template_definitions = get_template_defined_indicators(old_template_id)
            for old_def in old_template_definitions:
                _propagate_template_indicator_change(old_template_id, old_def, "remove", specific_subgroup_ids=[subgroup_id])

        # 2. Apply indicators from the new template (if any)
        if new_template_id is not None:
            new_template_definitions = get_template_defined_indicators(new_template_id)
            for new_def in new_template_definitions:
                # _propagate_template_indicator_change is for when template changes.
                # Here, the subgroup's link has changed, so we apply directly.
                 _apply_template_indicator_to_new_subgroup(subgroup_id, new_def)
            print(f"Indicatori del nuovo template {new_template_id} applicati/aggiornati per il sottogruppo {subgroup_id}.")


def delete_kpi_subgroup(subgroup_id):
    # Get all indicators in this subgroup to delete them and their data properly
    indicators_in_subgroup_ids = []
    with sqlite3.connect(DB_KPIS) as conn_kpis_read:
        conn_kpis_read.row_factory = sqlite3.Row
        indicators = conn_kpis_read.execute("SELECT id FROM kpi_indicators WHERE subgroup_id = ?", (subgroup_id,)).fetchall()
        indicators_in_subgroup_ids = [ind_row["id"] for ind_row in indicators]

    for ind_id in indicators_in_subgroup_ids:
        delete_kpi_indicator(ind_id) # This handles kpis spec and targets in other DBs

    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute("PRAGMA foreign_keys = ON;") # Ensure cascade from subgroup to indicators if any were manually added and not caught
        conn.execute("DELETE FROM kpi_subgroups WHERE id = ?", (subgroup_id,))
        conn.commit()


# --- Gestione Indicatori KPI ---
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
            existing_id_row = conn.execute("SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?", (name, subgroup_id)).fetchone()
            if existing_id_row: return existing_id_row[0]
            raise

def get_kpi_indicators_by_subgroup(subgroup_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM kpi_indicators WHERE subgroup_id = ? ORDER BY name",
            (subgroup_id,),
        ).fetchall()

def update_kpi_indicator(indicator_id, new_name, subgroup_id):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute("UPDATE kpi_indicators SET name = ?, subgroup_id = ? WHERE id = ?", (new_name, subgroup_id, indicator_id))
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento dell'indicatore: Nome '{new_name}' potrebbe già esistere in questo sottogruppo.")
            raise e

def delete_kpi_indicator(indicator_id):
    kpi_spec_id_to_delete = None
    with sqlite3.connect(DB_KPIS) as conn_kpis_read: # Separate read for kpi_spec_id
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

    # Deletes kpis spec via cascade FROM kpi_indicators when indicator is deleted in DB_KPIS
    with sqlite3.connect(DB_KPIS) as conn_kpis_delete:
        conn_kpis_delete.execute("PRAGMA foreign_keys = ON;") # Ensure cascade delete is active
        conn_kpis_delete.execute("DELETE FROM kpi_indicators WHERE id = ?", (indicator_id,))
        conn_kpis_delete.commit()


# --- Gestione Specifiche KPI (tabella `kpis`) ---
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
    # This function should handle "insert or update" logic for a kpi spec.
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpis (indicator_id,description,calculation_type,unit_of_measure,visible) VALUES (?,?,?,?,?)",
                (indicator_id, description, calculation_type, unit_of_measure, visible),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kpis.indicator_id" in str(e):
                # KPI spec for this indicator_id already exists, so update it.
                print(f"KPI Spec for indicator_id {indicator_id} already exists. Attempting to update.")
                existing_kpi_row = conn.execute("SELECT id FROM kpis WHERE indicator_id=?", (indicator_id,)).fetchone()
                if existing_kpi_row:
                    existing_kpi_id = existing_kpi_row[0] # This is kpis.id (the spec ID)
                    update_kpi(existing_kpi_id, indicator_id, description, calculation_type, unit_of_measure, visible) # Call update
                    conn.commit() # update_kpi commits, but ensure consistency if it didn't
                    return existing_kpi_id
                else: # Should not happen if IntegrityError was due to kpis.indicator_id
                    print(f"IntegrityError for indicator_id {indicator_id}, but could not find existing kpi_spec to update.")
                    raise e
            else: # Some other integrity error
                raise e


def update_kpi(kpi_id, indicator_id, description, calculation_type, unit_of_measure, visible):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute(
                "UPDATE kpis SET indicator_id=?,description=?,calculation_type=?,unit_of_measure=?,visible=? WHERE id=?",
                (indicator_id, description, calculation_type, unit_of_measure, visible, kpi_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as e: # indicator_id might clash if changed to an existing one
            raise e

def get_kpi_by_id(kpi_id): # Fetches full details including template name for the subgroup
    with sqlite3.connect(DB_KPIS) as conn_kpis: # Connection to DB_KPIS
        conn_kpis.row_factory = sqlite3.Row
        query = """SELECT k.id, g.name as group_name, sg.name as subgroup_name, i.name as indicator_name,
                          i.id as actual_indicator_id, k.indicator_id, k.description, k.calculation_type,
                          k.unit_of_measure, k.visible, sg.id as subgroup_id /* Added subgroup_id */
                   FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id
                   JOIN kpi_subgroups sg ON i.subgroup_id = sg.id JOIN kpi_groups g ON sg.group_id = g.id
                   WHERE k.id = ?"""
        kpi_info_row = conn_kpis.execute(query, (kpi_id,)).fetchone()

        if kpi_info_row:
            kpi_dict = dict(kpi_info_row)
            # Fetch template_id and name for the subgroup
            subgroup_full_details = get_kpi_subgroup_by_id_with_template_name(kpi_dict["subgroup_id"])
            if subgroup_full_details:
                kpi_dict['indicator_template_id'] = subgroup_full_details.get('indicator_template_id')
                kpi_dict['template_name'] = subgroup_full_details.get('template_name')
            return kpi_dict
    return None

def get_kpi_subgroup_by_id_with_template_name(subgroup_id):
    sg_dict = None
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        sg_raw = conn_kpis.execute("SELECT * FROM kpi_subgroups WHERE id = ?", (subgroup_id,)).fetchone()
        if sg_raw:
            sg_dict = dict(sg_raw)
            if sg_raw["indicator_template_id"]:
                with sqlite3.connect(DB_KPI_TEMPLATES) as conn_templates:
                    conn_templates.row_factory = sqlite3.Row
                    template_info = conn_templates.execute("SELECT name FROM kpi_indicator_templates WHERE id = ?",
                                                           (sg_raw["indicator_template_id"],)).fetchone()
                    if template_info:
                        sg_dict["template_name"] = template_info["name"]
    return sg_dict


# --- Gestione Stabilimenti ---
def get_stabilimenti(only_visible=False):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM stabilimenti" + (" WHERE visible = 1" if only_visible else "") + " ORDER BY name"
        return conn.execute(query).fetchall()

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


# --- Gestione Target Annuali ---
def get_annual_target(year, stabilimento_id, kpi_id): # kpi_id is kpis.id
    with sqlite3.connect(DB_TARGETS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM annual_targets WHERE year=? AND stabilimento_id=? AND kpi_id=?",
            (year, stabilimento_id, kpi_id),
        ).fetchone()

def save_annual_targets(year, stabilimento_id, targets_data):
    if not targets_data: print("Nessun dato target da salvare."); return
    with sqlite3.connect(DB_TARGETS) as conn:
        cursor = conn.cursor()
        for kpi_id_str, data in targets_data.items():
            try: current_kpi_id = int(kpi_id_str) # kpi_id here is kpis.id
            except ValueError: print(f"Skipping invalid kpi_id: {kpi_id_str}"); continue
            record = get_annual_target(year, stabilimento_id, current_kpi_id)
            repart_values_json = json.dumps(data.get("repartition_values", {}))
            dist_profile = data.get("distribution_profile", PROFILE_ANNUAL_PROGRESSIVE)
            profile_params_json = json.dumps(data.get("profile_params", {}))
            annual_t1 = float(data.get("annual_target1", 0.0) or 0.0)
            annual_t2 = float(data.get("annual_target2", 0.0) or 0.0)
            repart_logic = data.get("repartition_logic", REPARTITION_LOGIC_ANNO)
            if record:
                cursor.execute(
                    """UPDATE annual_targets SET annual_target1=?, annual_target2=?, repartition_logic=?,
                       repartition_values=?, distribution_profile=?, profile_params=? WHERE id=?""",
                    (annual_t1, annual_t2, repart_logic, repart_values_json, dist_profile, profile_params_json, record["id"]))
            else:
                cursor.execute(
                    """INSERT INTO annual_targets (year,stabilimento_id,kpi_id,annual_target1,annual_target2,
                       repartition_logic,repartition_values,distribution_profile,profile_params) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (year, stabilimento_id, current_kpi_id, annual_t1, annual_t2, repart_logic,
                     repart_values_json, dist_profile, profile_params_json))
        conn.commit()
    for kpi_id_saved_str in targets_data.keys():
        try:
            kpi_id_saved = int(kpi_id_saved_str)
            calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved, 1)
            calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved, 2)
        except ValueError: print(f"Skipping repartitions for invalid kpi_id during save: {kpi_id_saved_str}")
    try:
        if hasattr(export_manager, 'export_all_data_to_global_csvs'):
            export_manager.export_all_data_to_global_csvs(str(CSV_EXPORT_BASE_PATH))
        else: print("Funzione export_manager.export_all_data_to_global_csvs non trovata.")
    except Exception as e: print(f"ERRORE CRITICO durante la generazione dei CSV globali: {e}")


# --- Logica di Ripartizione e Calcolo (Refined) ---

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

    elif kpi_calc_type == CALC_TYPE_MEDIA:
        # For Media, user_repartition_values are target values or multipliers (e.g., if value is 80, it means target * 0.8)
        # The period_allocations will store these multipliers relative to the annual_target.
        if user_repartition_logic == REPARTITION_LOGIC_MESE:
            for i in range(12): # month_idx_0_based
                # Assuming user_repartition_values for Media/Month are direct target values for the month
                # To make it a multiplier: user_repartition_values.get(calendar.month_name[i+1], annual_target) / annual_target if annual_target else 1.0
                # For now, let's assume values are percentages of the annual_target for that month.
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
    return period_allocations


def _get_raw_daily_values_for_repartition(
    year,
    annual_target,
    kpi_calc_type,
    distribution_profile,
    profile_params,
    user_repartition_logic,
    period_allocations_map,
    all_dates_in_year,
):
    days_in_year = len(all_dates_in_year)
    raw_daily_values = np.zeros(days_in_year)

    # --- INCREMENTAL KPI ---
    if kpi_calc_type == CALC_TYPE_INCREMENTALE:
        if distribution_profile == PROFILE_EVEN:
            # If logic is Anno OR no specific period allocations were made (e.g. user provided empty month list)
            if (
                user_repartition_logic == REPARTITION_LOGIC_ANNO
                or not period_allocations_map
            ):
                daily_val = annual_target / days_in_year if days_in_year > 0 else 0
                raw_daily_values.fill(daily_val)
            else:  # Distribute period totals (from period_allocations_map) evenly among days in that period
                for d_idx, date_val in enumerate(all_dates_in_year):
                    target_sum_for_this_day_period = 0
                    num_days_in_this_day_period = 0

                    if user_repartition_logic == REPARTITION_LOGIC_MESE:
                        target_sum_for_this_day_period = period_allocations_map.get(
                            date_val.month - 1, 0
                        )  # Get sum for this month
                        _, num_days_in_this_day_period = calendar.monthrange(
                            year, date_val.month
                        )
                    elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
                        q_idx_0_based = (date_val.month - 1) // 3
                        target_sum_for_this_day_period = period_allocations_map.get(
                            q_idx_0_based, 0
                        )  # Get sum for this quarter
                        q_ranges = get_date_ranges_for_quarters(year)
                        q_start, q_end = q_ranges[q_idx_0_based + 1]
                        num_days_in_this_day_period = (q_end - q_start).days + 1
                    elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
                        iso_y, iso_w, _ = date_val.isocalendar()
                        wk_key = f"{iso_y}-W{iso_w:02d}"
                        target_sum_for_this_day_period = period_allocations_map.get(
                            wk_key, 0
                        )  # Get sum for this week
                        num_days_in_this_day_period = sum(
                            1
                            for d_in_wk in all_dates_in_year
                            if d_in_wk.isocalendar()[0] == iso_y
                            and d_in_wk.isocalendar()[1] == iso_w
                        )

                    raw_daily_values[d_idx] = (
                        target_sum_for_this_day_period / num_days_in_this_day_period
                        if num_days_in_this_day_period > 0
                        else 0
                    )

        elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE:
            props = get_weighted_proportions(
                days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC
            )
            raw_daily_values = np.array([annual_target * p for p in props])

        elif distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
            amp = profile_params.get("sine_amplitude", SINE_AMPLITUDE_INCREMENTAL)
            phase = profile_params.get("sine_phase", SINE_PHASE_OFFSET)
            props = get_sinusoidal_proportions(days_in_year, amp, phase)
            raw_daily_values = np.array([annual_target * p for p in props])

        elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
            base_props = get_weighted_proportions(
                days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC
            )
            adj_props = np.array(
                [
                    base_props[i]
                    * (
                        WEEKDAY_BIAS_FACTOR_INCREMENTAL
                        if all_dates_in_year[i].weekday() >= 5
                        else 1.0
                    )
                    for i in range(days_in_year)
                ]
            )
            current_sum_adj = np.sum(adj_props)
            final_props_adj = (
                (adj_props / current_sum_adj)
                if current_sum_adj > 1e-9
                else ([1.0 / days_in_year] * days_in_year if days_in_year > 0 else [])
            )
            raw_daily_values = np.array([annual_target * p for p in final_props_adj])

        elif distribution_profile in [
            PROFILE_MONTHLY_SINUSOIDAL,
            PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
            PROFILE_QUARTERLY_PROGRESSIVE,
            PROFILE_QUARTERLY_SINUSOIDAL,
        ]:

            if user_repartition_logic == REPARTITION_LOGIC_MESE or (
                user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE
                and distribution_profile
                in [PROFILE_MONTHLY_SINUSOIDAL, PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE]
            ):

                monthly_target_sums_final = [0.0] * 12  # 0-indexed month
                if user_repartition_logic == REPARTITION_LOGIC_MESE:
                    for m_idx_0based in range(12):
                        monthly_target_sums_final[m_idx_0based] = (
                            period_allocations_map.get(m_idx_0based, 0)
                        )
                elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
                    q_map_month_indices = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11]]
                    for q_idx_0based, months_in_q_indices in enumerate(
                        q_map_month_indices
                    ):
                        q_total_sum = period_allocations_map.get(q_idx_0based, 0)
                        num_months_in_q = len(months_in_q_indices)
                        month_weights_in_q = get_weighted_proportions(
                            num_months_in_q, 1, 1
                        )  # Default even split
                        if (
                            distribution_profile
                            == PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE
                        ):  # Special case for this profile
                            month_weights_in_q = get_weighted_proportions(
                                num_months_in_q,
                                WEIGHT_INITIAL_FACTOR_INC,
                                WEIGHT_FINAL_FACTOR_INC,
                            )
                        for i, month_idx_in_year_0based in enumerate(
                            months_in_q_indices
                        ):
                            monthly_target_sums_final[month_idx_in_year_0based] = (
                                q_total_sum * month_weights_in_q[i]
                            )

                for month_idx_0based, month_sum_val in enumerate(
                    monthly_target_sums_final
                ):
                    current_month_1based = month_idx_0based + 1
                    num_days_in_month_val = calendar.monthrange(
                        year, current_month_1based
                    )[1]
                    if num_days_in_month_val == 0 or abs(month_sum_val) < 1e-9:
                        continue

                    day_props_in_month_list = []
                    if distribution_profile == PROFILE_MONTHLY_SINUSOIDAL:
                        day_props_in_month_list = get_parabolic_proportions(
                            num_days_in_month_val, peak_at_center=True
                        )
                    elif (
                        distribution_profile == PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE
                    ):
                        day_props_in_month_list = get_weighted_proportions(
                            num_days_in_month_val,
                            WEIGHT_INITIAL_FACTOR_INC,
                            WEIGHT_FINAL_FACTOR_INC,
                        )
                    else:
                        day_props_in_month_list = [
                            1.0 / num_days_in_month_val
                        ] * num_days_in_month_val

                    month_start_day_idx_of_year = (
                        datetime.date(year, current_month_1based, 1)
                        - datetime.date(year, 1, 1)
                    ).days
                    for day_of_month_idx, prop in enumerate(day_props_in_month_list):
                        raw_daily_values[
                            month_start_day_idx_of_year + day_of_month_idx
                        ] = (month_sum_val * prop)

            elif (
                user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE
                and distribution_profile
                in [PROFILE_QUARTERLY_PROGRESSIVE, PROFILE_QUARTERLY_SINUSOIDAL]
            ):
                q_date_ranges = get_date_ranges_for_quarters(year)
                for q_idx_0based in range(4):
                    q_total_sum = period_allocations_map.get(q_idx_0based, 0)
                    if abs(q_total_sum) < 1e-9:
                        continue
                    q_start_date, q_end_date = q_date_ranges[q_idx_0based + 1]
                    num_days_in_q_val = (q_end_date - q_start_date).days + 1

                    day_props_in_q_list = []
                    if distribution_profile == PROFILE_QUARTERLY_PROGRESSIVE:
                        day_props_in_q_list = get_weighted_proportions(
                            num_days_in_q_val,
                            WEIGHT_INITIAL_FACTOR_INC,
                            WEIGHT_FINAL_FACTOR_INC,
                        )
                    elif distribution_profile == PROFILE_QUARTERLY_SINUSOIDAL:
                        day_props_in_q_list = get_parabolic_proportions(
                            num_days_in_q_val, peak_at_center=True
                        )
                    else:
                        day_props_in_q_list = [
                            1.0 / num_days_in_q_val
                        ] * num_days_in_q_val

                    q_start_day_idx_of_year = (
                        q_start_date - datetime.date(year, 1, 1)
                    ).days
                    for day_of_q_idx, prop in enumerate(day_props_in_q_list):
                        raw_daily_values[q_start_day_idx_of_year + day_of_q_idx] = (
                            q_total_sum * prop
                        )
        else:
            print(
                f"Profilo Incrementale '{distribution_profile}' non gestito per logica ripartizione '{user_repartition_logic}'. Default: annuale progressivo."
            )
            props = get_weighted_proportions(
                days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC
            )
            raw_daily_values = np.array([annual_target * p for p in props])

    # --- MEDIA KPI ---
    elif kpi_calc_type == CALC_TYPE_MEDIA:
        for d_idx, date_val in enumerate(all_dates_in_year):
            base_avg_for_day_from_repart = (
                annual_target  # Default annual average if no specific period multiplier
            )
            if user_repartition_logic == REPARTITION_LOGIC_MESE:
                base_avg_for_day_from_repart = (
                    annual_target * period_allocations_map.get(date_val.month - 1, 1.0)
                )
            elif user_repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
                base_avg_for_day_from_repart = (
                    annual_target * period_allocations_map.get(date_val.month - 1, 1.0)
                )
            elif user_repartition_logic == REPARTITION_LOGIC_SETTIMANA:
                iso_y, iso_w, _ = date_val.isocalendar()
                wk_key = f"{iso_y}-W{iso_w:02d}"
                base_avg_for_day_from_repart = (
                    annual_target * period_allocations_map.get(wk_key, 1.0)
                )

            if distribution_profile == PROFILE_EVEN:
                raw_daily_values[d_idx] = base_avg_for_day_from_repart
            elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE:
                factors_prog = np.linspace(
                    WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year
                )
                deviation = factors_prog[d_idx] - 1.0
                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (
                    1 + deviation * DEVIATION_SCALE_FACTOR_AVG
                )
            elif distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
                amp = profile_params.get("sine_amplitude", SINE_AMPLITUDE_MEDIA)
                phase = profile_params.get("sine_phase", SINE_PHASE_OFFSET)
                x_annual_sin = np.linspace(0, 2 * np.pi, days_in_year, endpoint=False)
                sine_mod = amp * np.sin(x_annual_sin[d_idx] + phase)
                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (1 + sine_mod)
            elif distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
                factors_bias = np.linspace(
                    WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year
                )
                deviation_bias = factors_bias[d_idx] - 1.0
                day_target_val_bias = base_avg_for_day_from_repart * (
                    1 + deviation_bias * DEVIATION_SCALE_FACTOR_AVG
                )
                if date_val.weekday() >= 5:
                    day_target_val_bias *= WEEKDAY_BIAS_FACTOR_MEDIA
                raw_daily_values[d_idx] = day_target_val_bias
            elif distribution_profile in [
                PROFILE_MONTHLY_SINUSOIDAL,
                PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
                PROFILE_QUARTERLY_PROGRESSIVE,
                PROFILE_QUARTERLY_SINUSOIDAL,
            ]:
                num_days_mod_period = 0
                day_idx_mod_period = 0
                if distribution_profile in [
                    PROFILE_MONTHLY_SINUSOIDAL,
                    PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
                ]:
                    num_days_mod_period = calendar.monthrange(year, date_val.month)[1]
                    day_idx_mod_period = date_val.day - 1
                elif distribution_profile in [
                    PROFILE_QUARTERLY_PROGRESSIVE,
                    PROFILE_QUARTERLY_SINUSOIDAL,
                ]:
                    q_idx_0based = (date_val.month - 1) // 3
                    q_ranges_mod = get_date_ranges_for_quarters(year)
                    q_start_mod, q_end_mod = q_ranges_mod[q_idx_0based + 1]
                    num_days_mod_period = (q_end_mod - q_start_mod).days + 1
                    day_idx_mod_period = (date_val - q_start_mod).days

                if num_days_mod_period == 0:
                    raw_daily_values[d_idx] = base_avg_for_day_from_repart
                    continue

                modulation_factor_val = 0.0
                if distribution_profile in [
                    PROFILE_MONTHLY_SINUSOIDAL,
                    PROFILE_QUARTERLY_SINUSOIDAL,
                ]:
                    par_weights_mod = np.zeros(num_days_mod_period)
                    mid_idx_mod = (num_days_mod_period - 1) / 2.0
                    for i_mod in range(num_days_mod_period):
                        par_weights_mod[i_mod] = (i_mod - mid_idx_mod) ** 2
                    par_weights_mod = np.max(par_weights_mod) - par_weights_mod
                    mean_w_mod = (
                        np.mean(par_weights_mod)
                        if num_days_mod_period > 1
                        else par_weights_mod[0]
                    )
                    norm_mod_val_calc = par_weights_mod[day_idx_mod_period] - mean_w_mod
                    max_abs_dev_mod = (
                        np.max(np.abs(par_weights_mod - mean_w_mod))
                        if num_days_mod_period > 1
                        else (
                            abs(par_weights_mod[0] - mean_w_mod)
                            if num_days_mod_period == 1
                            else 0
                        )
                    )
                    if max_abs_dev_mod > 1e-9:
                        norm_mod_val_calc /= max_abs_dev_mod
                    modulation_factor_val = (
                        norm_mod_val_calc * DEVIATION_SCALE_FACTOR_AVG
                    )
                elif distribution_profile in [
                    PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
                    PROFILE_QUARTERLY_PROGRESSIVE,
                ]:
                    factors_period_mod = np.linspace(
                        WEIGHT_INITIAL_FACTOR_AVG,
                        WEIGHT_FINAL_FACTOR_AVG,
                        num_days_mod_period,
                    )
                    deviation_period_mod = factors_period_mod[day_idx_mod_period] - 1.0
                    modulation_factor_val = (
                        deviation_period_mod * DEVIATION_SCALE_FACTOR_AVG
                    )
                raw_daily_values[d_idx] = base_avg_for_day_from_repart * (
                    1 + modulation_factor_val
                )
            else:
                print(
                    f"Profilo Media '{distribution_profile}' non gestito. Uso valore base del periodo."
                )
                raw_daily_values[d_idx] = base_avg_for_day_from_repart
    else:
        print(f"Tipo calcolo KPI sconosciuto: {kpi_calc_type}")
        # Potrebbe essere utile riempire con un valore di errore o lanciare un'eccezione
    return raw_daily_values


def _apply_event_adjustments_to_daily_values(raw_daily_values_input, event_data_list, kpi_calc_type, annual_target_for_norm, all_dates_in_year):
    if not event_data_list: return raw_daily_values_input

    adjusted_daily_values = np.copy(raw_daily_values_input)
    # days_in_year = len(all_dates_in_year) # Not directly used here but good for context

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
                        if abs(addition_event) > 1e-9: 
                            adjusted_daily_values[d_idx_event] += addition_event
        except (ValueError, KeyError, TypeError) as e_event_proc:
            print(f"Attenzione: Dati evento non validi o errore elaborazione, saltato. Dettagli: {event}, Errore: {e_event_proc}")
            continue

    if kpi_calc_type == CALC_TYPE_INCREMENTALE:
        current_total_after_events_val = np.sum(adjusted_daily_values)
        if abs(annual_target_for_norm) < 1e-9: 
            adjusted_daily_values.fill(0.0)
        elif abs(current_total_after_events_val) > 1e-9 : 
            adjusted_daily_values = (adjusted_daily_values / current_total_after_events_val) * annual_target_for_norm
    return adjusted_daily_values


def _aggregate_and_save_periodic_targets(
    daily_targets_list_of_tuples,
    year,
    stabilimento_id,
    kpi_id,
    target_number,
    kpi_calc_type,
):
    if not daily_targets_list_of_tuples:
        return

    with sqlite3.connect(DB_KPI_DAYS) as conn:
        conn.executemany(
            "INSERT INTO daily_targets (year,stabilimento_id,kpi_id,target_number,date_value,target_value) VALUES (?,?,?,?,?,?)",
            [
                (year, stabilimento_id, kpi_id, target_number, d.isoformat(), t)
                for d, t in daily_targets_list_of_tuples
            ],
        )
        conn.commit()

    weekly_agg_data = {}
    for date_val, daily_target_val in daily_targets_list_of_tuples:
        iso_y_cal, iso_w_num, _ = date_val.isocalendar()
        week_key_str = f"{iso_y_cal}-W{iso_w_num:02d}"
        if week_key_str not in weekly_agg_data:
            weekly_agg_data[week_key_str] = []
        weekly_agg_data[week_key_str].append(daily_target_val)
    db_week_recs = []
    for wk_key, tgts_in_wk_list in sorted(weekly_agg_data.items()):
        if not tgts_in_wk_list:
            continue
        wt_val = (
            sum(tgts_in_wk_list)
            if kpi_calc_type == CALC_TYPE_INCREMENTALE
            else (sum(tgts_in_wk_list) / len(tgts_in_wk_list) if tgts_in_wk_list else 0)
        )
        db_week_recs.append(
            (year, stabilimento_id, kpi_id, target_number, wk_key, wt_val)
        )
    if db_week_recs:
        with sqlite3.connect(DB_KPI_WEEKS) as conn:
            conn.executemany(
                "INSERT INTO weekly_targets (year,stabilimento_id,kpi_id,target_number,week_value,target_value) VALUES (?,?,?,?,?,?)",
                db_week_recs,
            )
            conn.commit()

    monthly_agg_data_map = {i: [] for i in range(12)}
    for date_val, daily_target_val in daily_targets_list_of_tuples:
        if date_val.year == year:
            monthly_agg_data_map[date_val.month - 1].append(daily_target_val)
    db_month_recs = []
    for month_idx_0based in range(12):
        tgts_in_m_list = monthly_agg_data_map[month_idx_0based]
        month_name_str = calendar.month_name[month_idx_0based + 1]
        mt_val = 0.0
        if tgts_in_m_list:
            mt_val = (
                sum(tgts_in_m_list)
                if kpi_calc_type == CALC_TYPE_INCREMENTALE
                else (
                    sum(tgts_in_m_list) / len(tgts_in_m_list) if tgts_in_m_list else 0
                )
            )
        db_month_recs.append(
            (year, stabilimento_id, kpi_id, target_number, month_name_str, mt_val)
        )
    if db_month_recs:
        with sqlite3.connect(DB_KPI_MONTHS) as conn:
            conn.executemany(
                "INSERT INTO monthly_targets (year,stabilimento_id,kpi_id,target_number,month_value,target_value) VALUES (?,?,?,?,?,?)",
                db_month_recs,
            )
            conn.commit()

    quarterly_agg_data_map = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
    actual_monthly_tgts_for_q_calc = {rec[4]: rec[5] for rec in db_month_recs}
    month_to_q_map_val = {
        calendar.month_name[i]: f"Q{((i-1)//3)+1}" for i in range(1, 13)
    }
    for mn_name_str, mt_val_for_q in actual_monthly_tgts_for_q_calc.items():
        if mn_name_str in month_to_q_map_val:
            quarterly_agg_data_map[month_to_q_map_val[mn_name_str]].append(mt_val_for_q)
    db_quarter_recs = []
    for qn_str in ["Q1", "Q2", "Q3", "Q4"]:
        tgts_in_q_list = quarterly_agg_data_map[qn_str]
        qt_val = 0.0
        if tgts_in_q_list:
            qt_val = (
                sum(tgts_in_q_list)
                if kpi_calc_type == CALC_TYPE_INCREMENTALE
                else (
                    sum(tgts_in_q_list) / len(tgts_in_q_list) if tgts_in_q_list else 0
                )
            )
        db_quarter_recs.append(
            (year, stabilimento_id, kpi_id, target_number, qn_str, qt_val)
        )
    if db_quarter_recs:
        with sqlite3.connect(DB_KPI_QUARTERS) as conn:
            conn.executemany(
                "INSERT INTO quarterly_targets (year,stabilimento_id,kpi_id,target_number,quarter_value,target_value) VALUES (?,?,?,?,?,?)",
                db_quarter_recs,
            )
            conn.commit()


def calculate_and_save_all_repartitions(
    year, stabilimento_id, kpi_id, target_number
):  # kpi_id is kpis.id
    target_info = get_annual_target(year, stabilimento_id, kpi_id)
    if not target_info:
        # print(f"WARN: Nessun target annuale trovato per KPI {kpi_id}, Anno {year}, Stab {stabilimento_id}, TargetNum {target_number}. Salto ripartizione.")
        return
    kpi_details = get_kpi_by_id(kpi_id)
    if not kpi_details:
        print(f"Dettagli KPI ID {kpi_id} non trovati. Salto ripartizione.")
        return

    annual_target_to_use = (
        target_info["annual_target1"]
        if target_number == 1
        else target_info["annual_target2"]
    )

    if annual_target_to_use is None or abs(annual_target_to_use) < 1e-9:
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

    user_repart_logic = target_info["repartition_logic"]
    user_repart_values = {}
    try:
        user_repart_values_str = target_info["repartition_values"]
        loaded_values = json.loads(user_repart_values_str or "{}")
        if isinstance(loaded_values, dict):
            user_repart_values = loaded_values
        else:
            print(
                f"WARN: Valori ripartizione per KPI {kpi_id} non sono un dizionario. Stringa: '{user_repart_values_str}'. Uso default."
            )
    except json.JSONDecodeError:
        print(
            f"WARN: Valori ripartizione JSON non validi per KPI {kpi_id}. Stringa: '{target_info['repartition_values']}'. Uso default."
        )

    kpi_calc_type = kpi_details["calculation_type"]
    distribution_profile = (
        target_info["distribution_profile"] or PROFILE_ANNUAL_PROGRESSIVE
    )

    profile_params = {}
    profile_params_json_str = "{}"
    try:
        # sqlite3.Row allows checking keys like a dictionary
        if "profile_params" in target_info.keys():  # Check if column name exists
            profile_params_json_str = target_info["profile_params"] or "{}"
        else:
            print(
                f"WARN: Colonna 'profile_params' non presente nei dati target per KPI {kpi_id}."
            )
    except Exception as e:  # Catch any other unexpected issue accessing the column
        print(
            f"WARN: Errore imprevisto nell'accesso a 'profile_params' per KPI {kpi_id}: {e}"
        )

    try:
        loaded_params = json.loads(profile_params_json_str)
        if isinstance(loaded_params, dict):
            profile_params = loaded_params
        else:
            print(
                f"WARN: Parametri profilo per KPI {kpi_id} non sono un dizionario. Stringa: '{profile_params_json_str}'. Uso default."
            )
    except json.JSONDecodeError:
        print(
            f"WARN: Parametri profilo JSON non validi per KPI {kpi_id}. Stringa: '{profile_params_json_str}'. Uso default."
        )

    for db_path_clear, table_name_clear in [
        (DB_KPI_DAYS, "daily_targets"),
        (DB_KPI_WEEKS, "weekly_targets"),
        (DB_KPI_MONTHS, "monthly_targets"),
        (DB_KPI_QUARTERS, "quarterly_targets"),
    ]:
        with sqlite3.connect(db_path_clear) as conn_clear:
            conn_clear.cursor().execute(
                f"DELETE FROM {table_name_clear} WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                (year, stabilimento_id, kpi_id, target_number),
            )
            conn_clear.commit()

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
        kpi_id,
        target_number,
        kpi_calc_type,
    )

    group_name_disp = kpi_details.get("group_name", "N/A")
    subgroup_name_disp = kpi_details.get("subgroup_name", "N/A")
    indicator_name_disp = kpi_details.get("indicator_name", "N/A")
    kpi_full_name_display = (
        f"{group_name_disp}>{subgroup_name_disp}>{indicator_name_disp}"
    )
    print(
        f"Ripartizioni per KPI '{kpi_full_name_display}' (ID:{kpi_id}), Target {target_number} (Profilo: {distribution_profile}, Logica Rip.: {user_repart_logic}) calcolate e salvate."
    )


# --- Funzioni di Lettura Dati Ripartiti ---
def get_ripartiti_data(year, stabilimento_id, kpi_id, period_type, target_number): # kpi_id is kpis.id
    db_map = {
        "Giorno": (DB_KPI_DAYS, "daily_targets", "date_value"),
        "Settimana": (DB_KPI_WEEKS, "weekly_targets", "week_value"),
        "Mese": (DB_KPI_MONTHS, "monthly_targets", "month_value"),
        "Trimestre": (DB_KPI_QUARTERS, "quarterly_targets", "quarter_value"),
    }
    if period_type not in db_map: raise ValueError(f"Tipo periodo non valido: {period_type}")
    db_path, table_name, period_col_name = db_map[period_type]
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        order_clause = f"ORDER BY {period_col_name}"
        if period_type == "Mese":
            month_order_cases = " ".join([f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1,13)])
            order_clause = f"ORDER BY CASE {period_col_name} {month_order_cases} END"
        elif period_type == "Trimestre":
            quarter_order_cases = " ".join([f"WHEN 'Q{i}' THEN {i}" for i in range(1,5)])
            order_clause = f"ORDER BY CASE {period_col_name} {quarter_order_cases} END"
        elif period_type == "Settimana":
             order_clause = f"ORDER BY SUBSTR({period_col_name}, 1, 4), CAST(SUBSTR({period_col_name}, INSTR({period_col_name}, '-W') + 2) AS INTEGER)"
        query = (f"SELECT {period_col_name} AS Periodo, target_value AS Target FROM {table_name} "
                 f"WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=? {order_clause}")
        cursor.execute(query, (year, stabilimento_id, kpi_id, target_number))
        return cursor.fetchall()

# --- Main Test Block ---
if __name__ == "__main__":
    print("Esecuzione di database_manager.py come script principale (per setup/test).")
    setup_databases()

    def _ensure_kpi_for_test(group_name, subgroup_name, indicator_name, calc_type, unit, subgroup_template_id=None):
        # This is a simplified helper for testing basic KPI setup, does not fully replicate all template logic nuances.
        # For full template testing, use the main module functions.
        try:
            group_id = add_kpi_group(group_name)
        except sqlite3.IntegrityError: # Group exists
            grps = get_kpi_groups()
            group_id = next((g['id'] for g in grps if g['name'] == group_name), None)
            if not group_id: raise Exception(f"Failed to get group_id for {group_name}")

        try:
            subgroup_id = add_kpi_subgroup(subgroup_name, group_id, subgroup_template_id)
        except sqlite3.IntegrityError: # Subgroup exists
            sgs = get_kpi_subgroups_by_group_revised(group_id)
            subgroup_id = next((sg['id'] for sg in sgs if sg['name'] == subgroup_name), None)
            if not subgroup_id: raise Exception(f"Failed to get subgroup_id for {subgroup_name}")
            # If subgroup exists and template ID needs to be set/changed, update_kpi_subgroup would be needed.

        actual_indicator_id = None
        if not subgroup_template_id: # Only add indicator manually if not templated (or template doesn't provide it)
            try:
                actual_indicator_id = add_kpi_indicator(indicator_name, subgroup_id)
            except sqlite3.IntegrityError: # Indicator exists
                inds = get_kpi_indicators_by_subgroup(subgroup_id)
                actual_indicator_id = next((i['id'] for i in inds if i['name'] == indicator_name), None)
                if not actual_indicator_id: raise Exception(f"Failed to get indicator_id for {indicator_name}")
        else: # If subgroup is templated, indicator should come from template. Find its ID.
            inds_from_template_subgroup = get_kpi_indicators_by_subgroup(subgroup_id)
            actual_indicator_id = next((i['id'] for i in inds_from_template_subgroup if i['name'] == indicator_name), None)
            if not actual_indicator_id:
                print(f"WARN (Test): Indicator '{indicator_name}' not found in templated subgroup '{subgroup_name}'. Test may fail if it relies on this specific indicator being manually added to a templated subgroup.")
                # For test purposes, if we are _ensure_kpi, we might still want to add it manually if it's missing from template application
                # This depends on the test's intent. For now, we assume template application is primary.
                return None


        if actual_indicator_id:
            # add_kpi handles insert or update of the kpis spec
            try:
                kpi_spec_id = add_kpi(actual_indicator_id, f"{indicator_name} ({calc_type})", calc_type, unit, True)
                return kpi_spec_id # This is kpis.id
            except Exception as e_add_spec:
                print(f"Error ensuring KPI spec for indicator {actual_indicator_id}: {e_add_spec}")
                # Try to fetch existing if add failed for other reasons but it might exist
                with sqlite3.connect(DB_KPIS) as conn:
                    row = conn.execute("SELECT id FROM kpis WHERE indicator_id=?",(actual_indicator_id,)).fetchone()
                    if row: return row[0]
                return None
        return None


    def _ensure_stabilimento_for_test(name):
        try:
            return add_stabilimento(name, True)
        except sqlite3.IntegrityError: # Stabilimento exists
            stabs = get_stabilimenti()
            return next((s['id'] for s in stabs if s['name'] == name), None)

    print("\n--- Inizio Test Logica Template KPI ---")
    try:
        template_name_test = "Standard Customer KPIs"
        try:
            customer_template_id = add_kpi_indicator_template(template_name_test, "A standard set.")
        except sqlite3.IntegrityError:
            tpls = get_kpi_indicator_templates()
            customer_template_id = next((t['id'] for t in tpls if t['name'] == template_name_test), None)
            # Clear existing definitions for a clean test run
            if customer_template_id:
                defs_to_clear = get_template_defined_indicators(customer_template_id)
                for d_clear in defs_to_clear: remove_indicator_definition_from_template(d_clear['id'])
        if not customer_template_id: raise Exception("Failed to create/find template for test")
        print(f"Template '{template_name_test}' ID: {customer_template_id}")

        add_indicator_definition_to_template(customer_template_id, "Official Claim Information", CALC_TYPE_INCREMENTALE, "Count", True, "Num official claims.")
        add_indicator_definition_to_template(customer_template_id, "Logistic Claim", CALC_TYPE_INCREMENTALE, "Count", True, "Num logistic claims.")
        
        group_name_tpl_test = "Customer Relations Test Dept"
        subgroup_name_retail_test = "Retail Customers Test"
        try: test_group_id_tpl = add_kpi_group(group_name_tpl_test)
        except sqlite3.IntegrityError: test_group_id_tpl = next((g['id'] for g in get_kpi_groups() if g['name'] == group_name_tpl_test), None)

        retail_subgroup_id_test = add_kpi_subgroup(subgroup_name_retail_test, test_group_id_tpl, customer_template_id)
        print(f"Creato sottogruppo '{subgroup_name_retail_test}' (ID: {retail_subgroup_id_test}) usando template ID {customer_template_id}.")
        retail_indicators_after_creation = get_kpi_indicators_by_subgroup(retail_subgroup_id_test)
        print(f"Indicatori in '{subgroup_name_retail_test}': {[i['name'] for i in retail_indicators_after_creation]}")
        assert len(retail_indicators_after_creation) == 2, "Retail subgroup should have 2 indicators from template initially."
        print("\n--- Fine Test Logica Template KPI ---")
    except Exception as e: print(f"ERRORE durante il test dei template KPI: {e}")

    kpi_id_inc_test = _ensure_kpi_for_test("TestGroupLegacy", "TestSubLegacy", "TestIndicatorIncLegacy", CALC_TYPE_INCREMENTALE, "Units")
    kpi_id_avg_test = _ensure_kpi_for_test("TestGroupLegacy", "TestSubLegacy", "TestIndicatorAvgLegacy", CALC_TYPE_MEDIA, "%")
    stab_id_test = _ensure_stabilimento_for_test("TestStabLegacy")
    test_year_main = datetime.datetime.now().year

    if kpi_id_inc_test and kpi_id_avg_test and stab_id_test:
        print("\n--- Inizio Test Logica Database con Nuovi Profili (Legacy KPIs) ---")
        days_this_year_for_test = (datetime.date(test_year_main, 12, 31) - datetime.date(test_year_main, 1, 1)).days + 1
        targets_even_inc = {
            kpi_id_inc_test: {"annual_target1": float(days_this_year_for_test * 10), "annual_target2": 0,
                              "repartition_logic": REPARTITION_LOGIC_ANNO, "repartition_values": {}, "distribution_profile": PROFILE_EVEN }}
        save_annual_targets(test_year_main, stab_id_test, targets_even_inc)
        print(f"\nTest Even Inc (Target 1: {targets_even_inc[kpi_id_inc_test]['annual_target1']}) - {test_year_main} - Giorno (Primi 5):")
        for row in get_ripartiti_data(test_year_main, stab_id_test, kpi_id_inc_test, "Giorno", 1)[:5]: print(f"  {row['Periodo']}: {row['Target']:.2f}")
        
        targets_sin_avg = {
            kpi_id_avg_test: {"annual_target1": 100, "annual_target2": 0, "repartition_logic": REPARTITION_LOGIC_ANNO,
                              "repartition_values": {}, "distribution_profile": PROFILE_TRUE_ANNUAL_SINUSOIDAL,
                              "profile_params": {"sine_amplitude": 0.15, "sine_phase": -np.pi/2} }}
        save_annual_targets(test_year_main, stab_id_test, targets_sin_avg)
        print(f"\nTest True Annual Sinusoidal Media (Target 1: 100) - {test_year_main} - Mese:")
        for row in get_ripartiti_data(test_year_main, stab_id_test, kpi_id_avg_test, "Mese", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")
        print("\n--- Fine Test Logica Database (Legacy KPIs) ---")
    else: print("\nATTENZIONE: KPI di test legacy o stabilimento non creati, salto i test di ripartizione.")
