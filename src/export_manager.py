import csv
import zipfile
from pathlib import Path
import database_manager as db
import sqlite3
import calendar  # Import the calendar module for month names

# Define the names for the global CSV files
GLOBAL_CSV_FILES = {
    "days": "all_daily_kpi_targets.csv",
    "weeks": "all_weekly_kpi_targets.csv",
    "months": "all_monthly_kpi_targets.csv",
    "quarters": "all_quarterly_kpi_targets.csv",
    "annual": "all_annual_kpi_master_targets.csv",
    "stabilimenti": "dict_stabilimenti.csv",  # New dict table
    "kpis": "dict_kpis.csv",  # New dict table
}


def export_all_data_to_global_csvs(base_export_path_str):
    """
    Generates/Overwrites 5 global CSV files with all data from the databases,
    plus two dictionary tables for stabilimenti and KPI descriptions.
    """
    base_export_path = Path(base_export_path_str)
    base_export_path.mkdir(parents=True, exist_ok=True)

    print(f"Inizio esportazione globale CSV in: {base_export_path}")

    # 1. Export Annual Master Targets (from db_kpi_targets.db)
    try:
        print(f"Esportazione {GLOBAL_CSV_FILES['annual']}...")
        _export_annual_master_to_csv(base_export_path / GLOBAL_CSV_FILES["annual"])
    except Exception as e:
        print(f"ERRORE CRITICO durante esportazione master annuale: {e}")

    # 2. Export Periodic Data (Days, Weeks, Months, Quarters)
    periodic_db_map = {
        "days": (db.DB_KPI_DAYS, "daily_targets", "date_value"),
        "weeks": (db.DB_KPI_WEEKS, "weekly_targets", "week_value"),
        "months": (db.DB_KPI_MONTHS, "monthly_targets", "month_value"),
        "quarters": (db.DB_KPI_QUARTERS, "quarterly_targets", "quarter_value"),
    }

    for period_key, (db_path, table_name, period_col_name) in periodic_db_map.items():
        output_filepath = base_export_path / GLOBAL_CSV_FILES[period_key]
        try:
            print(f"Esportazione {GLOBAL_CSV_FILES[period_key]}...")
            _export_single_period_to_global_csv(
                db_path, table_name, period_col_name, output_filepath
            )
        except Exception as e:
            print(f"ERRORE CRITICO durante esportazione {period_key}: {e}")

    # 3. Export Dictionary Tables
    try:
        print(f"Esportazione {GLOBAL_CSV_FILES['stabilimenti']}...")
        _export_stabilimenti_to_csv(base_export_path / GLOBAL_CSV_FILES["stabilimenti"])
    except Exception as e:
        print(f"ERRORE CRITICO durante esportazione stabilimenti: {e}")

    try:
        print(f"Esportazione {GLOBAL_CSV_FILES['kpis']}...")
        _export_kpis_to_csv(base_export_path / GLOBAL_CSV_FILES["kpis"])
    except Exception as e:
        print(f"ERRORE CRITICO durante esportazione KPI dictionary: {e}")

    print(f"Esportazione globale CSV completata in {base_export_path}")


def _export_annual_master_to_csv(output_filepath):
    """
    Exports all records from the annual_targets table, enriched with KPI and stabilimento details.
    """
    # Fetch lookups first for efficiency
    all_stabilimenti_dict = {s["id"]: s["name"] for s in db.get_stabilimenti()}
    # kpi_id from annual_targets.kpi_id refers to kpis.id
    all_kpi_specs_dict = {k_spec["id"]: k_spec for k_spec in db.get_kpis()}

    header = [
        "annual_target_id",
        "year",
        "stabilimento_id",
        "stabilimento_name",
        "kpi_id",
        "kpi_group_name",
        "kpi_subgroup_name",
        "kpi_indicator_name",
        "kpi_description",
        "kpi_calculation_type",
        "kpi_unit_of_measure",
        "kpi_visible_in_ui",
        "annual_target1_value",
        "annual_target2_value",
        "distribution_profile",
        "repartition_logic",
        "repartition_values_json",
        "profile_params_json",
    ]

    all_annual_targets_rows = []
    try:
        with sqlite3.connect(db.DB_TARGETS) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM annual_targets ORDER BY year, stabilimento_id, kpi_id"
            )
            all_annual_targets_rows = cursor.fetchall()
    except Exception as e:
        print(
            f"ERRORE (Export Annual Master): Impossibile recuperare i target annuali: {e}"
        )
        # Create empty file with header on error
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile_err:
            writer_err = csv.writer(csvfile_err)
            writer_err.writerow(header)
        return

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)

        if not all_annual_targets_rows:
            print(f"Nessun dato trovato in annual_targets per {output_filepath.name}")
            return

        for at_row in all_annual_targets_rows:
            kpi_spec_id_val = at_row["kpi_id"]  # This is kpis.id
            kpi_details = all_kpi_specs_dict.get(
                kpi_spec_id_val
            )  # kpi_details is a dict from db.get_kpis()
            stab_name = all_stabilimenti_dict.get(at_row["stabilimento_id"], "N/D")

            k_group, k_sub, k_ind, k_desc, k_calc, k_unit, k_vis_str = ["N/D"] * 7
            if kpi_details:
                k_group = kpi_details["group_name"]
                k_sub = kpi_details["subgroup_name"]
                k_ind = kpi_details["indicator_name"]
                k_desc = kpi_details["description"]
                k_calc = kpi_details["calculation_type"]
                k_unit = kpi_details["unit_of_measure"]
                k_vis_str = "Sì" if kpi_details["visible"] else "No"

            writer.writerow(
                [
                    at_row["id"],
                    at_row["year"],
                    at_row["stabilimento_id"],
                    stab_name,
                    kpi_spec_id_val,
                    k_group,
                    k_sub,
                    k_ind,
                    k_desc,
                    k_calc,
                    k_unit,
                    k_vis_str,
                    (
                        f"{at_row['annual_target1']:.2f}"
                        if at_row["annual_target1"] is not None
                        else ""
                    ),
                    (
                        f"{at_row['annual_target2']:.2f}"
                        if at_row["annual_target2"] is not None
                        else ""
                    ),
                    at_row["distribution_profile"],
                    at_row["repartition_logic"],
                    at_row["repartition_values"],  # Already a JSON string
                    at_row.get(
                        "profile_params", ""
                    ),  # Use .get for sqlite3.Row if column might be missing (though schema setup should ensure it)
                ]
            )
    print(f"Completata esportazione per: {output_filepath.name}")


def _export_single_period_to_global_csv(
    db_path, table_name, period_col_name, output_filepath
):
    """
    Exports all data from a specific periodic table, merging target1 and target2 values.
    """
    merged_data = (
        {}
    )  # {(kpi_id, stabilimento_id, year, period_value): {'t1': val, 't2': val}}
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
            # Order by for consistent output, crucial for diffs and readability
            # The sorting for month/quarter names is handled in get_ripartiti_data,
            # here we use a simpler sort that should be mostly fine given how data is inserted.
            order_clause_periodic = f"ORDER BY year, stabilimento_id, kpi_id, {period_col_name}, target_number"
            if period_col_name == "month_value":  # Special sort for month names
                month_order_cases = " ".join(
                    [f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1, 13)]
                )
                order_clause_periodic = f"ORDER BY year, stabilimento_id, kpi_id, CASE {period_col_name} {month_order_cases} END, target_number"
            elif period_col_name == "quarter_value":  # Special sort for Q names
                quarter_order_cases = " ".join(
                    [f"WHEN 'Q{i}' THEN {i}" for i in range(1, 5)]
                )
                order_clause_periodic = f"ORDER BY year, stabilimento_id, kpi_id, CASE {period_col_name} {quarter_order_cases} END, target_number"
            elif period_col_name == "week_value":  # Special sort for Week string
                order_clause_periodic = f"ORDER BY year, stabilimento_id, kpi_id, SUBSTR({period_col_name}, 1, 4), CAST(SUBSTR({period_col_name}, INSTR({period_col_name}, '-W') + 2) AS INTEGER), target_number"

            query = (
                f"SELECT kpi_id, stabilimento_id, year, {period_col_name}, target_number, target_value "
                f"FROM {table_name} {order_clause_periodic}"
            )
            cursor.execute(query)
            all_rows_for_period = cursor.fetchall()

            for row in all_rows_for_period:
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
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile_err:
            writer_err = csv.writer(csvfile_err)
            writer_err.writerow(header)
        return

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        if not merged_data:
            print(f"Nessun dato trovato in {table_name} per {output_filepath.name}")
            return

        # Keys are already somewhat ordered by the SQL query. To ensure perfect order for CSV:
        # Re-sort Python-side if complex period names (like 'January') are not naturally sorted by SQL's text sort.
        # The enhanced SQL ORDER BY should mostly handle this.
        sorted_keys = sorted(
            merged_data.keys(),
            key=lambda x: (
                x[2],  # year
                x[1],  # stabilimento_id
                x[0],  # kpi_id
                # Custom sort for period value if needed, e.g. for month names
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
                ),  # default sort for date_value, week_value (which are YYYY-MM-DD or YYYY-Www)
            ),
        )

        for key in sorted_keys:
            kpi_id_val, stab_id_val, yr_val, period_val_str = key
            targets = merged_data[key]
            t1_val_str = (
                f"{targets['target1_value']:.2f}"
                if targets["target1_value"] is not None
                else ""
            )
            t2_val_str = (
                f"{targets['target2_value']:.2f}"
                if targets["target2_value"] is not None
                else ""
            )
            writer.writerow(
                [
                    kpi_id_val,
                    stab_id_val,
                    yr_val,
                    period_val_str,
                    t1_val_str,
                    t2_val_str,
                ]
            )
    print(f"Completata esportazione per: {output_filepath.name}")


def _export_stabilimenti_to_csv(output_filepath):
    """
    Exports all records from the stabilimenti table.
    """
    header = ["id", "name", "description"]
    all_stabilimenti = []
    try:
        with sqlite3.connect(db.DB_KPI_DESCRIPTION) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, description FROM stabilimenti ORDER BY name"
            )
            all_stabilimenti = cursor.fetchall()
    except Exception as e:
        print(
            f"ERRORE (Export Stabilimenti): Impossibile recuperare i dati degli stabilimenti: {e}"
        )
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile_err:
            writer_err = csv.writer(csvfile_err)
            writer_err.writerow(header)
        return

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        if not all_stabilimenti:
            print(f"Nessun dato trovato in stabilimenti per {output_filepath.name}")
            return

        for row in all_stabilimenti:
            writer.writerow([row["id"], row["name"], row["description"]])
    print(f"Completata esportazione per: {output_filepath.name}")


def _export_kpis_to_csv(output_filepath):
    """
    Exports all records from the kpis table, including group and subgroup names.
    """
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
        with sqlite3.connect(db.DB_KPI_DESCRIPTION) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
                SELECT
                    k.id,
                    k.group_id,
                    kg.name AS group_name,
                    k.subgroup_id,
                    ksg.name AS subgroup_name,
                    k.indicator_name,
                    k.description,
                    k.calculation_type,
                    k.unit_of_measure,
                    k.visible
                FROM
                    kpis k
                LEFT JOIN
                    kpi_groups kg ON k.group_id = kg.id
                LEFT JOIN
                    kpi_subgroups ksg ON k.subgroup_id = ksg.id
                ORDER BY
                    kg.name, ksg.name, k.indicator_name
            """
            cursor.execute(query)
            all_kpis_data = cursor.fetchall()
    except Exception as e:
        print(f"ERRORE (Export KPIs): Impossibile recuperare i dati dei KPI: {e}")
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile_err:
            writer_err = csv.writer(csvfile_err)
            writer_err.writerow(header)
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


def package_all_csvs_as_zip(csv_base_path_str, output_zip_filepath_str):
    csv_base_path = Path(csv_base_path_str)
    output_zip_filepath = Path(output_zip_filepath_str)
    files_to_zip = [
        csv_base_path / fname
        for fname in GLOBAL_CSV_FILES.values()
        if (csv_base_path / fname).exists()
    ]

    if not files_to_zip:
        msg = f"Nessun file CSV globale trovato in {csv_base_path} per l'esportazione ZIP."
        print(msg)
        return False, msg
    try:
        with zipfile.ZipFile(output_zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path_abs in files_to_zip:
                zipf.write(file_path_abs, arcname=file_path_abs.name)
        msg = f"File ZIP ({len(files_to_zip)} files) creato con successo: {output_zip_filepath}"
        print(msg)
        return True, msg
    except Exception as e:
        msg = f"Errore durante la creazione del file ZIP: {e}"
        print(msg)
        return False, msg
