#export_manager.py
import csv
import zipfile
from pathlib import Path
import database_manager as db  # Assuming you import database_manager as db
import sqlite3
import calendar  # Import the calendar module for month names

# Define the names for the global CSV files
GLOBAL_CSV_FILES = {
    "days": "all_daily_kpi_targets.csv",
    "weeks": "all_weekly_kpi_targets.csv",
    "months": "all_monthly_kpi_targets.csv",
    "quarters": "all_quarterly_kpi_targets.csv",
    "annual": "all_annual_kpi_master_targets.csv",
    "stabilimenti": "dict_stabilimenti.csv",
    "kpis": "dict_kpis.csv",
}

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


def export_all_data_to_global_csvs(base_export_path_str: str):
    """
    Generates/Overwrites global CSV files with all data from the databases,
    plus dictionary tables for stabilimenti and KPI descriptions.
    Includes more robust error handling for each export step.
    """
    func_name = "export_all_data_to_global_csvs"
    print(
        f"INFO [{func_name}]: Inizio esportazione globale CSV in: {base_export_path_str}"
    )

    base_export_path = Path(base_export_path_str)
    try:
        base_export_path.mkdir(parents=True, exist_ok=True)
    except Exception as e_mkdir:
        print(
            f"CRITICAL ERROR [{func_name}]: Impossibile creare la cartella di esportazione base '{base_export_path}': {e_mkdir}"
        )
        print(traceback.format_exc())
        return  # Cannot proceed if base export path cannot be created

    export_successful_count = 0
    export_failed_count = 0
    export_details = []

    # 1. Export Annual Master Targets
    annual_export_file = GLOBAL_CSV_FILES["annual"]
    annual_output_filepath = base_export_path / annual_export_file
    print(f"INFO [{func_name}]: Tentativo esportazione {annual_export_file}...")
    try:
        _export_annual_master_to_csv(annual_output_filepath)
        print(f"SUCCESS [{func_name}]: Esportazione {annual_export_file} completata.")
        export_successful_count += 1
        export_details.append(f"[SUCCESS] {annual_export_file}")
    except Exception as e_annual:
        print(
            f"CRITICAL ERROR [{func_name}]: Fallita esportazione master annuale ({annual_export_file}): {e_annual}"
        )
        print(traceback.format_exc())
        export_failed_count += 1
        export_details.append(f"[FAILED]  {annual_export_file}: {e_annual}")
        # Optionally, create an empty file with header to indicate attempt
        try:
            with open(
                annual_output_filepath, "w", newline="", encoding="utf-8"
            ) as f_err:
                # Attempt to get header if function defines it early, otherwise generic
                header = [
                    "annual_target_id",
                    "year",
                    "stabilimento_id",
                    "kpi_id",
                    "...",
                ]  # Fallback header
                if (
                    hasattr(_export_annual_master_to_csv, "__closure__")
                    and _export_annual_master_to_csv.__closure__
                ):  # Risky check for non-locals
                    # This is generally not a good way to get header, better to define it centrally or pass it
                    pass
                csv.writer(f_err).writerow(header)
        except Exception:
            pass  # Ignore if even this fails

    # 2. Export Periodic Data (Days, Weeks, Months, Quarters)
    periodic_db_map = {
        "days": (db.DB_KPI_DAYS, "daily_targets", "date_value"),
        "weeks": (db.DB_KPI_WEEKS, "weekly_targets", "week_value"),
        "months": (db.DB_KPI_MONTHS, "monthly_targets", "month_value"),
        "quarters": (db.DB_KPI_QUARTERS, "quarterly_targets", "quarter_value"),
    }

    for period_key, (
        db_path_const,
        table_name,
        period_col_name,
    ) in periodic_db_map.items():
        periodic_export_file = GLOBAL_CSV_FILES[period_key]
        periodic_output_filepath = base_export_path / periodic_export_file
        print(f"INFO [{func_name}]: Tentativo esportazione {periodic_export_file}...")
        try:
            # Ensure the db_path from the constant is valid
            actual_db_path = None
            if hasattr(
                db,
                (
                    db_path_const.__name__
                    if hasattr(db_path_const, "__name__")
                    else str(db_path_const)
                ),
            ):  # Check if constant name exists in db module
                actual_db_path = getattr(
                    db,
                    (
                        db_path_const.__name__
                        if hasattr(db_path_const, "__name__")
                        else str(db_path_const)
                    ),
                )
            elif isinstance(
                db_path_const, (str, Path)
            ):  # If it's already a path string/object
                actual_db_path = db_path_const
            else:
                raise ValueError(
                    f"Percorso DB per '{period_key}' ({db_path_const}) non è valido o non trovato nel modulo 'db'."
                )

            _export_single_period_to_global_csv(
                actual_db_path, table_name, period_col_name, periodic_output_filepath
            )
            print(
                f"SUCCESS [{func_name}]: Esportazione {periodic_export_file} completata."
            )
            export_successful_count += 1
            export_details.append(f"[SUCCESS] {periodic_export_file}")
        except Exception as e_periodic:
            print(
                f"CRITICAL ERROR [{func_name}]: Fallita esportazione dati periodici '{period_key}' ({periodic_export_file}): {e_periodic}"
            )
            print(traceback.format_exc())
            export_failed_count += 1
            export_details.append(f"[FAILED]  {periodic_export_file}: {e_periodic}")
            try:
                with open(
                    periodic_output_filepath, "w", newline="", encoding="utf-8"
                ) as f_err:
                    header = [
                        "kpi_id",
                        "stabilimento_id",
                        "year",
                        period_col_name,
                        "target1_value",
                        "target2_value",
                    ]
                    csv.writer(f_err).writerow(header)
            except Exception:
                pass

    # 3. Export Dictionary Tables
    # Stabilimenti
    stab_export_file = GLOBAL_CSV_FILES["stabilimenti"]
    stab_output_filepath = base_export_path / stab_export_file
    print(f"INFO [{func_name}]: Tentativo esportazione {stab_export_file}...")
    try:
        _export_stabilimenti_to_csv(stab_output_filepath)
        print(f"SUCCESS [{func_name}]: Esportazione {stab_export_file} completata.")
        export_successful_count += 1
        export_details.append(f"[SUCCESS] {stab_export_file}")
    except Exception as e_stab:
        print(
            f"CRITICAL ERROR [{func_name}]: Fallita esportazione stabilimenti ({stab_export_file}): {e_stab}"
        )
        print(traceback.format_exc())
        export_failed_count += 1
        export_details.append(f"[FAILED]  {stab_export_file}: {e_stab}")
        try:
            with open(stab_output_filepath, "w", newline="", encoding="utf-8") as f_err:
                header = ["id", "name", "description"]
                csv.writer(f_err).writerow(header)
        except Exception:
            pass

    # KPIs
    kpis_export_file = GLOBAL_CSV_FILES["kpis"]
    kpis_output_filepath = base_export_path / kpis_export_file
    print(f"INFO [{func_name}]: Tentativo esportazione {kpis_export_file}...")
    try:
        _export_kpis_to_csv(kpis_output_filepath)
        print(f"SUCCESS [{func_name}]: Esportazione {kpis_export_file} completata.")
        export_successful_count += 1
        export_details.append(f"[SUCCESS] {kpis_export_file}")
    except Exception as e_kpis:
        print(
            f"CRITICAL ERROR [{func_name}]: Fallita esportazione dizionario KPI ({kpis_export_file}): {e_kpis}"
        )
        print(traceback.format_exc())
        export_failed_count += 1
        export_details.append(f"[FAILED]  {kpis_export_file}: {e_kpis}")
        try:
            with open(kpis_output_filepath, "w", newline="", encoding="utf-8") as f_err:
                header = [
                    "id",
                    "group_id",
                    "group_name",
                    "subgroup_id",
                    "subgroup_name",
                    "...",
                ]
                csv.writer(f_err).writerow(header)
        except Exception:
            pass

    print(f"INFO [{func_name}]: Esportazione globale CSV terminata.")
    print(f"INFO [{func_name}]: Riepilogo esportazioni:")
    for detail in export_details:
        print(f"    {detail}")
    print(
        f"INFO [{func_name}]: Totale Successi: {export_successful_count}, Totale Fallimenti: {export_failed_count}"
    )
    if export_failed_count > 0:
        print(
            f"ATTENZIONE [{func_name}]: Alcune esportazioni CSV sono fallite. Controllare i log sopra."
        )
    else:
        print(
            f"INFO [{func_name}]: Tutte le esportazioni CSV sono state completate con successo."
        )


def _export_annual_master_to_csv(output_filepath: Path):
    """
    Exports specified records from the annual_targets table.
    Focuses on exporting IDs and core target data.
    """
    func_name = "_export_annual_master_to_csv"
    print(f"DEBUG [{func_name}]: Starting export to {output_filepath}")

    header = [
        "annual_target_id",  # annual_targets.id
        "year",  # annual_targets.year
        "stabilimento_id",  # annual_targets.stabilimento_id (FK)
        "kpi_id",  # annual_targets.kpi_id (FK to kpis.id)
        "annual_target1_value",
        "annual_target2_value",
        "distribution_profile",
        "repartition_logic",
        "repartition_values_json",
        "profile_params_json",
        "is_target1_manual",  # boolean (0 or 1)
        "is_target2_manual",  # boolean (0 or 1)
    ]

    all_annual_targets_rows = []
    db_path_resolved_str = "UNKNOWN_DB_PATH"
    sql_query_executed = "NOT_YET_DEFINED"

    try:
        if not hasattr(db, "DB_TARGETS") or not db.DB_TARGETS:
            print(
                f"CRITICAL ERROR [{func_name}]: db.DB_TARGETS is not defined or is empty in database_manager module."
            )
            raise ValueError(
                "DB_TARGETS path is not configured."
            )  # Raise error to be caught by generic except

        # Ensure db.DB_TARGETS is a Path object or string path and resolve it
        db_path = Path(db.DB_TARGETS)
        if not db_path.is_absolute():
            # Attempt to resolve relative to a known base if necessary, or assume CWD
            # For simplicity, we'll resolve it directly. If it's relative, ensure it's correct.
            db_path_resolved_str = str(db_path.resolve())
        else:
            db_path_resolved_str = str(db_path)

        print(
            f"DEBUG [{func_name}]: Connecting to DB_TARGETS at resolved path: {db_path_resolved_str}"
        )

        if not Path(db_path_resolved_str).exists():
            print(
                f"CRITICAL ERROR [{func_name}]: Database file does not exist at {db_path_resolved_str}"
            )
            raise FileNotFoundError(
                f"DB_TARGETS file not found: {db_path_resolved_str}"
            )

        with sqlite3.connect(db_path_resolved_str) as conn:  # Use resolved path
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Explicitly list all columns to be fetched
            sql_query_executed = """
                SELECT id, year, stabilimento_id, kpi_id,
                       annual_target1, annual_target2,
                       distribution_profile, repartition_logic,
                       repartition_values, profile_params,
                       is_target1_manual, is_target2_manual
                FROM annual_targets
                ORDER BY year, stabilimento_id, kpi_id;
            """
            print(f"DEBUG [{func_name}]: Executing query: {sql_query_executed}")

            cursor.execute(sql_query_executed)
            all_annual_targets_rows = cursor.fetchall()

            print(
                f"DEBUG [{func_name}]: Fetched {len(all_annual_targets_rows)} rows from annual_targets."
            )
            if all_annual_targets_rows and len(all_annual_targets_rows) > 0:
                try:
                    # Attempt to convert the first row to dict for debugging
                    # This can fail if row_factory was not set or fetchall returned non-Row objects
                    first_row_dict = dict(all_annual_targets_rows[0])
                    print(f"DEBUG [{func_name}]: First row fetched: {first_row_dict}")
                except Exception as e_dict:
                    print(
                        f"DEBUG [{func_name}]: Could not convert first row to dict for debug print: {e_dict}"
                    )
                    print(
                        f"DEBUG [{func_name}]: First row raw type: {type(all_annual_targets_rows[0])}, content: {all_annual_targets_rows[0]}"
                    )

    except sqlite3.Error as sqle:
        print(
            f"CRITICAL SQLITE ERROR [{func_name}] on DB '{db_path_resolved_str}': {sqle}"
        )
        print(f"   Query was: {sql_query_executed}")
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile_err:
            csv.writer(csvfile_err).writerow(header)
        return  # Exit function after logging error and writing header
    except FileNotFoundError as fnfe:  # Specific handling for file not found
        print(f"CRITICAL FILE NOT FOUND ERROR [{func_name}]: {fnfe}")
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile_err:
            csv.writer(csvfile_err).writerow(header)
        return
    except Exception as e:
        print(
            f"UNEXPECTED ERROR [{func_name}] during data retrieval (DB: '{db_path_resolved_str}'): {e}"
        )
        print(traceback.format_exc())
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile_err:
            csv.writer(csvfile_err).writerow(header)
        return

    # --- Proceed to write CSV content ---
    print(
        f"DEBUG [{func_name}]: Proceeding to write CSV. Rows fetched: {len(all_annual_targets_rows)}"
    )
    try:
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)

            if not all_annual_targets_rows:
                print(
                    f"INFO [{func_name}]: Nessun dato trovato in annual_targets (DB: {db_path_resolved_str}) per il file {output_filepath.name}."
                )
                # No return here, an empty CSV with only a header is a valid state if table is empty.
            else:
                for i, at_row in enumerate(all_annual_targets_rows):
                    try:
                        # Safely get values, providing defaults for None where appropriate for formatting
                        annual_target_id = at_row["id"]
                        year = at_row["year"]
                        stabilimento_id = at_row["stabilimento_id"]
                        kpi_id = at_row["kpi_id"]

                        annual_target1 = at_row["annual_target1"]
                        annual_target1_str = (
                            f"{annual_target1:.2f}"
                            if annual_target1 is not None
                            else ""
                        )

                        annual_target2 = at_row["annual_target2"]
                        annual_target2_str = (
                            f"{annual_target2:.2f}"
                            if annual_target2 is not None
                            else ""
                        )

                        distribution_profile = (
                            at_row["distribution_profile"]
                            if at_row["distribution_profile"] is not None
                            else ""
                        )
                        repartition_logic = (
                            at_row["repartition_logic"]
                            if at_row["repartition_logic"] is not None
                            else ""
                        )

                        # These are expected to be JSON strings from the DB or None
                        repartition_values_json = (
                            at_row["repartition_values"]
                            if at_row["repartition_values"] is not None
                            else "{}"
                        )

                        profile_params_json = "{}"  # Default for profile_params
                        if (
                            "profile_params" in at_row.keys()
                            and at_row["profile_params"] is not None
                        ):
                            profile_params_json = at_row["profile_params"]

                        is_target1_manual = 1 if at_row["is_target1_manual"] else 0
                        is_target2_manual = 1 if at_row["is_target2_manual"] else 0

                        writer.writerow(
                            [
                                annual_target_id,
                                year,
                                stabilimento_id,
                                kpi_id,
                                annual_target1_str,
                                annual_target2_str,
                                distribution_profile,
                                repartition_logic,
                                repartition_values_json,
                                profile_params_json,
                                is_target1_manual,
                                is_target2_manual,
                            ]
                        )
                    except KeyError as ke:
                        print(
                            f"ERROR [{func_name}]: KeyError while processing row {i+1} (ID: {at_row.get('id', 'N/A')}): '{ke}'. Row data: {dict(at_row)}. Skipping row."
                        )
                        continue  # Skip this problematic row
                    except Exception as e_row:
                        print(
                            f"ERROR [{func_name}]: Unexpected error processing row {i+1} (ID: {at_row.get('id', 'N/A')}): {e_row}. Row data: {dict(at_row)}. Skipping row."
                        )
                        print(traceback.format_exc())
                        continue  # Skip this problematic row

        print(
            f"INFO [{func_name}]: Esportazione per {output_filepath.name} completata."
        )

    except IOError as ioe:
        print(
            f"CRITICAL IO_ERROR [{func_name}] writing CSV file {output_filepath}: {ioe}"
        )
        print(traceback.format_exc())
    except Exception as e_csv:
        print(
            f"UNEXPECTED ERROR [{func_name}] during CSV writing to {output_filepath}: {e_csv}"
        )
        print(traceback.format_exc())


def _export_single_period_to_global_csv(
    db_path, table_name, period_col_name, output_filepath
):
    merged_data = {}
    header = [
        "kpi_id",
        "stabilimento_id",
        "year",
        period_col_name,
        "target1_value",
        "target2_value",
    ]
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # ... (order clause logic remains the same) ...
            order_clause_periodic = f"ORDER BY year, stabilimento_id, kpi_id, {period_col_name}, target_number"
            if period_col_name == "month_value":
                month_order_cases = " ".join(
                    [f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1, 13)]
                )
                order_clause_periodic = f"ORDER BY year, stabilimento_id, kpi_id, CASE {period_col_name} {month_order_cases} END, target_number"
            elif period_col_name == "quarter_value":
                quarter_order_cases = " ".join(
                    [f"WHEN 'Q{i}' THEN {i}" for i in range(1, 5)]
                )
                order_clause_periodic = f"ORDER BY year, stabilimento_id, kpi_id, CASE {period_col_name} {quarter_order_cases} END, target_number"
            elif period_col_name == "week_value":
                order_clause_periodic = f"ORDER BY year, stabilimento_id, kpi_id, SUBSTR({period_col_name}, 1, 4), CAST(SUBSTR({period_col_name}, INSTR({period_col_name}, '-W') + 2) AS INTEGER), target_number"

            query = (
                f"SELECT kpi_id, stabilimento_id, year, {period_col_name}, target_number, target_value "
                f"FROM {table_name} {order_clause_periodic}"
            )
            cursor.execute(query)
            for row in cursor.fetchall():
                key = (
                    row["kpi_id"],
                    row["stabilimento_id"],
                    row["year"],
                    row[period_col_name],
                )
                if key not in merged_data:
                    merged_data[key] = {"target1_value": None, "target2_value": None}
                if row["target_number"] == 1:
                    merged_data[key]["target1_value"] = row["target_value"]
                elif row["target_number"] == 2:
                    merged_data[key]["target2_value"] = row["target_value"]
    except Exception as e:
        print(
            f"ERRORE (Export Periodic {table_name}): Impossibile recuperare dati da {db_path}: {e}"
        )
        with open(output_filepath, "w", newline="", encoding="utf-8") as f_err:
            csv.writer(f_err).writerow(header)
        return

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        if not merged_data:
            print(f"Nessun dato trovato in {table_name} per {output_filepath.name}")
            return
        # ... (sorting logic for keys remains the same) ...
        sorted_keys = sorted(
            merged_data.keys(),
            key=lambda x: (
                x[2],
                x[1],
                x[0],
                (
                    calendar.month_name[:].index(x[3])
                    if period_col_name == "month_value" and x[3] in calendar.month_name
                    else (
                        int(x[3][1:])
                        if period_col_name == "quarter_value"
                        and x[3].startswith("Q")
                        and x[3][1:].isdigit()
                        else x[3]
                    )
                ),
            ),
        )
        for key in sorted_keys:
            kpi_id_val, stab_id_val, yr_val, period_val_str = key
            targets = merged_data[key]
            t1_str = (
                f"{targets['target1_value']:.2f}"
                if targets["target1_value"] is not None
                else ""
            )
            t2_str = (
                f"{targets['target2_value']:.2f}"
                if targets["target2_value"] is not None
                else ""
            )
            writer.writerow(
                [kpi_id_val, stab_id_val, yr_val, period_val_str, t1_str, t2_str]
            )
    print(f"Completata esportazione per: {output_filepath.name}")


def _export_stabilimenti_to_csv(output_filepath):
    """
    Exports all records from the stabilimenti table.
    """
    header = ["id", "name", "description"]
    all_stabilimenti_rows = []  # Changed variable name for clarity
    try:
        with sqlite3.connect(db.DB_STABILIMENTI) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description FROM stabilimenti ORDER BY name"
            )
            all_stabilimenti_rows = cursor.fetchall()
    except Exception as e:
        print(
            f"ERRORE (Export Stabilimenti): Impossibile recuperare dati da {db.DB_STABILIMENTI}: {e}"
        )
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile_err:
            csv.writer(csvfile_err).writerow(header)
        return

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)

        if not all_stabilimenti_rows:
            print(f"Nessun dato trovato in stabilimenti per {output_filepath.name}")
            return

        for row in all_stabilimenti_rows:
            # Safely access 'description'
            description_val = ""  # Default to empty string
            try:
                # Check if 'description' key exists and is not None
                if "description" in row.keys() and row["description"] is not None:
                    description_val = row["description"]
            except KeyError:
                # This handles if 'description' is somehow not a key in the row
                # (should be rare if schema and query are correct)
                pass  # description_val remains ""

            writer.writerow(
                [row["id"], row["name"], description_val]  # Use the safe variable
            )
    print(f"Completata esportazione per: {output_filepath.name}")

def _export_kpis_to_csv(output_filepath):
    header = [
        "id",
        "group_id",
        "group_name",
        "subgroup_id",
        "subgroup_name",
        "indicator_name",
        "description",
        "calculation_type",
        "unit_of_measure",
        "visible",
    ]
    all_kpis_data = []
    try:
        with sqlite3.connect(db.DB_KPIS) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
                SELECT
                    k.id, ksg.group_id, kg.name AS group_name, ki.subgroup_id,
                    ksg.name AS subgroup_name, ki.name AS indicator_name, k.description,
                    k.calculation_type, k.unit_of_measure, k.visible
                FROM kpis k
                JOIN kpi_indicators ki ON k.indicator_id = ki.id
                JOIN kpi_subgroups ksg ON ki.subgroup_id = ksg.id
                JOIN kpi_groups kg ON ksg.group_id = kg.id
                ORDER BY group_name, subgroup_name, indicator_name;
            """
            cursor.execute(query)
            all_kpis_data = cursor.fetchall()
    except Exception as e:
        print(f"ERRORE (Export KPIs): Impossibile recuperare dati da {db.DB_KPIS}: {e}")
        with open(output_filepath, "w", newline="", encoding="utf-8") as f_err:
            csv.writer(f_err).writerow(header)
        return

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        if not all_kpis_data:
            print(f"Nessun dato trovato in kpis per {output_filepath.name}")
            return
        for row in all_kpis_data:
            writer.writerow(
                [
                    row["id"],
                    row["group_id"],
                    row["group_name"],
                    row["subgroup_id"],
                    row["subgroup_name"],
                    row["indicator_name"],
                    row["description"],
                    row["calculation_type"],
                    row["unit_of_measure"],
                    "Sì" if row["visible"] else "No",
                ]
            )
    print(f"Completata esportazione per: {output_filepath.name}")


def package_all_csvs_as_zip(
    csv_base_path_str, output_zip_filepath_str=None, return_bytes_for_streamlit=False
):
    csv_base_path = Path(csv_base_path_str)
    files_to_zip = [
        csv_base_path / fname
        for fname in GLOBAL_CSV_FILES.values()
        if (csv_base_path / fname).exists()
    ]
    if not files_to_zip:
        msg = f"Nessun file CSV globale trovato in {csv_base_path} per l'esportazione ZIP."
        return False, msg

    zip_buffer = io.BytesIO() if return_bytes_for_streamlit else None
    actual_zip_filepath = (
        Path(output_zip_filepath_str) if output_zip_filepath_str else None
    )
    zip_target = zip_buffer if zip_buffer else actual_zip_filepath

    if not zip_target:
        return False, "Nessuna destinazione ZIP specificata."

    try:
        with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path_abs in files_to_zip:
                zipf.write(file_path_abs, arcname=file_path_abs.name)

        if (
            zip_buffer and actual_zip_filepath
        ):  # If bytes were requested AND a file path was given
            with open(actual_zip_filepath, "wb") as f_out:
                f_out.write(zip_buffer.getvalue())
            msg = f"File ZIP ({len(files_to_zip)} files) creato: {actual_zip_filepath} e pronto per download."
        elif actual_zip_filepath:  # Only file path given
            msg = f"File ZIP ({len(files_to_zip)} files) creato: {actual_zip_filepath}"
        else:  # Only bytes requested
            msg = f"Archivio ZIP ({len(files_to_zip)} files) pronto per il download."

        return True, zip_buffer.getvalue() if zip_buffer else msg
    except Exception as e:
        msg = f"Errore creazione ZIP: {e}"
        return False, msg


# Example of how you might call this from your main script, if needed for testing:
if __name__ == "__main__":
    # This assumes your database_manager.py has initialized the DBs
    # and app_config.py has CSV_EXPORT_BASE_PATH defined
    # and that database_manager defines DB_STABILIMENTI, DB_KPIS, DB_TARGETS etc.
    # For standalone testing, you might need to mock db or set up paths manually.

    # Ensure app_config constants are accessible, if not already imported in db.
    # from app_config import CSV_EXPORT_BASE_PATH

    # Check if database_manager populates 'data_retriever' or if it's a separate module.
    # If `db.data_retriever` is not how you access it, adjust the calls in `_export_annual_master_to_csv`

    # Initialize databases if not already done by another script
    # db.setup_databases() # Call this if the DBs might not exist/be set up

    print("Running export_manager.py for testing...")
    # You'll need to define a test export path
    test_export_dir = Path("./test_csv_exports")

    # Make sure you have constants like db.DB_TARGETS, db.DB_STABILIMENTI, db.DB_KPIS
    # correctly pointing to your database files. These would typically come from app_config.py
    # and be available through your 'db' (database_manager) import.

    # Mock or ensure data exists in your databases before running this.
    # For example, using the test data generation from your database_manager.py.

    if hasattr(db, "CSV_EXPORT_BASE_PATH"):
        export_path = db.CSV_EXPORT_BASE_PATH
    else:
        # Fallback if CSV_EXPORT_BASE_PATH is not directly on db object
        # You might need to import it from app_config directly
        try:
            from app_config import CSV_EXPORT_BASE_PATH

            export_path = CSV_EXPORT_BASE_PATH
        except ImportError:
            print(
                "CSV_EXPORT_BASE_PATH not found. Using local test_csv_exports directory."
            )
            export_path = test_export_dir

    export_all_data_to_global_csvs(str(export_path))
    package_all_csvs_as_zip(
        str(export_path), str(export_path / "global_data_export.zip")
    )
    print("Test export complete.")
