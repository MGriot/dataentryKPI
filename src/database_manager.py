# database_manager.py
import sqlite3
import json
from pathlib import Path
import datetime
import calendar
import numpy as np
import export_manager

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
WEIGHT_INITIAL_FACTOR_AVG = 0.8
WEIGHT_FINAL_FACTOR_AVG = 1.2
DEVIATION_SCALE_FACTOR_AVG = 0.2


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
        # Add 'unit_of_measure' to kpis if it doesn't exist (for older DBs)
        cursor.execute("PRAGMA table_info(kpis)")
        kpi_columns_set = {col[1] for col in cursor.fetchall()}
        if "unit_of_measure" not in kpi_columns_set:
            try:
                cursor.execute("ALTER TABLE kpis ADD COLUMN unit_of_measure TEXT")
                print("Aggiunta colonna 'unit_of_measure' a 'kpis'.")
            except sqlite3.OperationalError: # Should not happen if column truly doesn't exist
                pass # Column might already exist if previous attempt failed midway
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
        # Drop old table if it exists and create the new one
        # This is simpler for first-time setup or if major schema changes occur.
        # For production with existing data, a more careful migration is needed.
        # cursor.execute("DROP TABLE IF EXISTS annual_targets") # Kept for potential future schema changes
        cursor.execute(
             """ CREATE TABLE IF NOT EXISTS annual_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, stabilimento_id INTEGER NOT NULL, kpi_id INTEGER NOT NULL,
                annual_target1 REAL NOT NULL DEFAULT 0, annual_target2 REAL NOT NULL DEFAULT 0,
                repartition_logic TEXT NOT NULL,
                repartition_values TEXT NOT NULL,
                distribution_profile TEXT NOT NULL DEFAULT 'annual_progressive',
                UNIQUE(year, stabilimento_id, kpi_id))"""
        )
        # Check if existing table needs migration (for robustness if run on an older DB)
        cursor.execute("PRAGMA table_info(annual_targets)")
        target_columns = {col[1] for col in cursor.fetchall()}
        if not {"annual_target1", "annual_target2", "distribution_profile"}.issubset(target_columns):
            print("Tabella 'annual_targets' necessita di aggiornamento schema...")
            # Drop and recreate is the simplest path for this project's current state
            cursor.execute("DROP TABLE IF EXISTS annual_targets")
            cursor.execute(
                """ CREATE TABLE annual_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, stabilimento_id INTEGER NOT NULL, kpi_id INTEGER NOT NULL,
                    annual_target1 REAL NOT NULL DEFAULT 0, annual_target2 REAL NOT NULL DEFAULT 0,
                    repartition_logic TEXT NOT NULL,
                    repartition_values TEXT NOT NULL,
                    distribution_profile TEXT NOT NULL DEFAULT 'annual_progressive',
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
            # Drop and recreate for simplicity and to ensure schema is correct
            # cursor.execute(f"DROP TABLE IF EXISTS {table_name}") # Also kept for future
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

def update_kpi_subgroup(subgroup_id, new_name, group_id):
    with sqlite3.connect(DB_KPIS) as conn:
        try:
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

def update_kpi_indicator(indicator_id, new_name, subgroup_id):
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
            distribution_profile = data.get(
                "distribution_profile", "annual_progressive"
            )
            annual_target1 = float(data.get("annual_target1", 0.0) or 0.0)
            annual_target2 = float(data.get("annual_target2", 0.0) or 0.0)
            repartition_logic = data.get("repartition_logic", "Mese")

            if record:
                cursor.execute(
                    """UPDATE annual_targets SET annual_target1=?, annual_target2=?, repartition_logic=?,
                       repartition_values=?, distribution_profile=? WHERE id=?""",
                    (
                        annual_target1,
                        annual_target2,
                        repartition_logic,
                        repartition_values_json,
                        distribution_profile,
                        record["id"],
                    ),
                )
            else:
                cursor.execute(
                    """INSERT INTO annual_targets (year,stabilimento_id,kpi_id,annual_target1,annual_target2,
                       repartition_logic,repartition_values,distribution_profile) VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        year,
                        stabilimento_id,
                        kpi_id,
                        annual_target1,
                        annual_target2,
                        repartition_logic,
                        repartition_values_json,
                        distribution_profile,
                    ),
                )
        conn.commit()

    for kpi_id_saved in targets_data.keys():
        calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved, 1)
        calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved, 2)

    try:
        print(f"Avvio rigenerazione completa dei file CSV globali in: {str(CSV_EXPORT_BASE_PATH)}")
        export_manager.export_all_data_to_global_csvs(str(CSV_EXPORT_BASE_PATH))
    except Exception as e:
        print(f"ERRORE CRITICO durante la generazione dei CSV globali: {e}")
        import traceback
        traceback.print_exc()


def calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id, target_number):
    target_info = get_annual_target(year, stabilimento_id, kpi_id)
    if not target_info:
        print(f"Nessun target annuale per KPI {kpi_id}, Anno {year}, Stab {stabilimento_id}, Target Num {target_number}")
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
    if abs(annual_target_to_use or 0.0) < 1e-9 : # Handle None case for target_to_use
        # print(f"Target {target_number} per KPI {kpi_id} (Anno {year}, Stab {stabilimento_id}) è zero. Nessuna ripartizione calcolata.")
        dbs_to_clear = [
            (DB_KPI_DAYS, "daily_targets"), (DB_KPI_WEEKS, "weekly_targets"),
            (DB_KPI_MONTHS, "monthly_targets"), (DB_KPI_QUARTERS, "quarterly_targets"),
        ]
        for db_path, table_name in dbs_to_clear:
            with sqlite3.connect(db_path) as conn:
                conn.cursor().execute(
                    f"DELETE FROM {table_name} WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                    (year, stabilimento_id, kpi_id, target_number),
                )
                conn.commit()
        return


    user_repartition_logic = target_info["repartition_logic"]
    user_repartition_values_str = target_info["repartition_values"]
    try:
        user_repartition_values = json.loads(user_repartition_values_str) if user_repartition_values_str else {}
    except json.JSONDecodeError:
        print(f"ATTENZIONE: Valori di ripartizione non validi per KPI {kpi_id}, Anno {year}, Stab {stabilimento_id}. Uso default.")
        user_repartition_values = {} # Fallback to empty dict

    kpi_calc_type = kpi_details["calculation_type"]
    distribution_profile = target_info["distribution_profile"] if "distribution_profile" in target_info.keys() and target_info["distribution_profile"] else "annual_progressive"


    dbs_to_clear_periodic = [
        (DB_KPI_DAYS, "daily_targets"), (DB_KPI_WEEKS, "weekly_targets"),
        (DB_KPI_MONTHS, "monthly_targets"), (DB_KPI_QUARTERS, "quarterly_targets"),
    ]
    for db_path, table_name in dbs_to_clear_periodic:
        with sqlite3.connect(db_path) as conn:
            conn.cursor().execute(
                f"DELETE FROM {table_name} WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=?",
                (year, stabilimento_id, kpi_id, target_number),
            )
            conn.commit()

    days_in_year = (datetime.date(year, 12, 31) - datetime.date(year, 1, 1)).days + 1
    all_dates_in_year = [
        datetime.date(year, 1, 1) + datetime.timedelta(days=i)
        for i in range(days_in_year)
    ]
    daily_targets_values = []


    if kpi_calc_type == "Incrementale":
        if distribution_profile == "annual_progressive":
            daily_proportions_year = get_weighted_proportions(
                days_in_year, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC
            )
            for i, date_val in enumerate(all_dates_in_year):
                daily_targets_values.append(
                    (date_val, annual_target_to_use * daily_proportions_year[i])
                )
        elif distribution_profile in [
            "monthly_sinusoidal",
            "legacy_intra_period_progressive",
        ]:
            monthly_target_sums = [0.0] * 12
            month_user_proportions = [0.0] * 12
            if user_repartition_logic == "Mese":
                for i in range(12):
                    month_name = calendar.month_name[i + 1]
                    month_user_proportions[i] = (
                        user_repartition_values.get(month_name, 0) / 100.0
                    )
            elif user_repartition_logic == "Trimestre":
                q_map = {
                    "Q1": [0, 1, 2], "Q2": [3, 4, 5],
                    "Q3": [6, 7, 8], "Q4": [9, 10, 11],
                }
                for q_name, months_indices in q_map.items():
                    q_perc = user_repartition_values.get(q_name, 0) / 100.0
                    if q_perc > 0 and months_indices:
                        num_months_in_q = len(months_indices)
                        if distribution_profile == "legacy_intra_period_progressive":
                            month_weights_in_q = get_weighted_proportions(
                                num_months_in_q, WEIGHT_INITIAL_FACTOR_INC, WEIGHT_FINAL_FACTOR_INC
                            )
                        else:
                            month_weights_in_q = get_weighted_proportions(num_months_in_q, 1.0, 1.0)

                        for i_m, month_idx in enumerate(months_indices):
                            month_user_proportions[month_idx] = q_perc * month_weights_in_q[i_m]

            sum_prop = sum(month_user_proportions)
            if abs(sum_prop - 1.0) > 0.01 and sum_prop > 1e-9 :
                print(f"Warning: Somma proporzioni mese/trimestre per KPI {kpi_id} ({sum_prop*100:.1f}%) non è 100%. Normalizzazione...")
                month_user_proportions = [p / sum_prop for p in month_user_proportions]
            elif sum_prop < 1e-9:
                print(f"Warning: Tutte le proporzioni mese/trimestre per KPI {kpi_id} sono zero. Ripartizione annuale uniforme tra i mesi.")
                month_user_proportions = [1.0 / 12.0] * 12

            for i in range(12):
                monthly_target_sums[i] = (
                    annual_target_to_use * month_user_proportions[i]
                )

            for month_idx, month_target_sum_val in enumerate(monthly_target_sums):
                current_month = month_idx + 1
                num_days_in_month = calendar.monthrange(year, current_month)[1]
                if num_days_in_month > 0 and abs(month_target_sum_val) > 1e-9:
                    daily_weights_month = []
                    if distribution_profile == "monthly_sinusoidal":
                        daily_weights_month = get_parabolic_proportions(
                            num_days_in_month, peak_at_center=True
                        )
                    elif distribution_profile == "legacy_intra_period_progressive":
                        daily_weights_month = get_weighted_proportions(
                            num_days_in_month,
                            WEIGHT_INITIAL_FACTOR_INC,
                            WEIGHT_FINAL_FACTOR_INC,
                        )
                    else:
                        daily_weights_month = [1.0/num_days_in_month] * num_days_in_month

                    for day_of_month, day_weight in enumerate(daily_weights_month):
                        daily_targets_values.append(
                            (
                                datetime.date(year, current_month, day_of_month + 1),
                                month_target_sum_val * day_weight,
                            )
                        )
                elif num_days_in_month > 0:
                    for day_of_month in range(num_days_in_month):
                        daily_targets_values.append(
                            (datetime.date(year, current_month, day_of_month + 1), 0.0)
                        )
    elif kpi_calc_type == "Media":
        if distribution_profile == "annual_progressive":
            raw_daily_mod_factors = np.linspace(
                WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year
            )
            mean_raw_factor = np.mean(raw_daily_mod_factors) if days_in_year > 1 else raw_daily_mod_factors[0]
            for i, date_val in enumerate(all_dates_in_year):
                norm_mod = (raw_daily_mod_factors[i] - mean_raw_factor) if days_in_year > 1 else 0
                daily_targets_values.append(
                    (
                        date_val,
                        annual_target_to_use * (1 + norm_mod * DEVIATION_SCALE_FACTOR_AVG),
                    )
                )

        elif distribution_profile in [
            "monthly_sinusoidal",
            "legacy_intra_period_progressive",
        ]:
            monthly_avg_targets_base = [annual_target_to_use] * 12
            month_user_multipliers = [1.0] * 12

            if user_repartition_logic == "Mese":
                for i in range(12):
                    month_name = calendar.month_name[i + 1]
                    month_user_multipliers[i] = user_repartition_values.get(month_name, 100.0) / 100.0
            elif user_repartition_logic == "Trimestre":
                q_map = {"Q1": [0,1,2], "Q2": [3,4,5], "Q3": [6,7,8], "Q4": [9,10,11]}
                for q_name, months_indices in q_map.items():
                    q_multiplier = user_repartition_values.get(q_name, 100.0) / 100.0
                    for month_idx in months_indices:
                        month_user_multipliers[month_idx] = q_multiplier
            monthly_avg_targets = [annual_target_to_use * mult for mult in month_user_multipliers]

            for date_val in all_dates_in_year:
                month_idx = date_val.month - 1
                day_of_month_idx = date_val.day - 1
                current_month_base_avg_target = monthly_avg_targets[month_idx]
                num_days_in_month = calendar.monthrange(year, date_val.month)[1]
                daily_target_final = current_month_base_avg_target

                if num_days_in_month > 0 and abs(current_month_base_avg_target) > 1e-9:
                    if distribution_profile == "monthly_sinusoidal":
                        month_mod_factors = np.linspace(WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, num_days_in_month) # Example, adjust factors
                        mean_month_mod_factor = np.mean(month_mod_factors) if num_days_in_month > 1 else month_mod_factors[0]
                        current_day_mod_factor = month_mod_factors[day_of_month_idx]
                        norm_month_mod = (current_day_mod_factor - mean_month_mod_factor) if num_days_in_month > 1 else 0
                        daily_target_final = current_month_base_avg_target * (1 + norm_month_mod * DEVIATION_SCALE_FACTOR_AVG)
                    elif distribution_profile == "legacy_intra_period_progressive":
                        linear_mod_factors_month = np.linspace(
                            WEIGHT_INITIAL_FACTOR_AVG,
                            WEIGHT_FINAL_FACTOR_AVG,
                            num_days_in_month,
                        )
                        mean_linear_factor_month = (
                            np.mean(linear_mod_factors_month)
                            if num_days_in_month > 1
                            else linear_mod_factors_month[0]
                        )
                        current_linear_factor = linear_mod_factors_month[day_of_month_idx]
                        norm_linear_mod = (
                            (current_linear_factor - mean_linear_factor_month)
                            if num_days_in_month > 1
                            else 0
                        )
                        daily_target_final = current_month_base_avg_target * (
                            1 + norm_linear_mod * DEVIATION_SCALE_FACTOR_AVG
                        )
                daily_targets_values.append((date_val, daily_target_final))
    else:
        print(f"Tipo calcolo KPI sconosciuto: {kpi_calc_type}")
        return


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
    for wk, tgts_in_wk in weekly_agg_data.items():
        if not tgts_in_wk:
            continue
        wt = (
            sum(tgts_in_wk)
            if kpi_calc_type == "Incrementale"
            else (sum(tgts_in_wk) / len(tgts_in_wk) if tgts_in_wk else 0)
        )
        db_week_recs.append((year, stabilimento_id, kpi_id, target_number, wk, wt))
    if db_week_recs:
        db_week_recs.sort(key=lambda x: x[4])
        with sqlite3.connect(DB_KPI_WEEKS) as conn:
            conn.executemany(
                "INSERT INTO weekly_targets (year,stabilimento_id,kpi_id,target_number,week_value,target_value) VALUES (?,?,?,?,?,?)",
                db_week_recs,
            )
            conn.commit()

    monthly_agg_data = {i: [] for i in range(12)}
    for date_val, daily_target_val in daily_targets_values:
        monthly_agg_data[date_val.month - 1].append(daily_target_val)
    db_month_recs = []
    for month_idx, tgts_in_m in monthly_agg_data.items():
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

    month_to_q_map = {
        calendar.month_name[i]: f"Q{((i-1)//3)+1}" for i in range(1, 13)
    }
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

    kpi_full_name_display = f"{kpi_details['group_name']}>{kpi_details['subgroup_name']}>{kpi_details['indicator_name']}"
    print(
        f"Ripartizioni per KPI '{kpi_full_name_display}' (ID:{kpi_id}), Target {target_number} (Profilo: {distribution_profile}) calcolate e salvate."
    )


def get_ripartiti_data(year, stabilimento_id, kpi_id, period_type, target_number):
    db_map = {
        "Giorno": (DB_KPI_DAYS, "daily_targets", "date_value"),
        "Settimana": (DB_KPI_WEEKS, "weekly_targets", "week_value"),
        "Mese": (DB_KPI_MONTHS, "monthly_targets", "month_value"),
        "Trimestre": (DB_KPI_QUARTERS, "quarterly_targets", "quarter_value"),
    }
    if period_type not in db_map:
        raise ValueError("Tipo periodo non valido.")
    db_path, table_name, period_col_name = db_map[period_type]
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        order_clause = f"ORDER BY {period_col_name}"
        if period_type == "Mese":
            order_clause = (
                "ORDER BY CASE month_value "
                + " ".join(
                    [f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1, 13)]
                )
                + " END"
            )
        elif period_type == "Trimestre":
            order_clause = (
                "ORDER BY CASE quarter_value "
                + " ".join([f"WHEN 'Q{i}' THEN {i}" for i in range(1, 5)])
                + " END"
            )
        query = (
            f"SELECT {period_col_name} AS Periodo, target_value AS Target FROM {table_name} "
            f"WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=? {order_clause}"
        )
        cursor.execute(query, (year, stabilimento_id, kpi_id, target_number))
        return cursor.fetchall()


if __name__ == "__main__":
    print("Esecuzione di database_manager.py come script principale (per setup/test).")
    setup_databases()

    print("\n--- Inizio Test Logica Database ---")
    try: add_kpi_group("TestGroup")
    except sqlite3.IntegrityError: print("TestGroup già esiste.")
    test_group = next((g for g in get_kpi_groups() if g["name"] == "TestGroup"), None)

    if test_group:
        try: add_kpi_subgroup("TestSubGroup", test_group["id"])
        except sqlite3.IntegrityError: print("TestSubGroup già esiste.")
        test_subgroup = next((sg for sg in get_kpi_subgroups_by_group(test_group["id"]) if sg["name"] == "TestSubGroup"), None)

        if test_subgroup:
            try: add_kpi_indicator("TestIndicatorInc", test_subgroup["id"])
            except sqlite3.IntegrityError: print("TestIndicatorInc già esiste.")
            test_indicator_inc = next((i for i in get_kpi_indicators_by_subgroup(test_subgroup["id"]) if i["name"] == "TestIndicatorInc"), None)

            try: add_kpi_indicator("TestIndicatorAvg", test_subgroup["id"])
            except sqlite3.IntegrityError: print("TestIndicatorAvg già esiste.")
            test_indicator_avg = next((i for i in get_kpi_indicators_by_subgroup(test_subgroup["id"]) if i["name"] == "TestIndicatorAvg"), None)


            if test_indicator_inc:
                try:
                    add_kpi(test_indicator_inc["id"], "Test KPI Incrementale", "Incrementale", "UnitàInc", True)
                    print(f"KPI Incrementale 'TestIndicatorInc' (ID ind: {test_indicator_inc['id']}) aggiunto.")
                except sqlite3.IntegrityError: print(f"Specifica KPI per TestIndicatorInc (ID ind: {test_indicator_inc['id']}) già esistente.")
            else: print("Fallimento creazione TestIndicatorInc.")

            if test_indicator_avg:
                try:
                    add_kpi(test_indicator_avg["id"], "Test KPI Media", "Media", "UnitàAvg", True)
                    print(f"KPI Media 'TestIndicatorAvg' (ID ind: {test_indicator_avg['id']}) aggiunto.")
                except sqlite3.IntegrityError: print(f"Specifica KPI per TestIndicatorAvg (ID ind: {test_indicator_avg['id']}) già esistente.")
            else: print("Fallimento creazione TestIndicatorAvg.")
    else: print("Fallimento creazione TestGroup.")

    kpi_inc_obj = next((k for k in get_kpis() if k["indicator_name"] == "TestIndicatorInc"), None)
    kpi_avg_obj = next((k for k in get_kpis() if k["indicator_name"] == "TestIndicatorAvg"), None)

    try: add_stabilimento("TestStab", True)
    except sqlite3.IntegrityError: print("TestStab già esiste.")
    test_stab = next((s for s in get_stabilimenti() if s["name"] == "TestStab"), None)

    test_year_main = datetime.datetime.now().year

    if kpi_inc_obj and test_stab:
        kpi_id_inc = kpi_inc_obj["id"]
        print(f"\n--- Test KPI Incrementale: {kpi_inc_obj['indicator_name']} (ID kpi: {kpi_id_inc}) ---")
        targets_inc = {
            kpi_id_inc: {
                "annual_target1": 1200, "annual_target2": 1500,
                "repartition_logic": "Mese",
                "repartition_values": {calendar.month_name[i]: round(100/12, 2) for i in range(1,13)},
                "distribution_profile": "monthly_sinusoidal"
            }
        }
        save_annual_targets(test_year_main, test_stab["id"], targets_inc)
        print(f"Target 1 - {test_year_main} - Mese (KPI Inc):")
        for row in get_ripartiti_data(test_year_main, test_stab["id"], kpi_id_inc, "Mese", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")
        print(f"Target 1 - {test_year_main} - Giorno (KPI Inc) - Primi 5 e Ultimi 5:")
        daily_data_inc = get_ripartiti_data(test_year_main, test_stab["id"], kpi_id_inc, "Giorno", 1)
        if len(daily_data_inc) > 10:
            for row in daily_data_inc[:5]: print(f"  {row['Periodo']}: {row['Target']:.2f}")
            print("  ...")
            for row in daily_data_inc[-5:]: print(f"  {row['Periodo']}: {row['Target']:.2f}")
        else:
            for row in daily_data_inc: print(f"  {row['Periodo']}: {row['Target']:.2f}")


    if kpi_avg_obj and test_stab:
        kpi_id_avg = kpi_avg_obj["id"]
        print(f"\n--- Test KPI Media: {kpi_avg_obj['indicator_name']} (ID kpi: {kpi_id_avg}) ---")
        targets_avg = {
            kpi_id_avg: {
                "annual_target1": 100, "annual_target2": 90,
                "repartition_logic": "Trimestre",
                "repartition_values": {"Q1": 100, "Q2": 120, "Q3": 80, "Q4": 100},
                "distribution_profile": "legacy_intra_period_progressive"
            }
        }
        save_annual_targets(test_year_main, test_stab["id"], targets_avg)
        print(f"Target 1 - {test_year_main} - Trimestre (KPI Avg):")
        for row in get_ripartiti_data(test_year_main, test_stab["id"], kpi_id_avg, "Trimestre", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")
        print(f"Target 1 - {test_year_main} - Mese (KPI Avg):")
        for row in get_ripartiti_data(test_year_main, test_stab["id"], kpi_id_avg, "Mese", 1): print(f"  {row['Periodo']}: {row['Target']:.2f}")

    print("\n--- Fine Test Logica Database ---")