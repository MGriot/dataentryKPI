# src/export_manager.py
import csv
import zipfile
import io  # For zip in memory for Streamlit
import traceback
from pathlib import Path
import calendar  # For month name sorting in periodic data

# Configuration import
try:
    from app_config import CSV_EXPORT_BASE_PATH

    # DB Path constants are not directly used here anymore if data_retriever handles all fetching.
    # If data_retriever needs them passed, they could be imported.
except ImportError:
    print(
        "CRITICAL WARNING: app_config.py not found on PYTHONPATH. "
        "CSV_EXPORT_BASE_PATH will not be correctly defined. "
    )
    CSV_EXPORT_BASE_PATH = "./fallback_csv_exports"  # Fallback

# Data retrieval import
_data_retriever_available = False
try:
    # Assuming data_retriever.py has or will have these functions:
    from data_retriever import (
        get_all_annual_target_entries_for_export,  # New function needed in data_retriever
        get_all_periodic_targets_for_export,  # New function needed in data_retriever (takes period_type)
        get_all_stabilimenti,  # Existing function, suitable
        get_all_kpis_detailed,  # Existing function, suitable
    )

    _data_retriever_available = True
except ImportError:
    print(
        "CRITICAL WARNING: data_retriever.py or its required export functions not found. "
        "Export functionality will be severely limited or non-operational. "
        "Mocks will be used if this script is run directly."
    )

    # Mock functions if data_retriever is not available (for script to load, not for real use)
    def get_all_annual_target_entries_for_export():
        print("MOCK: get_all_annual_target_entries_for_export called")
        return []

    def get_all_periodic_targets_for_export(period_type: str):
        print(f"MOCK: get_all_periodic_targets_for_export({period_type}) called")
        return []

    def get_all_stabilimenti(only_visible=False):
        print("MOCK: get_all_stabilimenti called")
        return []

    def get_all_kpis_detailed(only_visible=False):
        print("MOCK: get_all_kpis_detailed called")
        return []


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

# Ensure CSV_EXPORT_BASE_PATH is a Path object
_CSV_EXPORT_BASE_PATH_OBJ = Path(CSV_EXPORT_BASE_PATH)


def export_all_data_to_global_csvs(base_export_path_str: str = None):
    """
    Generates/Overwrites global CSV files with all data, fetched via data_retriever.
    """
    func_name = "export_all_data_to_global_csvs"

    target_export_path = _CSV_EXPORT_BASE_PATH_OBJ
    if base_export_path_str:  # Allow overriding the default from app_config
        target_export_path = Path(base_export_path_str)

    print(
        f"INFO [{func_name}]: Inizio esportazione globale CSV in: {target_export_path}"
    )

    if not _data_retriever_available:
        print(
            f"CRITICAL ERROR [{func_name}]: data_retriever module not available. Aborting export."
        )
        return

    try:
        target_export_path.mkdir(parents=True, exist_ok=True)
    except Exception as e_mkdir:
        print(
            f"CRITICAL ERROR [{func_name}]: Impossibile creare la cartella di esportazione '{target_export_path}': {e_mkdir}"
        )
        print(traceback.format_exc())
        return

    export_successful_count = 0
    export_failed_count = 0
    export_details = []

    # 1. Export Annual Master Targets
    annual_export_file = GLOBAL_CSV_FILES["annual"]
    annual_output_filepath = target_export_path / annual_export_file
    print(f"INFO [{func_name}]: Tentativo esportazione {annual_export_file}...")
    try:
        _export_annual_master_to_csv(annual_output_filepath)
        print(f"SUCCESS [{func_name}]: Esportazione {annual_export_file} completata.")
        export_successful_count += 1
        export_details.append(f"[SUCCESS] {annual_export_file}")
    except Exception as e_annual:
        msg = f"Fallita esportazione master annuale ({annual_export_file}): {e_annual}"
        print(f"CRITICAL ERROR [{func_name}]: {msg}")
        print(traceback.format_exc())
        export_failed_count += 1
        export_details.append(f"[FAILED]  {annual_export_file}: {msg}")
        _write_empty_csv_with_header(
            annual_output_filepath,
            [
                "annual_target_id",
                "year",
                "stabilimento_id",
                "kpi_id",
                "annual_target1_value",
                "annual_target2_value",
                "distribution_profile",
                "repartition_logic",
                "repartition_values_json",
                "profile_params_json",
                "is_target1_manual",
                "is_target2_manual",
            ],
        )

    # 2. Export Periodic Data (Days, Weeks, Months, Quarters)
    # The new `get_all_periodic_targets_for_export` in data_retriever should handle
    # fetching from the correct DB based on period_type.
    periodic_map_for_export = {
        "days": ("date_value", GLOBAL_CSV_FILES["days"]),
        "weeks": ("week_value", GLOBAL_CSV_FILES["weeks"]),
        "months": ("month_value", GLOBAL_CSV_FILES["months"]),
        "quarters": ("quarter_value", GLOBAL_CSV_FILES["quarters"]),
    }

    for period_key, (
        period_col_name,
        periodic_file_name,
    ) in periodic_map_for_export.items():
        periodic_output_filepath = target_export_path / periodic_file_name
        print(
            f"INFO [{func_name}]: Tentativo esportazione {periodic_file_name} (Type: {period_key})..."
        )
        try:
            _export_single_period_to_global_csv(
                period_key, period_col_name, periodic_output_filepath
            )
            print(
                f"SUCCESS [{func_name}]: Esportazione {periodic_file_name} completata."
            )
            export_successful_count += 1
            export_details.append(f"[SUCCESS] {periodic_file_name}")
        except Exception as e_periodic:
            msg = f"Fallita esportazione dati periodici '{period_key}' ({periodic_file_name}): {e_periodic}"
            print(f"CRITICAL ERROR [{func_name}]: {msg}")
            print(traceback.format_exc())
            export_failed_count += 1
            export_details.append(f"[FAILED]  {periodic_file_name}: {msg}")
            _write_empty_csv_with_header(
                periodic_output_filepath,
                [
                    "kpi_id",
                    "stabilimento_id",
                    "year",
                    period_col_name,
                    "target1_value",
                    "target2_value",
                ],
            )

    # 3. Export Dictionary Tables
    # Stabilimenti
    stab_export_file = GLOBAL_CSV_FILES["stabilimenti"]
    stab_output_filepath = target_export_path / stab_export_file
    print(f"INFO [{func_name}]: Tentativo esportazione {stab_export_file}...")
    try:
        _export_stabilimenti_to_csv(stab_output_filepath)
        print(f"SUCCESS [{func_name}]: Esportazione {stab_export_file} completata.")
        export_successful_count += 1
        export_details.append(f"[SUCCESS] {stab_export_file}")
    except Exception as e_stab:
        msg = f"Fallita esportazione stabilimenti ({stab_export_file}): {e_stab}"
        print(f"CRITICAL ERROR [{func_name}]: {msg}")
        print(traceback.format_exc())
        export_failed_count += 1
        export_details.append(f"[FAILED]  {stab_export_file}: {msg}")
        _write_empty_csv_with_header(
            stab_output_filepath, ["id", "name", "description", "visible"]
        )

    # KPIs
    kpis_export_file = GLOBAL_CSV_FILES["kpis"]
    kpis_output_filepath = target_export_path / kpis_export_file
    print(f"INFO [{func_name}]: Tentativo esportazione {kpis_export_file}...")
    try:
        _export_kpis_to_csv(kpis_output_filepath)
        print(f"SUCCESS [{func_name}]: Esportazione {kpis_export_file} completata.")
        export_successful_count += 1
        export_details.append(f"[SUCCESS] {kpis_export_file}")
    except Exception as e_kpis:
        msg = f"Fallita esportazione dizionario KPI ({kpis_export_file}): {e_kpis}"
        print(f"CRITICAL ERROR [{func_name}]: {msg}")
        print(traceback.format_exc())
        export_failed_count += 1
        export_details.append(f"[FAILED]  {kpis_export_file}: {msg}")
        _write_empty_csv_with_header(
            kpis_output_filepath,
            [
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
            ],
        )

    # --- Summary ---
    print(f"INFO [{func_name}]: Esportazione globale CSV terminata.")
    print(f"INFO [{func_name}]: Riepilogo esportazioni in '{target_export_path}':")
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


def _write_empty_csv_with_header(filepath: Path, header: list):
    """Helper to write an empty CSV file with just a header, typically on error."""
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f_err:
            csv.writer(f_err).writerow(header)
        print(f"    INFO: Scritto file CSV vuoto con header: {filepath.name}")
    except Exception as e_write_empty:
        print(
            f"    WARN: Impossibile scrivere file CSV vuoto con header per {filepath.name}: {e_write_empty}"
        )


def _export_annual_master_to_csv(output_filepath: Path):
    """Exports all annual_targets records, fetched via data_retriever."""
    header = [
        "annual_target_id",
        "year",
        "stabilimento_id",
        "kpi_id",
        "annual_target1_value",
        "annual_target2_value",
        "distribution_profile",
        "repartition_logic",
        "repartition_values_json",
        "profile_params_json",
        "is_target1_manual",
        "is_target2_manual",
        "target1_is_formula_based",
        "target1_formula",
        "target1_formula_inputs",
        "target2_is_formula_based",
        "target2_formula",
        "target2_formula_inputs",
    ]

    # data_retriever.get_all_annual_target_entries_for_export() should return a list of dicts or Row objects
    all_annual_targets_rows = get_all_annual_target_entries_for_export()
    if all_annual_targets_rows is None:  # Check if data_retriever indicated an error
        print(
            f"    WARN (_export_annual_master): Data retriever returned None. Cannot export."
        )
        all_annual_targets_rows = []  # Treat as empty

    print(
        f"DEBUG (_export_annual_master): Fetched {len(all_annual_targets_rows)} rows for annual targets."
    )

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for row_data in all_annual_targets_rows:
            # Assuming row_data is a dict-like object (e.g., from sqlite3.Row or a manually constructed dict)
            # Ensure all keys exist, provide defaults for missing ones for robustness
            writer.writerow(
                [
                    row_data["id"],
                    row_data["year"],
                    row_data["stabilimento_id"],
                    row_data["kpi_id"],
                    (
                        f"{row_data['annual_target1']:.2f}"
                        if row_data["annual_target1"] is not None
                        else ""
                    ),
                    (
                        f"{row_data['annual_target2']:.2f}"
                        if row_data["annual_target2"] is not None
                        else ""
                    ),
                    row_data["distribution_profile"],
                    row_data["repartition_logic"],
                    row_data["repartition_values"],
                    row_data["profile_params"],
                    1 if row_data["is_target1_manual"] else 0,
                    1 if row_data["is_target2_manual"] else 0,
                    1 if row_data["target1_is_formula_based"] else 0,
                    row_data["target1_formula"],
                    row_data["target1_formula_inputs"],
                    1 if row_data["target2_is_formula_based"] else 0,
                    row_data["target2_formula"],
                    row_data["target2_formula_inputs"],
                ]
            )


def _export_single_period_to_global_csv(
    period_type: str, period_col_name: str, output_filepath: Path
):
    """
    Exports all periodic target data for a given period_type (days, weeks, etc.),
    fetched via data_retriever. Merges Target1 and Target2 onto the same row.
    """
    header = [
        "kpi_id",
        "stabilimento_id",
        "year",
        period_col_name,
        "target1_value",
        "target2_value",
    ]

    # data_retriever.get_all_periodic_targets_for_export(period_type)
    # This new function should return all rows for that period type, including 'target_number'.
    # Example row from retriever: {'kpi_id':1, 'stabilimento_id':1, 'year':2023, period_col_name:'2023-01-01', 'target_number':1, 'target_value':100}
    all_periodic_rows = get_all_periodic_targets_for_export(period_type=period_type)
    if all_periodic_rows is None:
        print(
            f"    WARN (_export_single_period {period_type}): Data retriever returned None. Cannot export."
        )
        all_periodic_rows = []

    print(
        f"DEBUG (_export_single_period {period_type}): Fetched {len(all_periodic_rows)} raw rows for {period_type} targets."
    )

    merged_data = (
        {}
    )  # Key: (kpi_id, stab_id, year, period_value), Value: {'target1_value': V, 'target2_value': V}
    for row in all_periodic_rows:
        # Ensure row is dict-like
        row_dict = dict(row) if not isinstance(row, dict) else row
        key = (
            row_dict.get("kpi_id"),
            row_dict.get("stabilimento_id"),
            row_dict.get("year"),
            row_dict.get(
                period_col_name
            ),  # period_col_name holds the actual period value like '2023-01-01' or 'January'
        )
        if None in key:  # Skip if key components are missing
            print(
                f"    WARN (_export_single_period {period_type}): Skipping row with missing key components: {row_dict}"
            )
            continue

        if key not in merged_data:
            merged_data[key] = {"target1_value": None, "target2_value": None}

        target_number = row_dict.get("target_number")
        target_value = row_dict.get("target_value")

        if target_number == 1:
            merged_data[key]["target1_value"] = target_value
        elif target_number == 2:
            merged_data[key]["target2_value"] = target_value

    # Sorting logic for keys (important for consistent output)
    def sort_key_periodic(k_tuple):
        # k_tuple = (kpi_id, stab_id, year, period_value_str)
        year_val = k_tuple[2]
        stab_id_val = k_tuple[1]
        kpi_id_val = k_tuple[0]
        period_val_str = k_tuple[3]

        period_sort_metric = period_val_str  # Default for dates, week strings
        if period_type == "months":
            try:  # Robust month name to number for sorting
                period_sort_metric = list(calendar.month_name).index(period_val_str)
            except ValueError:
                period_sort_metric = 0  # Fallback
        elif period_type == "quarters":
            try:
                period_sort_metric = (
                    int(period_val_str[1:]) if period_val_str.startswith("Q") else 0
                )
            except ValueError:
                period_sort_metric = 0  # Fallback
        return (year_val, stab_id_val, kpi_id_val, period_sort_metric)

    sorted_keys = sorted(merged_data.keys(), key=sort_key_periodic)

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for key_tuple in sorted_keys:
            kpi_id_val, stab_id_val, yr_val, period_val_output = (
                key_tuple  # period_val_output is the actual string value
            )
            targets = merged_data[key_tuple]
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
                [kpi_id_val, stab_id_val, yr_val, period_val_output, t1_str, t2_str]
            )


def _export_stabilimenti_to_csv(output_filepath: Path):
    """Exports all stabilimenti records, fetched via data_retriever."""
    header = ["id", "name", "description", "visible"]
    all_stabilimenti_rows = get_all_stabilimenti(
        visible_only=False
    )  # Fetch all for dictionary
    if all_stabilimenti_rows is None:
        all_stabilimenti_rows = []
    print(
        f"DEBUG (_export_stabilimenti): Fetched {len(all_stabilimenti_rows)} rows for stabilimenti."
    )

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for row_data in all_stabilimenti_rows:
            writer.writerow(
                [
                    row_data.get("id"),
                    row_data.get("name"),
                    row_data.get(
                        "description", ""
                    ),  # Ensure description exists, default to empty
                    1 if row_data.get("visible") else 0,
                ]
            )


def _export_kpis_to_csv(output_filepath: Path):
    """Exports all detailed KPI records, fetched via data_retriever."""
    header = [
        "kpi_spec_id",  # This is kpis.id
        "indicator_id",  # This is kpi_indicators.id
        "group_name",
        "subgroup_name",
        "indicator_name",
        "description",
        "calculation_type",
        "unit_of_measure",
        "visible",
    ]
    # get_all_kpis_detailed should return list of dicts/Rows with keys like:
    # id (kpis.id), actual_indicator_id (kpi_indicators.id), group_name, subgroup_name, indicator_name, etc.
    all_kpis_data = get_all_kpis_detailed(
        only_visible=False
    )  # Fetch all for dictionary
    if all_kpis_data is None:
        all_kpis_data = []
    print(f"DEBUG (_export_kpis): Fetched {len(all_kpis_data)} rows for KPIs.")

    with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for row_data in all_kpis_data:
            writer.writerow(
                [
                    row_data["id"],  # This is kpis.id -> kpi_spec_id
                    row_data["actual_indicator_id"],  # This is kpi_indicators.id
                    row_data["group_name"],
                    row_data["subgroup_name"],
                    row_data["indicator_name"],
                    row_data["description"],
                    row_data["calculation_type"],
                    row_data["unit_of_measure"],
                    1 if row_data["visible"] else 0,
                ]
            )


def package_all_csvs_as_zip(
    csv_base_path_str: str = None,
    output_zip_filepath_str: str = None,
    return_bytes_for_streamlit: bool = False,
):
    """
    Packages all globally defined CSV files from the csv_base_path into a ZIP archive.
    Can save to a file or return as bytes for Streamlit download.
    """
    func_name = "package_all_csvs_as_zip"

    source_csv_path = _CSV_EXPORT_BASE_PATH_OBJ
    if csv_base_path_str:  # Allow override
        source_csv_path = Path(csv_base_path_str)

    files_to_zip = [
        source_csv_path / fname
        for fname in GLOBAL_CSV_FILES.values()
        if (source_csv_path / fname).exists()
    ]

    if not files_to_zip:
        msg = f"Nessun file CSV globale trovato in {source_csv_path} per l'esportazione ZIP."
        print(f"INFO [{func_name}]: {msg}")
        return False, (None if return_bytes_for_streamlit else msg)

    zip_buffer = io.BytesIO() if return_bytes_for_streamlit else None
    actual_zip_filepath = (
        Path(output_zip_filepath_str) if output_zip_filepath_str else None
    )
    zip_target = zip_buffer if zip_buffer else actual_zip_filepath

    if not zip_target:  # Should not happen if one of the options is chosen
        msg = "Nessuna destinazione ZIP specificata (né file, né buffer)."
        print(f"ERROR [{func_name}]: {msg}")
        return False, (None if return_bytes_for_streamlit else msg)

    try:
        with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path_abs in files_to_zip:
                zipf.write(
                    file_path_abs, arcname=file_path_abs.name
                )  # Use relative name in ZIP

        num_files = len(files_to_zip)
        if (
            zip_buffer and actual_zip_filepath
        ):  # Bytes requested AND file path given (save and return bytes)
            with open(actual_zip_filepath, "wb") as f_out:
                f_out.write(zip_buffer.getvalue())
            msg = f"File ZIP ({num_files} files) creato: {actual_zip_filepath} e buffer pronto."
            print(f"INFO [{func_name}]: {msg}")
            return True, zip_buffer.getvalue()
        elif actual_zip_filepath:  # Only file path given
            msg = f"File ZIP ({num_files} files) creato: {actual_zip_filepath}"
            print(f"INFO [{func_name}]: {msg}")
            return True, msg
        elif zip_buffer:  # Only bytes requested
            msg = f"Archivio ZIP ({num_files} files) creato in memoria."
            print(f"INFO [{func_name}]: {msg}")
            return True, zip_buffer.getvalue()
        else:  # Should not be reached if logic above is correct
            return False, "Logica ZIP imprevista."

    except Exception as e_zip:
        msg = f"Errore creazione ZIP: {e_zip}"
        print(f"ERROR [{func_name}]: {msg}")
        print(traceback.format_exc())
        return False, (None if return_bytes_for_streamlit else msg)


if __name__ == "__main__":
    print("Running export_manager.py for testing...")
    # This test assumes app_config.CSV_EXPORT_BASE_PATH is defined.
    # It also assumes data_retriever can provide data or mocks are active.

    # Use the path from app_config by default for the test
    test_export_dir = _CSV_EXPORT_BASE_PATH_OBJ
    test_zip_file = test_export_dir / "test_global_data_export.zip"

    print(f"Test export directory: {test_export_dir}")
    print(f"Test ZIP output file: {test_zip_file}")

    # Create dummy data for data_retriever mocks if not available
    if not _data_retriever_available:
        print("INFO: data_retriever not available, using mocks for export test.")

        # Provide some minimal mock data structure if needed by export functions
        def get_all_annual_target_entries_for_export():
            return [
                {
                    "id": 1,
                    "year": 2023,
                    "stabilimento_id": 1,
                    "kpi_id": 1,
                    "annual_target1": 100,
                    "annual_target2": 200,
                }
            ]

        def get_all_periodic_targets_for_export(period_type: str):
            if period_type == "days":
                return [
                    {
                        "kpi_id": 1,
                        "stabilimento_id": 1,
                        "year": 2023,
                        "date_value": "2023-01-01",
                        "target_number": 1,
                        "target_value": 10,
                    }
                ]
            return []

        def get_all_stabilimenti(only_visible=False):
            return [
                {"id": 1, "name": "Test Stab", "description": "Desc", "visible": True}
            ]

        def get_all_kpis_detailed(only_visible=False):
            return [
                {
                    "id": 1,
                    "actual_indicator_id": 101,
                    "group_name": "Grp",
                    "subgroup_name": "Sub",
                    "indicator_name": "Ind",
                }
            ]

    # Run the main export function
    export_all_data_to_global_csvs(str(test_export_dir))

    # Run the ZIP packaging function
    success, result = package_all_csvs_as_zip(
        csv_base_path_str=str(test_export_dir),
        output_zip_filepath_str=str(test_zip_file),
        return_bytes_for_streamlit=False,  # For file output in test
    )

    if success:
        print(f"Test ZIP packaging successful: {result}")
    else:
        print(f"Test ZIP packaging failed: {result}")

    print("\nTest export_manager.py complete.")
    print(
        f"Please check the directory '{test_export_dir}' for output CSVs and ZIP file."
    )
