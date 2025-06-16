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
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, group_id INTEGER NOT NULL,
                FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE, UNIQUE (name, group_id) )"""
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
                # This might happen if a previous attempt to add it failed midway or if it somehow exists already.
                # For robustness, we can check again if it exists now. If not, then there's a problem.
                cursor.execute("PRAGMA table_info(annual_targets)")
                if "profile_params" not in {col[1] for col in cursor.fetchall()}:
                    print("ERRORE: Impossibile aggiungere la colonna 'profile_params' a 'annual_targets'.")
                else:
                    print("Colonna 'profile_params' ora presente in 'annual_targets'.")

        # Check for other columns and recreate if schema is too old (simplistic migration)
        if not {"annual_target1", "annual_target2", "distribution_profile", "repartition_logic", "repartition_values"}.issubset(target_columns):
            print("Tabella 'annual_targets' con schema obsoleto, tentativo di ricreazione...")
            cursor.execute("DROP TABLE IF EXISTS annual_targets") # Use with caution on existing data
            cursor.execute(
                """ CREATE TABLE annual_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, stabilimento_id INTEGER NOT NULL, kpi_id INTEGER NOT NULL,
                    annual_target1 REAL NOT NULL DEFAULT 0, annual_target2 REAL NOT NULL DEFAULT 0,
                    repartition_logic TEXT NOT NULL,
                    repartition_values TEXT NOT NULL,
                    distribution_profile TEXT NOT NULL DEFAULT 'annual_progressive',
                    profile_params TEXT,
                    UNIQUE(year, stabilimento_id, kpi_id))"""
            )
            print("Tabella 'annual_targets' ricreata con nuovo schema.")
        conn.commit()
        print(f"Setup tabelle in {DB_TARGETS} completato.")


    # --- Periodic Target Databases Setup ---
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
                    {period_col_def.replace(' UNIQUE', '')}, /* Remove UNIQUE from definition if it was there by mistake */
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
        conn.execute("DELETE FROM kpi_groups WHERE id = ?", (group_id,))
        conn.commit()

def add_kpi_subgroup(name, group_id):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute(
                "INSERT INTO kpi_subgroups (name, group_id) VALUES (?,?)",
                (name, group_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"Sottogruppo '{name}' già esistente in questo gruppo.")
            raise

def get_kpi_subgroups_by_group(group_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM kpi_subgroups WHERE group_id = ? ORDER BY name", (group_id,)
        ).fetchall()

def update_kpi_subgroup(subgroup_id, new_name, group_id): # group_id might not be needed if not changing group
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            # Check if new name for this group_id would conflict
            # This check should ideally be done before the update if group_id can change
            conn.execute("UPDATE kpi_subgroups SET name = ? WHERE id = ?", (new_name, subgroup_id))
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento del sottogruppo: Nome '{new_name}' potrebbe già esistere in questo gruppo.")
            raise e

def delete_kpi_subgroup(subgroup_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.execute("DELETE FROM kpi_subgroups WHERE id = ?", (subgroup_id,))
        conn.commit()

def add_kpi_indicator(name, subgroup_id):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute(
                "INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)",
                (name, subgroup_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"Indicatore '{name}' già esistente in questo sottogruppo.")
            raise

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
            conn.execute("UPDATE kpi_indicators SET name = ? WHERE id = ?", (new_name, indicator_id))
            conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Errore durante l'aggiornamento dell'indicatore: Nome '{new_name}' potrebbe già esistere in questo sottogruppo.")
            raise e

def delete_kpi_indicator(indicator_id):
    kpi_spec = None
    with sqlite3.connect(DB_KPIS) as conn_kpis_read:
        conn_kpis_read.row_factory = sqlite3.Row
        kpi_spec = conn_kpis_read.execute("SELECT id FROM kpis WHERE indicator_id = ?", (indicator_id,)).fetchone()

    if kpi_spec:
        kpi_spec_id_to_delete = kpi_spec["id"]
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

    with sqlite3.connect(DB_KPIS) as conn: # Deletes kpis spec via cascade from kpi_indicators
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
    with sqlite3.connect(DB_KPIS) as conn:
        try:
            conn.execute(
                "INSERT INTO kpis (indicator_id,description,calculation_type,unit_of_measure,visible) VALUES (?,?,?,?,?)",
                (indicator_id, description, calculation_type, unit_of_measure, visible),
            )
            conn.commit()
        except sqlite3.IntegrityError as e: # Likely UNIQUE constraint on indicator_id
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
                          k.indicator_id, k.description, k.calculation_type, k.unit_of_measure, k.visible
                   FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id
                   JOIN kpi_subgroups sg ON i.subgroup_id = sg.id JOIN kpi_groups g ON sg.group_id = g.id
                   WHERE k.id = ?"""
        return conn.execute(query, (kpi_id,)).fetchone()


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
            record = get_annual_target(year, stabilimento_id, kpi_id)
            repartition_values_json = json.dumps(data.get("repartition_values", {}))
            distribution_profile = data.get("distribution_profile", "annual_progressive")
            profile_params_json = json.dumps(data.get("profile_params", {})) # New field
            annual_target1 = float(data.get("annual_target1", 0.0) or 0.0)
            annual_target2 = float(data.get("annual_target2", 0.0) or 0.0)
            repartition_logic = data.get("repartition_logic", "Anno") # Default to Anno if not specified

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
                        kpi_id,
                        annual_target1,
                        annual_target2,
                        repartition_logic,
                        repartition_values_json,
                        distribution_profile,
                        profile_params_json,
                    ),
                )
        conn.commit()

    for kpi_id_saved in targets_data.keys():
        calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved, 1)
        calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved, 2)

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
        # print(f"Nessun target annuale per KPI {kpi_id}, Anno {year}, Stab {stabilimento_id}, Target Num {target_number}")
        return
    kpi_details = get_kpi_by_id(kpi_id)
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
    ):  # Also handles if target is exactly 0.0
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
        # print(f"Target {target_number} per KPI {kpi_id} (Anno {year}, Stab {stabilimento_id}) è zero o nullo. Ripartizioni esistenti cancellate.")
        return

    user_repartition_logic = target_info[
        "repartition_logic"
    ]  # Mese, Trimestre, Settimana, Anno
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

    kpi_calc_type = kpi_details["calculation_type"]
    distribution_profile = (
        target_info["distribution_profile"]
        if target_info["distribution_profile"]
        else "annual_progressive"
    )

    # CORRECTED LINE HERE:
    profile_params_str = (
        target_info["profile_params"]
        if "profile_params" in target_info.keys()
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

    # Example: Extract event data if implementing event_based_spikes_or_dips
    # event_data = profile_params.get("events", [])
    # custom_sine_amplitude = profile_params.get("sine_amplitude", SINE_AMPLITUDE_MEDIA if kpi_calc_type == "Media" else SINE_AMPLITUDE_INCREMENTAL)
    # custom_sine_phase = profile_params.get("sine_phase", SINE_PHASE_OFFSET)

    # Clear existing periodic targets for this combo
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

    raw_daily_values = np.zeros(days_in_year) # This will hold the calculated target for each day of the year

    # --- Stage 1: Determine Period Targets (if repartition_logic is not 'Anno') ---
    # period_targets will store the total target sum (for Incremental) or base average (for Media) for each period.
    # For Incremental: key = period_id (month_idx, quarter_idx, week_str), value = target_sum for this period
    # For Media: key = period_id, value = multiplier for annual_target_to_use for this period
    period_allocations = {}

    if kpi_calc_type == "Incrementale":
        if user_repartition_logic == "Mese":
            proportions = [user_repartition_values.get(calendar.month_name[i+1], 0)/100.0 for i in range(12)]
            current_sum = sum(proportions)
            if abs(current_sum - 1.0) > 0.01 and current_sum > 1e-9: # Normalize if not 100% and not all zero
                proportions = [p / current_sum for p in proportions]
            elif current_sum < 1e-9: # All zero, so distribute evenly
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

            if num_defined_weeks == 0: # Default to even across all ISO weeks if none defined
                num_iso_weeks_in_year = datetime.date(year, 12, 28).isocalendar()[1]
                default_prop = 1.0 / num_iso_weeks_in_year if num_iso_weeks_in_year > 0 else 0
                temp_period_targets = {}
                for d_val in all_dates_in_year: # Assign target to week based on its days
                    iso_y, iso_w, _ = d_val.isocalendar()
                    wk_key = f"{iso_y}-W{iso_w:02d}"
                    if wk_key not in temp_period_targets : temp_period_targets[wk_key] = 0
                    # This is an approximation for now, better to assign total week prop then distribute
                for wk_key in temp_period_targets: # Placeholder for proper distribution
                    period_allocations[wk_key] = annual_target_to_use * default_prop
            else:
                for week_str, prop_val_str in user_repartition_values.items():
                    try:
                        prop_val = float(prop_val_str) / 100.0
                        # Validate week format YYYY-Www
                        datetime.datetime.strptime(week_str + '-1', "%Y-W%W-%w") 
                        if abs(total_prop - 1.0) > 0.01 and total_prop > 1e-9: # Normalize
                            period_allocations[week_str] = annual_target_to_use * (prop_val / total_prop)
                        else: # Use directly or if sum is zero (implies even distribution later if profile allows)
                            period_allocations[week_str] = annual_target_to_use * prop_val
                    except (ValueError, TypeError):
                        print(f"Attenzione: Formato settimana o valore non valido per '{week_str}': '{prop_val_str}', saltato.")
        # If 'Anno' or no valid repartition, annual_target_to_use is the main sum.

    elif kpi_calc_type == "Media": # For Media, period_allocations stores multipliers
        if user_repartition_logic == "Mese":
            for i in range(12):
                period_allocations[i] = user_repartition_values.get(calendar.month_name[i+1], 100.0)/100.0
        elif user_repartition_logic == "Trimestre":
            q_map_indices = [[0,1,2], [3,4,5], [6,7,8], [9,10,11]]
            for q_idx in range(4):
                q_multiplier = user_repartition_values.get(f"Q{q_idx+1}", 100.0)/100.0
                for month_idx_in_year in q_map_indices[q_idx]:
                    period_allocations[month_idx_in_year] = q_multiplier # Store by month for easier daily lookup
        elif user_repartition_logic == "Settimana":
            for week_str, mult_val_str in user_repartition_values.items():
                try:
                    mult_val = float(mult_val_str) / 100.0
                    datetime.datetime.strptime(week_str + '-1', "%Y-W%W-%w")
                    period_allocations[week_str] = mult_val
                except (ValueError, TypeError):
                    print(f"Attenzione: Formato settimana o valore non valido per '{week_str}' in Media: '{mult_val_str}', saltato.")
        # If 'Anno', all multipliers are effectively 1.0.

    # --- Stage 2: Distribute target within periods (or over the year) using selected profile ---
    if kpi_calc_type == "Incrementale":
        if distribution_profile == "even_distribution":
            if user_repartition_logic == "Anno" or not period_allocations:
                daily_val = annual_target_to_use / days_in_year if days_in_year > 0 else 0
                raw_daily_values.fill(daily_val)
            else: # Distribute period sum evenly within that period
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
            props = get_sinusoidal_proportions(days_in_year, SINE_AMPLITUDE_INCREMENTAL, SINE_PHASE_OFFSET)
            for i in range(days_in_year): raw_daily_values[i] = annual_target_to_use * props[i]

        elif distribution_profile == "annual_progressive_weekday_bias":
            base_props = get_weighted_proportions(days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
            adj_props = np.array([base_props[i] * (WEEKDAY_BIAS_FACTOR_INCREMENTAL if all_dates_in_year[i].weekday() >= 5 else 1.0) for i in range(days_in_year)])
            current_sum = np.sum(adj_props)
            final_props = (adj_props / current_sum) if current_sum > 1e-9 else [1.0/days_in_year]*days_in_year
            for i in range(days_in_year): raw_daily_values[i] = annual_target_to_use * final_props[i]

        # Profiles that work on pre-allocated period sums:
        elif distribution_profile in ["monthly_sinusoidal", "legacy_intra_period_progressive", "quarterly_progressive", "quarterly_sinusoidal"]:
            if (user_repartition_logic == "Mese" or (user_repartition_logic == "Trimestre" and distribution_profile in ["monthly_sinusoidal", "legacy_intra_period_progressive"])) :
                # These profiles need monthly sums first
                monthly_target_sums_final = [0.0] * 12
                if user_repartition_logic == "Mese":
                    for m_idx in range(12): monthly_target_sums_final[m_idx] = period_allocations.get(m_idx,0)
                elif user_repartition_logic == "Trimestre": # Distribute quarter sum to its months before daily
                    q_map = [[0,1,2], [3,4,5], [6,7,8], [9,10,11]]
                    for q_idx, months_in_q_indices in enumerate(q_map):
                        q_total = period_allocations.get(q_idx, 0)
                        num_m = len(months_in_q_indices)
                        month_weights = get_weighted_proportions(num_m, 1, 1) # Even by default
                        if distribution_profile == "legacy_intra_period_progressive": # Special case from original
                            month_weights = get_weighted_proportions(num_m, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
                        for i, m_idx_year in enumerate(months_in_q_indices):
                            monthly_target_sums_final[m_idx_year] = q_total * month_weights[i]

                # Now distribute each month's sum to its days based on profile
                for month_idx, month_sum in enumerate(monthly_target_sums_final):
                    current_m = month_idx + 1
                    num_days_m = calendar.monthrange(year, current_m)[1]
                    if num_days_m == 0 or abs(month_sum) < 1e-9: continue

                    day_props_in_month = []
                    if distribution_profile == "monthly_sinusoidal":
                        day_props_in_month = get_parabolic_proportions(num_days_m, peak_at_center=True)
                    elif distribution_profile == "legacy_intra_period_progressive":
                        day_props_in_month = get_weighted_proportions(num_days_m, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
                    else: # Fallback should not be reached if logic is correct
                        day_props_in_month = [1.0/num_days_m] * num_days_m

                    month_start_day_idx_of_year = (datetime.date(year, current_m, 1) - datetime.date(year,1,1)).days
                    for day_of_m_idx, prop in enumerate(day_props_in_month):
                        raw_daily_values[month_start_day_idx_of_year + day_of_m_idx] = month_sum * prop

            elif user_repartition_logic == "Trimestre" and distribution_profile in ["quarterly_progressive", "quarterly_sinusoidal"]:
                q_date_ranges = get_date_ranges_for_quarters(year)
                for q_idx in range(4): # 0 for Q1, etc.
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
            # Note: weekly repartition with these complex profiles might require specific logic if needed
        else: # Default/Unknown Incremental profile
            print(f"Profilo Incrementale '{distribution_profile}' non gestito specificamente con logica ripartizione '{user_repartition_logic}'. Uso annuale progressivo.")
            props = get_weighted_proportions(days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC)
            for i in range(days_in_year): raw_daily_values[i] = annual_target_to_use * props[i]

    elif kpi_calc_type == "Media":
        # For Media, we establish a base daily average, then modulate it.
        # The base average can be annual, or specific to month/quarter/week if repartitioned.
        for d_idx, date_val in enumerate(all_dates_in_year):
            base_avg_for_day = annual_target_to_use # Default annual average
            if user_repartition_logic == "Mese":
                base_avg_for_day = annual_target_to_use * period_allocations.get(date_val.month - 1, 1.0)
            elif user_repartition_logic == "Trimestre": # period_allocations for Media/Trimestre is stored by month_idx
                base_avg_for_day = annual_target_to_use * period_allocations.get(date_val.month - 1, 1.0)
            elif user_repartition_logic == "Settimana":
                iso_y, iso_w, _ = date_val.isocalendar()
                wk_key = f"{iso_y}-W{iso_w:02d}"
                base_avg_for_day = annual_target_to_use * period_allocations.get(wk_key, 1.0)

            # Apply profile modulation
            if distribution_profile == "even_distribution":
                raw_daily_values[d_idx] = base_avg_for_day

            elif distribution_profile == "annual_progressive":
                # This profile uses its own annual factors, overriding period-specific base averages for modulation.
                factors = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year)
                mean_f = np.mean(factors) if days_in_year > 1 else factors[0]
                norm_mod = (factors[d_idx] - mean_f) if days_in_year > 1 else 0
                # Scale factor should represent a percentage deviation for AVG types
                # e.g. if factor is 0.8, it means target * (1 - (1-0.8)*scale)
                # if factor is 1.2, it means target * (1 + (1.2-1)*scale)
                effective_deviation = (factors[d_idx] - 1.0) # centered around 1.0
                raw_daily_values[d_idx] = annual_target_to_use * (1 + effective_deviation * DEVIATION_SCALE_FACTOR_AVG)

            elif distribution_profile == "true_annual_sinusoidal":
                x = np.linspace(0, 2 * np.pi, days_in_year, endpoint=False)
                sine_modulation = SINE_AMPLITUDE_MEDIA * np.sin(x[d_idx] + SINE_PHASE_OFFSET) # Centered around 0
                raw_daily_values[d_idx] = annual_target_to_use * (1 + sine_modulation) # Apply to main annual target

            elif distribution_profile == "annual_progressive_weekday_bias":
                factors = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year)
                effective_deviation = (factors[d_idx] - 1.0)
                day_target = annual_target_to_use * (1 + effective_deviation * DEVIATION_SCALE_FACTOR_AVG)
                if date_val.weekday() >= 5: day_target *= WEEKDAY_BIAS_FACTOR_MEDIA
                raw_daily_values[d_idx] = day_target

            elif distribution_profile in ["monthly_sinusoidal", "legacy_intra_period_progressive", "quarterly_progressive", "quarterly_sinusoidal"]:
                # These modulate the `base_avg_for_day` which is already period-specific
                num_days_in_mod_period = 0
                day_idx_in_mod_period = 0

                # Determine the period for modulation (month or quarter)
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

                modulation_value = 0 # This will be the +/- part of target * (1 +/- modulation_value)
                if distribution_profile == "monthly_sinusoidal" or distribution_profile == "quarterly_sinusoidal":
                    # Parabolic modulation for Media
                    par_weights = np.zeros(num_days_in_mod_period)
                    mid_idx = (num_days_in_mod_period -1)/2.0
                    for i in range(num_days_in_mod_period): par_weights[i] = (i-mid_idx)**2
                    par_weights = np.max(par_weights) - par_weights # Peak at center

                    mean_w = np.mean(par_weights) if num_days_in_mod_period > 1 else par_weights[0]
                    norm_mod_factor = (par_weights[day_idx_in_mod_period] - mean_w)
                    max_abs_dev = np.max(np.abs(par_weights - mean_w))
                    if max_abs_dev > 1e-9: norm_mod_factor /= max_abs_dev # Scale to [-1, 1] range
                    modulation_value = norm_mod_factor * DEVIATION_SCALE_FACTOR_AVG

                elif distribution_profile == "legacy_intra_period_progressive" or distribution_profile == "quarterly_progressive":
                    # Linear modulation for Media
                    factors_period = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, num_days_in_mod_period)
                    effective_deviation_period = (factors_period[day_idx_in_mod_period] - 1.0) # Based on 0.8 to 1.2 range
                    modulation_value = effective_deviation_period * DEVIATION_SCALE_FACTOR_AVG

                raw_daily_values[d_idx] = base_avg_for_day * (1 + modulation_value)
            else: # Default/Unknown Media profile
                print(f"Profilo Media '{distribution_profile}' non gestito. Uso valore base del periodo.")
                raw_daily_values[d_idx] = base_avg_for_day
    else:
        print(f"Tipo calcolo KPI sconosciuto: {kpi_calc_type}")
        return

    # --- Conceptual: Apply event_based_spikes_or_dips ---
    # This would involve parsing profile_params.get("events", [])
    # And then iterating through all_dates_in_year, checking if a date falls into an event range.
    # If so, apply multiplier or fixed addition to raw_daily_values[d_idx].
    # For Incremental, a re-normalization step would be needed to ensure sum(raw_daily_values) == annual_target_to_use.
    # For Media, direct application is usually fine.
    # Example:
    # event_data = profile_params.get("events", [])
    # if event_data:
    #     temp_values = np.copy(raw_daily_values)
    #     for event in event_data:
    #         start_event = datetime.datetime.strptime(event['start_date'], '%Y-%m-%d').date()
    #         end_event = datetime.datetime.strptime(event['end_date'], '%Y-%m-%d').date()
    #         multiplier = float(event.get('multiplier', 1.0))
    #         addition = float(event.get('addition', 0.0))
    #         for d_idx, date_val in enumerate(all_dates_in_year):
    #             if start_event <= date_val <= end_event:
    #                 temp_values[d_idx] = temp_values[d_idx] * multiplier + addition
    #     if kpi_calc_type == "Incrementale":
    #         current_total = np.sum(temp_values)
    #         if abs(current_total) > 1e-9 and abs(annual_target_to_use) > 1e-9: # Avoid div by zero if target is zero
    #             raw_daily_values = (temp_values / current_total) * annual_target_to_use
    #         elif abs(annual_target_to_use) < 1e-9 : # if target is zero, all days should be zero
    #             raw_daily_values.fill(0.0)
    #         # else: if current_total is zero but target is not, there's an issue / keep un-evented
    #     else: # Media
    #         raw_daily_values = temp_values

    # --- Final daily_targets_values list ---
    daily_targets_values = [(all_dates_in_year[i], raw_daily_values[i]) for i in range(days_in_year)]

    # --- Save daily targets ---
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

    # --- Aggregate and Save for Weeks, Months, Quarters ---
    weekly_agg_data = {} # Key: "YYYY-Www", Value: list of daily targets
    for date_val, daily_target_val in daily_targets_values:
        iso_year_calendar, iso_week_number, _ = date_val.isocalendar()
        # Ensure week numbers are consistent if year boundary is involved; isocalendar handles this well.
        week_key = f"{iso_year_calendar}-W{iso_week_number:02d}"
        if week_key not in weekly_agg_data:
            weekly_agg_data[week_key] = []
        weekly_agg_data[week_key].append(daily_target_val)

    db_week_recs = []
    # Sort weeks naturally for consistent insertion order
    sorted_week_keys = sorted(weekly_agg_data.keys(), key=lambda wk: (int(wk.split('-W')[0]), int(wk.split('-W')[1])))

    for wk in sorted_week_keys:
        tgts_in_wk = weekly_agg_data[wk]
        if not tgts_in_wk: continue # Should not happen if daily targets exist for those days
        wt = (
            sum(tgts_in_wk)
            if kpi_calc_type == "Incrementale"
            else (sum(tgts_in_wk) / len(tgts_in_wk) if tgts_in_wk else 0)
        )
        # The 'year' field for weekly_targets should align with the annual target's year,
        # even if iso_year_calendar is different for some days (e.g., late Dec/early Jan).
        # The week_key itself (YYYY-Www) correctly identifies the ISO week.
        db_week_recs.append((year, stabilimento_id, kpi_id, target_number, wk, wt))
    if db_week_recs:
        with sqlite3.connect(DB_KPI_WEEKS) as conn:
            conn.executemany(
                "INSERT INTO weekly_targets (year,stabilimento_id,kpi_id,target_number,week_value,target_value) VALUES (?,?,?,?,?,?)",
                db_week_recs,
            )
            conn.commit()

    monthly_agg_data = {i: [] for i in range(12)} # Key: month_idx (0-11), Value: list of daily targets
    for date_val, daily_target_val in daily_targets_values:
        if date_val.year == year: # Only aggregate days belonging to the target year for monthly totals
            monthly_agg_data[date_val.month - 1].append(daily_target_val)

    db_month_recs = []
    for month_idx in range(12): # Iterate in calendar order
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

    # Quarterly aggregation based on the *calculated monthly targets* for consistency
    quarterly_agg_data = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
    # Use the monthly targets we just stored/prepared for DB
    actual_monthly_tgts_for_q_calc = {rec[4]: rec[5] for rec in db_month_recs} # month_name: month_target

    month_to_q_map = { calendar.month_name[i]: f"Q{((i-1)//3)+1}" for i in range(1, 13) }
    for mn_name, mt_val in actual_monthly_tgts_for_q_calc.items():
        if mn_name in month_to_q_map: # Should always be true
            quarterly_agg_data[month_to_q_map[mn_name]].append(mt_val)

    db_quarter_recs = []
    for qn in ["Q1", "Q2", "Q3", "Q4"]: # Iterate in calendar order
        tgts_in_q = quarterly_agg_data[qn] # These are monthly totals/averages for the quarter
        qt = 0.0
        if tgts_in_q: # tgts_in_q contains 3 monthly values for that quarter
            qt = (
                sum(tgts_in_q) # Sum of monthly totals for Incremental
                if kpi_calc_type == "Incrementale"
                else (sum(tgts_in_q) / len(tgts_in_q) if tgts_in_q else 0) # Average of monthly averages for Media
            )
        db_quarter_recs.append((year, stabilimento_id, kpi_id, target_number, qn, qt))
    if db_quarter_recs:
        with sqlite3.connect(DB_KPI_QUARTERS) as conn:
            conn.executemany(
                "INSERT INTO quarterly_targets (year,stabilimento_id,kpi_id,target_number,quarter_value,target_value) VALUES (?,?,?,?,?,?)",
                db_quarter_recs,
            )
            conn.commit()

    group_name_disp = (
        kpi_details["group_name"]
        if "group_name" in kpi_details.keys() and kpi_details["group_name"]
        else "N/A"
    )
    subgroup_name_disp = (
        kpi_details["subgroup_name"]
        if "subgroup_name" in kpi_details.keys() and kpi_details["subgroup_name"]
        else "N/A"
    )
    indicator_name_disp = (
        kpi_details["indicator_name"]
        if "indicator_name" in kpi_details.keys() and kpi_details["indicator_name"]
        else "N/A"
    )

    kpi_full_name_display = (
        f"{group_name_disp}>{subgroup_name_disp}>{indicator_name_disp}"
    )

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
        
        order_clause = f"ORDER BY {period_col_name}" # Default sort
        if period_type == "Mese":
            month_order_cases = " ".join([f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1,13)])
            order_clause = f"ORDER BY CASE {period_col_name} {month_order_cases} END"
        elif period_type == "Trimestre":
            quarter_order_cases = " ".join([f"WHEN 'Q{i}' THEN {i}" for i in range(1,5)])
            order_clause = f"ORDER BY CASE {period_col_name} {quarter_order_cases} END"
        elif period_type == "Settimana": # Sort naturally by YYYY-Www, e.g., 2023-W52 then 2024-W01
             order_clause = f"ORDER BY SUBSTR({period_col_name}, 1, 4), CAST(SUBSTR({period_col_name}, 7) AS INTEGER)"

        query = (
            f"SELECT {period_col_name} AS Periodo, target_value AS Target FROM {table_name} "
            f"WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=? {order_clause}"
        )
        cursor.execute(query, (year, stabilimento_id, kpi_id, target_number))
        return cursor.fetchall()


if __name__ == "__main__":
    print("Esecuzione di database_manager.py come script principale (per setup/test).")
    setup_databases()

    # --- Utility to add kpi/stabilimento for testing ---
    def _ensure_kpi(conn_kpis_main, group_name, subgroup_name, indicator_name, calc_type, unit):
        # Check if connection is a path or a connection object
        is_path = isinstance(conn_kpis_main, (str, Path))
        conn_kpis = sqlite3.connect(conn_kpis_main) if is_path else conn_kpis_main
        
        cursor = conn_kpis.cursor()
        try:
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
                cursor.execute("INSERT INTO kpi_subgroups (name, group_id) VALUES (?,?)", (subgroup_name, group_id))
                subgroup_id = cursor.lastrowid
            else:
                subgroup_id = subgroup[0]
            
            cursor.execute("SELECT id FROM kpi_indicators WHERE name=? AND subgroup_id=?", (indicator_name, subgroup_id))
            indicator = cursor.fetchone()
            if not indicator:
                cursor.execute("INSERT INTO kpi_indicators (name, subgroup_id) VALUES (?,?)", (indicator_name, subgroup_id))
                indicator_id = cursor.lastrowid
            else:
                indicator_id = indicator[0]

            cursor.execute("SELECT id FROM kpis WHERE indicator_id=?", (indicator_id,))
            kpi = cursor.fetchone()
            if not kpi:
                cursor.execute("INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible) VALUES (?,?,?,?,?)",
                               (indicator_id, f"{indicator_name} ({calc_type})", calc_type, unit, True))
                kpi_id = cursor.lastrowid
            else:
                kpi_id = kpi[0]
                cursor.execute("UPDATE kpis SET calculation_type=?, unit_of_measure=? WHERE id=?", (calc_type, unit, kpi_id))
            if is_path: conn_kpis.commit() # Commit only if we opened the connection
            return kpi_id
        finally:
            if is_path: conn_kpis.close()


    def _ensure_stabilimento(conn_stab_main, name):
        is_path = isinstance(conn_stab_main, (str, Path))
        conn_stab = sqlite3.connect(conn_stab_main) if is_path else conn_stab_main
        cursor = conn_stab.cursor()
        try:
            cursor.execute("SELECT id FROM stabilimenti WHERE name=?", (name,))
            stab = cursor.fetchone()
            if not stab:
                cursor.execute("INSERT INTO stabilimenti (name, visible) VALUES (?,?)", (name, True))
                stab_id = cursor.lastrowid
            else:
                stab_id = stab[0]
            if is_path: conn_stab.commit()
            return stab_id
        finally:
            if is_path: conn_stab.close()

    # Use paths for _ensure functions if they manage their own connections
    kpi_id_inc_test = _ensure_kpi(DB_KPIS, "TestGroupNew", "TestSubNew", "TestIndicatorIncNew", "Incrementale", "Units")
    kpi_id_avg_test = _ensure_kpi(DB_KPIS, "TestGroupNew", "TestSubNew", "TestIndicatorAvgNew", "Media", "%")
    stab_id_test = _ensure_stabilimento(DB_STABILIMENTI, "TestStabNew")

    test_year_main = datetime.datetime.now().year if datetime.datetime.now().month < 10 else datetime.datetime.now().year + 1


    print("\n--- Inizio Test Logica Database con Nuovi Profili ---")

    # Test 1: Even Distribution - Incrementale
    days_this_year_for_test = (datetime.date(test_year_main, 12, 31) - datetime.date(test_year_main, 1, 1)).days + 1
    targets_even_inc = {
        kpi_id_inc_test: {
            "annual_target1": float(days_this_year_for_test * 10), "annual_target2": 0, # 10 per day
            "repartition_logic": "Anno", 
            "repartition_values": {},
            "distribution_profile": "even_distribution"
        }
    }
    save_annual_targets(test_year_main, stab_id_test, targets_even_inc)
    print(f"\nTest Even Inc (Target 1: {targets_even_inc[kpi_id_inc_test]['annual_target1']}) - {test_year_main} - Giorno (Primi 5):")
    daily_data = get_ripartiti_data(test_year_main, stab_id_test, kpi_id_inc_test, "Giorno", 1)
    for row in daily_data[:5]: print(f"  {row['Periodo']}: {row['Target']:.2f}")
    print(f"Test Even Inc - {test_year_main} - Mese:")
    for row in get_ripartiti_data(test_year_main, stab_id_test, kpi_id_inc_test, "Mese", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")


    # Test 2: True Annual Sinusoidal - Media
    targets_sin_avg = {
        kpi_id_avg_test: {
            "annual_target1": 100, "annual_target2": 0,
            "repartition_logic": "Anno",
            "repartition_values": {},
            "distribution_profile": "true_annual_sinusoidal",
            "profile_params": {"sine_amplitude": 0.15, "sine_phase": -np.pi/2} # Example custom params
        }
    }
    # Note: calculate_and_save_all_repartitions needs to be updated to use profile_params for SINE_AMPLITUDE etc.
    # For now, it will use the hardcoded defaults in the script.
    save_annual_targets(test_year_main, stab_id_test, targets_sin_avg)
    print(f"\nTest True Annual Sinusoidal Media (Target 1: 100) - {test_year_main} - Giorno (Primi 3, Mid 3, Ultimi 3):")
    daily_data = get_ripartiti_data(test_year_main, stab_id_test, kpi_id_avg_test, "Giorno", 1)
    if len(daily_data) > 6:
        for row in daily_data[:3]: print(f"  {row['Periodo']}: {row['Target']:.2f}")
        print("  ...")
        mid_idx = len(daily_data)//2 -1
        if mid_idx < 0: mid_idx=0
        for row in daily_data[mid_idx:min(mid_idx+3, len(daily_data))]: print(f"  {row['Periodo']}: {row['Target']:.2f}")
        print("  ...")
        for row in daily_data[-3:]: print(f"  {row['Periodo']}: {row['Target']:.2f}")
    print(f"Test True Annual Sinusoidal Media - {test_year_main} - Mese:")
    for row in get_ripartiti_data(test_year_main, stab_id_test, kpi_id_avg_test, "Mese", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")


    # Test 3: Quarterly Progressive - Incrementale
    targets_q_prog_inc = {
        kpi_id_inc_test: {
            "annual_target1": 4000, "annual_target2": 0,
            "repartition_logic": "Trimestre",
            "repartition_values": {"Q1": 25, "Q2": 30, "Q3": 20, "Q4": 25}, # Sums to 100% -> 1000, 1200, 800, 1000
            "distribution_profile": "quarterly_progressive"
        }
    }
    save_annual_targets(test_year_main, stab_id_test, targets_q_prog_inc)
    print(f"\nTest Quarterly Progressive Inc (Target 1: 4000 total) - {test_year_main} - Trimestre:")
    for row in get_ripartiti_data(test_year_main, stab_id_test, kpi_id_inc_test, "Trimestre", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")
    print(f"Test Quarterly Progressive Inc - {test_year_main} - Mese (Mostra primi 2 mesi di Q1 e Q2 per vedere trend):")
    monthly_data = get_ripartiti_data(test_year_main, stab_id_test, kpi_id_inc_test, "Mese", 1)
    # Filter for first two months of Q1 (Jan, Feb) and Q2 (Apr, May)
    months_to_show = [calendar.month_name[1], calendar.month_name[2], calendar.month_name[4], calendar.month_name[5]]
    for row in monthly_data:
        if row['Periodo'] in months_to_show:
            print(f"  {row['Periodo']}: {row['Target']:.2f}")


    # Test 4: Repartition by Settimana - Incrementale, Even daily within week
    num_iso_weeks_in_year = datetime.date(test_year_main, 12, 28).isocalendar()[1]
    weekly_repart_values = {}
    if num_iso_weeks_in_year > 0:
        perc_per_week = 100.0 / num_iso_weeks_in_year
        # Simulate some variation
        for w_num in range(1, num_iso_weeks_in_year + 1):
            iso_y_for_week = test_year_main
            # Handle weeks that span year boundaries if generating keys. isocalendar() on a date gives correct YYYY for that week.
            # For simplicity, assuming all weeks are within test_year_main for defining repartition_values keys.
            wk_key_test = f"{test_year_main}-W{w_num:02d}"
            if w_num <= num_iso_weeks_in_year // 2:
                 weekly_repart_values[wk_key_test] = perc_per_week * 1.1 # Front load a bit
            else:
                 weekly_repart_values[wk_key_test] = perc_per_week * 0.9 # Back load less
        # Normalize weekly_repart_values to sum to 100
        current_total_perc = sum(weekly_repart_values.values())
        if abs(current_total_perc - 100.0)>0.01 and current_total_perc > 1e-9:
            for wk_k in weekly_repart_values: weekly_repart_values[wk_k] = (weekly_repart_values[wk_k] / current_total_perc) * 100.0

    targets_week_repart_inc = {
        kpi_id_inc_test: {
            "annual_target1": 5200, "annual_target2": 0, # Approx 100 per week if 52 weeks
            "repartition_logic": "Settimana",
            "repartition_values": weekly_repart_values,
            "distribution_profile": "even_distribution" # Distributes week's sum evenly over its days
        }
    }
    save_annual_targets(test_year_main, stab_id_test, targets_week_repart_inc)
    print(f"\nTest Repartition by Settimana Inc (Target 1: 5200) - {test_year_main} - Settimana (Primi 5):")
    weekly_data = get_ripartiti_data(test_year_main, stab_id_test, kpi_id_inc_test, "Settimana", 1)
    for row in weekly_data[:5]: print(f"  {row['Periodo']}: {row['Target']:.2f}")


    # Test 5: Monthly Sinusoidal Refined for Media (parabolic daily modulation)
    targets_monthly_sin_media_refined = {
         kpi_id_avg_test: {
            "annual_target1": 50, "annual_target2": 0,
            "repartition_logic": "Mese", 
            "repartition_values": { # These are multipliers for the annual_target_to_use (e.g. 80 means 0.8 * 50 = 40 for Jan avg)
                "January": 80, "February": 90, "March": 100, "April": 110, 
                "May": 120, "June": 130, "July": 120, "August": 110,
                "September": 100, "October": 90, "November": 80, "December": 70
            },
            "distribution_profile": "monthly_sinusoidal"
        }
    }
    save_annual_targets(test_year_main, stab_id_test, targets_monthly_sin_media_refined)
    print(f"\nTest Monthly Sinusoidal Media (Refined, Parabolic Daily) - {test_year_main} - Mese:")
    for row in get_ripartiti_data(test_year_main, stab_id_test, kpi_id_avg_test, "Mese", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")
    
    print(f"Test Monthly Sinusoidal Media (Refined) - {test_year_main} - Giorno (Gennaio primi 5 e ultimi 5 per vedere parabola):")
    daily_data_full_year = get_ripartiti_data(test_year_main, stab_id_test, kpi_id_avg_test, "Giorno", 1)
    daily_data_jan = [r for r in daily_data_full_year if r["Periodo"].startswith(f"{test_year_main}-01-")]
    if daily_data_jan:
        for row in daily_data_jan[:5]: print(f"  {row['Periodo']}: {row['Target']:.3f}")
        if len(daily_data_jan) > 10:
            print("  ...")
            for row in daily_data_jan[-5:]: print(f"  {row['Periodo']}: {row['Target']:.3f}")
        elif len(daily_data_jan) > 5: # if between 6 and 10 days
             for row in daily_data_jan[5:]: print(f"  {row['Periodo']}: {row['Target']:.3f}")
    else:
        print("  Nessun dato giornaliero per Gennaio.")


    # Test 6: Annual Progressive Weekday Bias - Media
    targets_weekday_bias_media = {
        kpi_id_avg_test: {
            "annual_target1": 75, "annual_target2": 0,
            "repartition_logic": "Anno",
            "repartition_values": {},
            "distribution_profile": "annual_progressive_weekday_bias"
        }
    }
    save_annual_targets(test_year_main, stab_id_test, targets_weekday_bias_media)
    print(f"\nTest Annual Progressive Weekday Bias Media (Target 1: 75) - {test_year_main} - Giorno (Prima settimana):")
    daily_data_bias = get_ripartiti_data(test_year_main, stab_id_test, kpi_id_avg_test, "Giorno", 1)
    for row in daily_data_bias[:7]: print(f"  {row['Periodo']} (Weekday: {datetime.date.fromisoformat(row['Periodo']).weekday()}): {row['Target']:.2f}")


    print("\n--- Fine Test Logica Database ---")
