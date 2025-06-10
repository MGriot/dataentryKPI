# database_manager.py

import sqlite3
import json
from pathlib import Path
import datetime
import calendar
import numpy as np  # Per linspace, utile per i pesi

# --- CONFIGURAZIONE DATABASE ---
BASE_DIR = Path(__file__).parent
DB_KPIS = BASE_DIR / "db_kpis.db"
DB_STABILIMENTI = BASE_DIR / "db_stabilimenti.db"
DB_TARGETS = BASE_DIR / "db_kpi_targets.db"

# Nuovi database per i dati ripartiti
DB_KPI_DAYS = BASE_DIR / "db_kpi_days.db"
DB_KPI_WEEKS = BASE_DIR / "db_kpi_weeks.db"
DB_KPI_MONTHS = BASE_DIR / "db_kpi_months.db"
DB_KPI_QUARTERS = BASE_DIR / "db_kpi_quarters.db"

# Fattori per la distribuzione "più generoso/permissivo all'inizio"
# Per KPI Incrementale: proporzioni di distribuzione (es. 1.5 -> 0.5 significa che i primi periodi prendono di più)
WEIGHT_INITIAL_FACTOR_INC = 1.2
WEIGHT_FINAL_FACTOR_INC = 0.8
# Per KPI Media: modulazione attorno alla media (es. 1.2 -> 0.8 significa che i primi target sono il 20% sopra la media modulata, gli ultimi il 20% sotto)
# Il fattore di scala determina quanto i target si discostano dalla media annuale.
# Es. 0.2 significa che i target possono variare fino al +/- 20% della media annuale, modulati dai pesi.
DEVIATION_SCALE_FACTOR_AVG = 0.2
WEIGHT_INITIAL_FACTOR_AVG = 1.2  # Pesi grezzi, es. per modulare la deviazione
WEIGHT_FINAL_FACTOR_AVG = 0.8


def get_weighted_proportions(
    num_periods, initial_factor=1.5, final_factor=0.5, decreasing=True
):
    """
    Genera una lista di proporzioni pesate che sommano a 1.0.
    I pesi sono generati linearmente da initial_factor a final_factor.
    """
    if num_periods <= 0:
        return []
    if num_periods == 1:
        return [1.0]

    if not decreasing:
        initial_factor, final_factor = final_factor, initial_factor

    if initial_factor == final_factor:
        raw_weights = [1.0] * num_periods
    else:
        # Usiamo numpy.linspace per generare i pesi grezzi
        raw_weights = np.linspace(initial_factor, final_factor, num_periods).tolist()

    # Assicuriamo che i pesi siano positivi prima della normalizzazione
    min_raw_weight = min(raw_weights)
    if min_raw_weight <= 0:
        shift = (
            abs(min_raw_weight) + 1e-9
        )  # Aggiungi un piccolo epsilon per evitare pesi zero
        raw_weights = [w + shift for w in raw_weights]

    total_weight = sum(raw_weights)
    if total_weight == 0:  # Caso di emergenza, dovrebbe essere evitato dallo shift
        return [1.0 / num_periods] * num_periods

    normalized_weights = [w / total_weight for w in raw_weights]
    return normalized_weights


def setup_databases():
    """Crea tutte le tabelle dei database se non esistono già."""
    with sqlite3.connect(DB_KPIS) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(kpis)")
        columns = [col[1] for col in cursor.fetchall()]
        if "unit_of_measure" not in columns:
            try:
                cursor.execute("ALTER TABLE kpis ADD COLUMN unit_of_measure TEXT")
            except sqlite3.OperationalError:  # La tabella potrebbe non esistere ancora
                pass
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS kpis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                calculation_type TEXT NOT NULL CHECK(calculation_type IN ('Incrementale', 'Media')),
                unit_of_measure TEXT,
                visible BOOLEAN NOT NULL DEFAULT 1
            )
        """
        )

    with sqlite3.connect(DB_STABILIMENTI) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stabilimenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                visible BOOLEAN NOT NULL DEFAULT 1
            )
        """
        )

    with sqlite3.connect(DB_TARGETS) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS annual_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                stabilimento_id INTEGER NOT NULL,
                kpi_id INTEGER NOT NULL,
                annual_target REAL NOT NULL,
                repartition_logic TEXT NOT NULL CHECK(repartition_logic IN ('Mese', 'Trimestre')),
                repartition_values TEXT NOT NULL, -- JSON con le percentuali
                UNIQUE(year, stabilimento_id, kpi_id)
            )
        """
        )

    # Setup per i nuovi database ripartiti
    db_configs = [
        (DB_KPI_DAYS, "daily_targets", "date_value TEXT NOT NULL UNIQUE"),  # YYYY-MM-DD
        (DB_KPI_WEEKS, "weekly_targets", "week_value TEXT NOT NULL UNIQUE"),  # YYYY-Www
        (
            DB_KPI_MONTHS,
            "monthly_targets",
            "month_value TEXT NOT NULL UNIQUE",
        ),  # Month Name
        (
            DB_KPI_QUARTERS,
            "quarterly_targets",
            "quarter_value TEXT NOT NULL UNIQUE",
        ),  # QX
    ]

    for db_path, table_name, period_col_def in db_configs:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # La UNIQUE constraint su period_value deve essere parte di una chiave composita
            # con year, stabilimento_id, kpi_id.
            # Per semplicità, la tabella viene rigenerata ogni volta, quindi UNIQUE su period_value
            # all'interno di un singolo calcolo è sufficiente, ma per storage persistente
            # e aggiornamenti parziali, una chiave composita sarebbe meglio.
            # Tuttavia, dato che cancelliamo e reinseriamo, non è strettamente necessario qui.
            # Rimuoviamo UNIQUE(period_value) per ora, la gestione avviene tramite DELETE + INSERT.
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    stabilimento_id INTEGER NOT NULL,
                    kpi_id INTEGER NOT NULL,
                    {period_col_def.replace(' UNIQUE', '')},
                    target_value REAL NOT NULL,
                    UNIQUE(year, stabilimento_id, kpi_id, {period_col_def.split()[0]})
                )
            """
            )
    print("Controllo e setup database completato.")


# --- FUNZIONI DI GESTIONE KPI (invariate, ma incluse per completezza) ---
def get_kpis(only_visible=False):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM kpis"
        if only_visible:
            query += " WHERE visible = 1"
        query += " ORDER BY name"
        cursor.execute(query)
        return cursor.fetchall()


def add_kpi(name, description, calculation_type, unit_of_measure, visible):
    with sqlite3.connect(DB_KPIS) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO kpis (name, description, calculation_type, unit_of_measure, visible) VALUES (?, ?, ?, ?, ?)",
                (name, description, calculation_type, unit_of_measure, visible),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise e


def update_kpi(kpi_id, name, description, calculation_type, unit_of_measure, visible):
    with sqlite3.connect(DB_KPIS) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE kpis SET name=?, description=?, calculation_type=?, unit_of_measure=?, visible=? WHERE id=?",
                (name, description, calculation_type, unit_of_measure, visible, kpi_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise e


def get_kpi_by_id(kpi_id):
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM kpis WHERE id = ?", (kpi_id,))
        return cursor.fetchone()


# --- FUNZIONI DI GESTIONE STABILIMENTI (invariate, ma incluse per completezza) ---
def get_stabilimenti(only_visible=False):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM stabilimenti"
        if only_visible:
            query += " WHERE visible = 1"
        query += " ORDER BY name"
        cursor.execute(query)
        return cursor.fetchall()


def add_stabilimento(name, visible):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO stabilimenti (name, visible) VALUES (?, ?)",
                (name, visible),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise e


def update_stabilimento(stabilimento_id, name, visible):
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE stabilimenti SET name=?, visible=? WHERE id=?",
                (name, visible, stabilimento_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise e


# --- FUNZIONI DI GESTIONE TARGET ---
def get_annual_target(year, stabilimento_id, kpi_id):
    with sqlite3.connect(DB_TARGETS) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM annual_targets WHERE year=? AND stabilimento_id=? AND kpi_id=?",
            (year, stabilimento_id, kpi_id),
        )
        return cursor.fetchone()


def save_annual_targets(year, stabilimento_id, targets_data):
    if not targets_data:
        print("Nessun dato target da salvare.")
        return

    with sqlite3.connect(DB_TARGETS) as conn:
        cursor = conn.cursor()
        for kpi_id, data in targets_data.items():
            record = get_annual_target(
                year, stabilimento_id, kpi_id
            )  # Usa la funzione esistente
            repartition_values_json = json.dumps(data["repartition_values"])

            if record:
                cursor.execute(
                    """UPDATE annual_targets
                       SET annual_target=?, repartition_logic=?, repartition_values=?
                       WHERE id=?""",
                    (
                        data["annual_target"],
                        data["repartition_logic"],
                        repartition_values_json,
                        record["id"],
                    ),
                )
            else:
                cursor.execute(
                    """INSERT INTO annual_targets
                       (year, stabilimento_id, kpi_id, annual_target, repartition_logic, repartition_values)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        year,
                        stabilimento_id,
                        kpi_id,
                        data["annual_target"],
                        data["repartition_logic"],
                        repartition_values_json,
                    ),
                )
        conn.commit()

    for kpi_id_saved in targets_data.keys():
        calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id_saved)


def calculate_and_save_all_repartitions(year, stabilimento_id, kpi_id):
    """
    Funzione principale per calcolare e salvare tutte le ripartizioni
    (giornaliera, settimanale, mensile, trimestrale) per un KPI.
    """
    target_info = get_annual_target(year, stabilimento_id, kpi_id)
    if not target_info:
        print(
            f"Nessun target annuale trovato per KPI {kpi_id}, Anno {year}, Stabilimento {stabilimento_id}"
        )
        return

    kpi_details = get_kpi_by_id(kpi_id)
    if not kpi_details:
        print(f"Dettagli KPI non trovati per ID {kpi_id}")
        return

    annual_target = target_info["annual_target"]
    user_repartition_logic = target_info["repartition_logic"]  # 'Mese' o 'Trimestre'
    user_repartition_values = json.loads(
        target_info["repartition_values"]
    )  # Percentuali
    kpi_calc_type = kpi_details["calculation_type"]

    # Cancella i dati vecchi per questo KPI, anno, stabilimento dai DB ripartiti
    dbs_to_clear = [
        (DB_KPI_DAYS, "daily_targets"),
        (DB_KPI_WEEKS, "weekly_targets"),
        (DB_KPI_MONTHS, "monthly_targets"),
        (DB_KPI_QUARTERS, "quarterly_targets"),
    ]
    for db_path, table_name in dbs_to_clear:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"DELETE FROM {table_name} WHERE year=? AND stabilimento_id=? AND kpi_id=?",
                (year, stabilimento_id, kpi_id),
            )
            conn.commit()

    # --- Preparazione dati temporali ---
    days_in_year = (datetime.date(year, 12, 31) - datetime.date(year, 1, 1)).days + 1
    all_dates_in_year = [
        datetime.date(year, 1, 1) + datetime.timedelta(days=i)
        for i in range(days_in_year)
    ]

    monthly_targets_values = [0.0] * 12  # Indice 0 per Gennaio, ..., 11 per Dicembre
    daily_targets_values = []  # Lista di tuple (datetime.date, target_value)

    # --- Logica di Calcolo ---
    if kpi_calc_type == "Incrementale":
        # 1. Determinare i target mensili (somma)
        month_proportions = [0.0] * 12
        if user_repartition_logic == "Mese":
            for i in range(12):
                month_name = calendar.month_name[i + 1]
                month_proportions[i] = (
                    user_repartition_values.get(month_name, 0) / 100.0
                )
        elif user_repartition_logic == "Trimestre":
            q_map = {
                "Q1": [0, 1, 2],
                "Q2": [3, 4, 5],
                "Q3": [6, 7, 8],
                "Q4": [9, 10, 11],
            }
            for q_name, months_indices in q_map.items():
                q_percentage = user_repartition_values.get(q_name, 0) / 100.0
                if q_percentage > 0 and len(months_indices) > 0:
                    # Distribuisci la percentuale del trimestre sui suoi mesi con pesi
                    month_weights_in_quarter = get_weighted_proportions(
                        len(months_indices),
                        WEIGHT_INITIAL_FACTOR_INC,
                        WEIGHT_FINAL_FACTOR_INC,
                    )
                    for i, month_idx in enumerate(months_indices):
                        month_proportions[month_idx] = (
                            q_percentage * month_weights_in_quarter[i]
                        )

        # Normalizza le proporzioni mensili se necessario (dovrebbero già sommare a 1 se l'input è corretto)
        current_sum_proportions = sum(month_proportions)
        if current_sum_proportions > 0 and not (
            0.999 <= current_sum_proportions <= 1.001
        ):  # Tolleranza
            print(
                f"Attenzione: la somma delle proporzioni mensili ({current_sum_proportions}) non è 1. Normalizzazione."
            )
            month_proportions = [p / current_sum_proportions for p in month_proportions]

        for i in range(12):
            monthly_targets_values[i] = annual_target * month_proportions[i]

        # 2. Dai target mensili (somma) ai target giornalieri (somma)
        for month_idx, month_target_sum in enumerate(monthly_targets_values):
            current_month = month_idx + 1
            num_days_in_month = calendar.monthrange(year, current_month)[1]
            if (
                num_days_in_month > 0 and month_target_sum != 0
            ):  # Evita divisione per zero o pesi inutili
                daily_weights_for_month = get_weighted_proportions(
                    num_days_in_month,
                    WEIGHT_INITIAL_FACTOR_INC,
                    WEIGHT_FINAL_FACTOR_INC,
                )
                for day_of_month, day_weight in enumerate(daily_weights_for_month):
                    date_val = datetime.date(year, current_month, day_of_month + 1)
                    daily_target = month_target_sum * day_weight
                    daily_targets_values.append((date_val, daily_target))
            elif (
                num_days_in_month > 0 and month_target_sum == 0
            ):  # Se il target del mese è 0, tutti i giorni sono 0
                for day_of_month in range(num_days_in_month):
                    date_val = datetime.date(year, current_month, day_of_month + 1)
                    daily_targets_values.append((date_val, 0.0))

    elif kpi_calc_type == "Media":
        # 1. Calcola target giornalieri (media) direttamente modulando il target annuale
        # Pesi grezzi per la deviazione giornaliera
        raw_daily_modulation_factors = np.linspace(
            WEIGHT_INITIAL_FACTOR_AVG, WEIGHT_FINAL_FACTOR_AVG, days_in_year
        )
        mean_raw_factor = np.mean(raw_daily_modulation_factors)

        for i, date_val in enumerate(all_dates_in_year):
            # Il fattore di modulazione normalizzato (media zero)
            normalized_modulation = raw_daily_modulation_factors[i] - mean_raw_factor
            # Il target giornaliero oscilla attorno al target annuale
            daily_target_avg = annual_target + (
                normalized_modulation * annual_target * DEVIATION_SCALE_FACTOR_AVG
            )
            daily_targets_values.append((date_val, daily_target_avg))

        # 2. I target mensili (media) saranno la media dei target giornalieri del mese
        # Questo calcolo verrà fatto più avanti durante il salvataggio dei dati mensili.

    else:
        print(f"Tipo di calcolo KPI sconosciuto: {kpi_calc_type}")
        return

    # --- Salvataggio Dati Ripartiti ---

    # Giornalieri
    db_day_records = []
    for date_val, target in daily_targets_values:
        db_day_records.append(
            (year, stabilimento_id, kpi_id, date_val.isoformat(), target)
        )
    if db_day_records:
        with sqlite3.connect(DB_KPI_DAYS) as conn:
            conn.executemany(
                f"INSERT INTO daily_targets (year, stabilimento_id, kpi_id, date_value, target_value) VALUES (?, ?, ?, ?, ?)",
                db_day_records,
            )
            conn.commit()

    # Settimanali
    weekly_aggregated_data = {}  # key: YYYY-Www, value: list of daily targets
    for date_val, daily_target in daily_targets_values:
        iso_year, iso_week, _ = date_val.isocalendar()
        # Assicurati che l'anno ISO corrisponda all'anno del target se la settimana è a cavallo
        # Per semplicità, usiamo l'anno ISO, ma potrebbe essere necessario gestirlo se si vuole strettamente l'anno civile
        week_key = f"{iso_year}-W{iso_week:02d}"
        if week_key not in weekly_aggregated_data:
            weekly_aggregated_data[week_key] = []
        weekly_aggregated_data[week_key].append(daily_target)

    db_week_records = []
    for week_key, daily_targets_in_week in weekly_aggregated_data.items():
        if not daily_targets_in_week:
            continue
        if kpi_calc_type == "Incrementale":
            week_target = sum(daily_targets_in_week)
        else:  # Media
            week_target = sum(daily_targets_in_week) / len(daily_targets_in_week)
        db_week_records.append((year, stabilimento_id, kpi_id, week_key, week_target))

    if db_week_records:
        # Ordina per chiave settimanale prima dell'inserimento per coerenza
        db_week_records.sort(key=lambda x: x[3])
        with sqlite3.connect(DB_KPI_WEEKS) as conn:
            conn.executemany(
                f"INSERT INTO weekly_targets (year, stabilimento_id, kpi_id, week_value, target_value) VALUES (?, ?, ?, ?, ?)",
                db_week_records,
            )
            conn.commit()

    # Mensili
    monthly_aggregated_data = {
        i: [] for i in range(12)
    }  # key: month_idx (0-11), value: list of daily targets
    if kpi_calc_type == "Incrementale":  # Usa i monthly_targets_values già calcolati
        db_month_records = []
        for month_idx, month_target_sum in enumerate(monthly_targets_values):
            month_name = calendar.month_name[month_idx + 1]
            db_month_records.append(
                (year, stabilimento_id, kpi_id, month_name, month_target_sum)
            )
    else:  # Media: aggrega dai giornalieri
        for date_val, daily_target in daily_targets_values:
            monthly_aggregated_data[date_val.month - 1].append(daily_target)

        db_month_records = []
        for month_idx, daily_targets_in_month in monthly_aggregated_data.items():
            month_name = calendar.month_name[month_idx + 1]
            if (
                not daily_targets_in_month
            ):  # Mese senza giorni (improbabile) o senza target
                month_target = 0.0
            else:
                month_target = sum(daily_targets_in_month) / len(daily_targets_in_month)
            db_month_records.append(
                (year, stabilimento_id, kpi_id, month_name, month_target)
            )

    if db_month_records:
        with sqlite3.connect(DB_KPI_MONTHS) as conn:
            conn.executemany(
                f"INSERT INTO monthly_targets (year, stabilimento_id, kpi_id, month_value, target_value) VALUES (?, ?, ?, ?, ?)",
                db_month_records,
            )
            conn.commit()

    # Trimestrali
    quarterly_aggregated_data = {
        "Q1": [],
        "Q2": [],
        "Q3": [],
        "Q4": [],
    }  # value: list of monthly targets (from db_month_records)
    # oppure daily targets per Media

    # Per consistenza, usiamo i target mensili (appena calcolati e salvati in db_month_records) per calcolare i trimestri
    # o i giornalieri se il KPI è Media e vogliamo la media dei giornalieri.
    # Useremo i db_month_records che contengono i target mensili finali.

    # Recupera i target mensili appena calcolati per l'aggregazione trimestrale
    actual_monthly_targets_for_quarter_calc = {}
    for rec in db_month_records:  # year, stab_id, kpi_id, month_name, target
        actual_monthly_targets_for_quarter_calc[rec[3]] = rec[4]

    month_to_quarter_map = {}
    for i in range(1, 13):
        month_name = calendar.month_name[i]
        if 1 <= i <= 3:
            month_to_quarter_map[month_name] = "Q1"
        elif 4 <= i <= 6:
            month_to_quarter_map[month_name] = "Q2"
        elif 7 <= i <= 9:
            month_to_quarter_map[month_name] = "Q3"
        else:
            month_to_quarter_map[month_name] = "Q4"

    for month_name, monthly_target in actual_monthly_targets_for_quarter_calc.items():
        q_name = month_to_quarter_map[month_name]
        quarterly_aggregated_data[q_name].append(monthly_target)

    db_quarter_records = []
    for q_name, monthly_targets_in_quarter in quarterly_aggregated_data.items():
        if not monthly_targets_in_quarter:
            continue  # Trimestre vuoto
        if kpi_calc_type == "Incrementale":
            quarter_target = sum(monthly_targets_in_quarter)
        else:  # Media
            quarter_target = sum(monthly_targets_in_quarter) / len(
                monthly_targets_in_quarter
            )
        db_quarter_records.append(
            (year, stabilimento_id, kpi_id, q_name, quarter_target)
        )

    if db_quarter_records:
        # Ordina per Q1, Q2, Q3, Q4
        db_quarter_records.sort(key=lambda x: x[3])
        with sqlite3.connect(DB_KPI_QUARTERS) as conn:
            conn.executemany(
                f"INSERT INTO quarterly_targets (year, stabilimento_id, kpi_id, quarter_value, target_value) VALUES (?, ?, ?, ?, ?)",
                db_quarter_records,
            )
            conn.commit()

    print(
        f"Ripartizioni per KPI {kpi_id} (Anno {year}, Stab {stabilimento_id}, Tipo: {kpi_calc_type}) calcolate e salvate."
    )


def get_ripartiti_data(year, stabilimento_id, kpi_id, period_type):
    """Recupera i dati ripartiti dal database corretto."""
    db_path, table_name, period_col_name = None, None, None
    if period_type == "Giorno":
        db_path, table_name, period_col_name = (
            DB_KPI_DAYS,
            "daily_targets",
            "date_value",
        )
    elif period_type == "Settimana":
        db_path, table_name, period_col_name = (
            DB_KPI_WEEKS,
            "weekly_targets",
            "week_value",
        )
    elif period_type == "Mese":
        db_path, table_name, period_col_name = (
            DB_KPI_MONTHS,
            "monthly_targets",
            "month_value",
        )
    elif period_type == "Trimestre":
        db_path, table_name, period_col_name = (
            DB_KPI_QUARTERS,
            "quarterly_targets",
            "quarter_value",
        )
    else:
        raise ValueError("Tipo di periodo non valido.")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT {period_col_name} AS Periodo, target_value AS Target FROM {table_name} "
            "WHERE year=? AND stabilimento_id=? AND kpi_id=? "
            f"ORDER BY CASE {period_col_name} "  # Ordinamento specifico per mese/trimestre
            f"WHEN 'Gennaio' THEN 1 WHEN 'Febbraio' THEN 2 WHEN 'Marzo' THEN 3 "
            f"WHEN 'Aprile' THEN 4 WHEN 'Maggio' THEN 5 WHEN 'Giugno' THEN 6 "
            f"WHEN 'Luglio' THEN 7 WHEN 'Agosto' THEN 8 WHEN 'Settembre' THEN 9 "
            f"WHEN 'Ottobre' THEN 10 WHEN 'Novembre' THEN 11 WHEN 'Dicembre' THEN 12 "
            f"WHEN 'Q1' THEN 1 WHEN 'Q2' THEN 2 WHEN 'Q3' THEN 3 WHEN 'Q4' THEN 4 "
            f"ELSE {period_col_name} END",  # Altrimenti ordina alfabeticamente/numericamente (per date, settimane)
            (year, stabilimento_id, kpi_id),
        )
        return cursor.fetchall()


# Esegui il setup iniziale quando il modulo viene importato/eseguito
setup_databases()

if __name__ == "__main__":
    print("Esecuzione di database_manager.py come script principale (per test).")

    # --- DATI DI TEST ---
    try:
        add_stabilimento("Stabilimento Alpha", True)
        add_stabilimento("Stabilimento Beta (Inattivo)", False)
    except sqlite3.IntegrityError:
        pass  # Ignora se già esistenti

    try:
        add_kpi(
            "Vendite Totali",
            "Volume totale delle vendite annuali",
            "Incrementale",
            "€",
            True,
        )
        add_kpi(
            "Temperatura Media Magazzino",
            "Temperatura media interna del magazzino",
            "Media",
            "°C",
            True,
        )
        add_kpi(
            "Costi Operativi", "Costi operativi totali", "Incrementale", "€", False
        )  # KPI non visibile
    except sqlite3.IntegrityError:
        pass

    kpi_vendite = next((k for k in get_kpis() if k["name"] == "Vendite Totali"), None)
    kpi_temp = next(
        (k for k in get_kpis() if k["name"] == "Temperatura Media Magazzino"), None
    )
    stab_alpha = next(
        (s for s in get_stabilimenti() if s["name"] == "Stabilimento Alpha"), None
    )

    if kpi_vendite and stab_alpha:
        print(f"\n--- Test KPI Incrementale: {kpi_vendite['name']} ---")
        test_year = datetime.datetime.now().year
        id_kpi_vendite = kpi_vendite["id"]
        id_stab_alpha = stab_alpha["id"]

        targets_vendite = {
            id_kpi_vendite: {
                "annual_target": 1200000,  # 1.2 Milioni
                "repartition_logic": "Trimestre",  # Ripartizione utente per trimestri
                "repartition_values": {
                    "Q1": 20,
                    "Q2": 30,
                    "Q3": 30,
                    "Q4": 20,
                },  # Somma 100%
            }
        }
        save_annual_targets(test_year, id_stab_alpha, targets_vendite)

        print("Dati Mensili (Vendite):")
        for row in get_ripartiti_data(test_year, id_stab_alpha, id_kpi_vendite, "Mese"):
            print(f"  {row['Periodo']}: {row['Target']:.2f}")

        # Verifica somma annuale
        dati_giornalieri = get_ripartiti_data(
            test_year, id_stab_alpha, id_kpi_vendite, "Giorno"
        )
        somma_giornaliera = sum(r["Target"] for r in dati_giornalieri)
        print(
            f"Somma target giornalieri (Vendite): {somma_giornaliera:.2f} (Target Annuale: 1200000)"
        )

    if kpi_temp and stab_alpha:
        print(f"\n--- Test KPI Media: {kpi_temp['name']} ---")
        test_year = datetime.datetime.now().year
        id_kpi_temp = kpi_temp["id"]
        id_stab_alpha = stab_alpha["id"]

        targets_temp = {
            id_kpi_temp: {
                "annual_target": 15.0,  # Media 15°C
                "repartition_logic": "Mese",  # Questa logica utente è ignorata per KPI Media nella mia implementazione,
                # la ripartizione "generosa" è applicata direttamente a livello giornaliero.
                "repartition_values": {
                    calendar.month_name[i]: (100 / 12) for i in range(1, 13)
                },
            }
        }
        save_annual_targets(test_year, id_stab_alpha, targets_temp)

        print("Dati Mensili (Temperatura Media):")
        for row in get_ripartiti_data(test_year, id_stab_alpha, id_kpi_temp, "Mese"):
            print(f"  {row['Periodo']}: {row['Target']:.2f}")

        dati_giornalieri_temp = get_ripartiti_data(
            test_year, id_stab_alpha, id_kpi_temp, "Giorno"
        )
        if dati_giornalieri_temp:
            media_giornaliera_temp = sum(
                r["Target"] for r in dati_giornalieri_temp
            ) / len(dati_giornalieri_temp)
            print(
                f"Media dei target giornalieri (Temperatura): {media_giornaliera_temp:.2f} (Target Annuale: 15.0)"
            )
            print(f"  Prime 3 ripartizioni giornaliere (Temperatura):")
            for r in dati_giornalieri_temp[:3]:
                print(f"    {r['Periodo']}: {r['Target']:.2f}")
            print(f"  Ultime 3 ripartizioni giornaliere (Temperatura):")
            for r in dati_giornalieri_temp[-3:]:
                print(f"    {r['Periodo']}: {r['Target']:.2f}")

    print("\nFine esecuzione script database_manager.py (test).")
