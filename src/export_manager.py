# export_manager.py
import csv
import os  # For zip functionality if still needed for these global files
import zipfile  # For zip functionality
from pathlib import Path
import database_manager as db  # To access DB paths and query functions
import sqlite3  # For direct DB connection

# Define the names for the global CSV files
GLOBAL_CSV_FILES = {
    "days": "all_daily_kpi_targets.csv",
    "weeks": "all_weekly_kpi_targets.csv",
    "months": "all_monthly_kpi_targets.csv",
    "quarters": "all_quarterly_kpi_targets.csv",
    "annual": "all_annual_kpi_master_targets.csv",
}


def export_all_data_to_global_csvs(base_export_path_str):
    """
    Generates/Overwrites 5 global CSV files with all data from the databases.
    """
    base_export_path = Path(base_export_path_str)
    base_export_path.mkdir(parents=True, exist_ok=True)  # Ensure base path exists

    print(f"Inizio esportazione globale CSV in: {base_export_path}")

    # 1. Export Annual Master Targets (from db_kpi_targets.db)
    try:
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
            _export_single_period_to_global_csv(
                db_path, table_name, period_col_name, output_filepath
            )
        except Exception as e:
            print(f"ERRORE CRITICO durante esportazione {period_key}: {e}")

    print(f"Esportazione globale CSV completata in {base_export_path}")


def _export_annual_master_to_csv(output_filepath):
    """
    Exports all records from the annual_targets table, enriched with KPI and stabilimento details.
    """
    all_annual_targets = []
    # Fetch lookups first for efficiency
    all_stabilimenti_dict = {s["id"]: s["name"] for s in db.get_stabilimenti()}
    all_kpi_specs_dict = {k["id"]: k for k in db.get_kpis()}  # kpi_id from kpis table

    print(f"Esportazione master annuale in: {output_filepath}...")
    try:
        with sqlite3.connect(db.DB_TARGETS) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Fetch all annual targets, ordered for consistency
            cursor.execute(
                "SELECT * FROM annual_targets ORDER BY id"
            )  # Order by annual_target_id
            all_annual_targets = cursor.fetchall()
    except Exception as e:
        print(
            f"ERRORE (Export Annual Master): Impossibile recuperare i target annuali dal DB: {e}"
        )
        # Create empty file with header on error to prevent old file from persisting if query fails
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
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
                ]
            )
        return

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
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
        ]
        writer.writerow(header)

        if not all_annual_targets:
            print(f"Nessun dato trovato in annual_targets per {output_filepath.name}")
            return

        for at_row in all_annual_targets:  # at_row is sqlite3.Row
            kpi_id_for_spec = at_row["kpi_id"]  # This is the kpi_id from the kpis table
            kpi_details = all_kpi_specs_dict.get(kpi_id_for_spec)
            stab_name = all_stabilimenti_dict.get(at_row["stabilimento_id"], "N/D")

            k_group, k_sub, k_ind, k_desc, k_calc, k_unit, k_vis = ["N/D"] * 7
            if kpi_details:  # kpi_details is a dict (from sqlite3.Row)
                k_group = kpi_details["group_name"]
                k_sub = kpi_details["subgroup_name"]
                k_ind = kpi_details["indicator_name"]
                k_desc = kpi_details["description"]
                k_calc = kpi_details["calculation_type"]
                k_unit = kpi_details["unit_of_measure"]
                k_vis = "Sì" if kpi_details["visible"] else "No"

            writer.writerow(
                [
                    at_row["id"],
                    at_row["year"],
                    at_row["stabilimento_id"],
                    stab_name,
                    kpi_id_for_spec,
                    k_group,
                    k_sub,
                    k_ind,
                    k_desc,
                    k_calc,
                    k_unit,
                    k_vis,
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
                ]
            )
    print(f"Completata esportazione per: {output_filepath.name}")


def _export_single_period_to_global_csv(
    db_path, table_name, period_col_name, output_filepath
):
    """
    Exports all data from a specific periodic table (e.g., daily_targets),
    merging target1 and target2 values into single rows.
    The CSV will contain all kpi_id, stabilimento_id, year, period_value combinations.
    """
    # This dictionary will store data as:
    # {(kpi_id, stabilimento_id, year, period_value): {'target1_value': val1, 'target2_value': val2}}
    merged_data = {}
    print(f"Esportazione periodica {table_name} in: {output_filepath}...")

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Select all columns needed, order by the unique key parts of the periodic table
            # excluding target_number for now, as we'll pivot on it.
            query = (
                f"SELECT kpi_id, stabilimento_id, year, {period_col_name}, target_number, target_value "
                f"FROM {table_name} "
                f"ORDER BY year, stabilimento_id, kpi_id, {period_col_name}, target_number"
            )
            cursor.execute(query)
            all_rows_for_period = cursor.fetchall()

            for row in all_rows_for_period:
                # Create a unique key for each period instance (excluding target_number)
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
        # Create empty file with header on error
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(
                [
                    "kpi_id",
                    "stabilimento_id",
                    "year",
                    period_col_name,
                    "target1_value",
                    "target2_value",
                ]
            )
        return

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        header = [
            "kpi_id",
            "stabilimento_id",
            "year",
            period_col_name,
            "target1_value",
            "target2_value",
        ]
        writer.writerow(header)

        if not merged_data:
            print(f"Nessun dato trovato in {table_name} per {output_filepath.name}")
            return

        # Sort the merged_data keys for consistent CSV output
        # Sorting by year, stabilimento_id, kpi_id, then period_value
        # Note: Period value sorting might need specific logic for months/quarters if string sort isn't ideal
        # The SQL query already orders them, so iterating through sorted(merged_data.items()) should be mostly fine.
        # However, if period_col_name is a string like "January", "February", standard sort is alphabetical.
        # For simplicity, we use the order from the dictionary which is somewhat based on insertion from sorted SQL.
        # For truly robust sorting of period_value, custom sort key for months/quarters would be needed here.
        sorted_keys = sorted(merged_data.keys(), key=lambda x: (x[2], x[1], x[0], x[3]))

        for key in sorted_keys:
            kpi_id, stab_id, yr, period_val = key
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
            writer.writerow([kpi_id, stab_id, yr, period_val, t1_val_str, t2_val_str])
    print(f"Completata esportazione per: {output_filepath.name}")


def package_all_csvs_as_zip(csv_base_path_str, output_zip_filepath_str):
    """
    Creates a ZIP file containing the 5 global CSV files found in the csv_base_path.
    """
    csv_base_path = Path(csv_base_path_str)
    output_zip_filepath = Path(output_zip_filepath_str)

    # List only the expected global CSV files if they exist
    files_to_zip = []
    for fname in GLOBAL_CSV_FILES.values():
        file_path = csv_base_path / fname
        if file_path.exists():
            files_to_zip.append(file_path)

    if not files_to_zip:
        print(
            f"Nessun file CSV globale trovato in {csv_base_path} per l'esportazione ZIP."
        )
        return False, "Nessun CSV globale da zippare."

    try:
        with zipfile.ZipFile(output_zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path_abs in files_to_zip:
                # Store files at the root of the ZIP archive using their original names
                arcname = file_path_abs.name
                zipf.write(file_path_abs, arcname)
        print(
            f"File ZIP ({len(files_to_zip)} files) creato con successo: {output_zip_filepath}"
        )
        return True, f"Dati esportati in {output_zip_filepath}"
    except Exception as e:
        print(f"Errore durante la creazione del file ZIP: {e}")
        return False, f"Errore creazione ZIP: {e}"
