# src/export_manager.py
import csv
import zipfile
import io
import traceback
from pathlib import Path
import json

import traceback

# Configuration import
try:
    from src.app_config import CSV_EXPORT_BASE_PATH
except ImportError:
    print("CRITICAL WARNING: app_config.py not found. Using fallback for CSV_EXPORT_BASE_PATH.")
    CSV_EXPORT_BASE_PATH = "./fallback_csv_exports"

# Data retrieval import
try:
    from src.data_retriever import (
        get_all_annual_target_entries_for_export,
        get_all_periodic_targets_for_export,
        get_all_plants,
        get_kpi_groups,
        get_all_kpi_subgroups,
        get_all_kpi_indicators,
        get_all_kpis_detailed,
    )
    _data_retriever_available = True
except ImportError as e:
    print(f"CRITICAL WARNING: data_retriever.py or its functions not found. Export will fail. Error: {e}")
    traceback.print_exc() # Print full traceback
    _data_retriever_available = False

# Define the names for the global CSV files, matching the database tables
GLOBAL_CSV_FILES = {
    "plants": "dict_plants.csv",
    "kpi_groups": "dict_kpi_groups.csv",
    "kpi_subgroups": "dict_kpi_subgroups.csv",
    "kpi_indicators": "dict_kpi_indicators.csv",
    "kpis": "dict_kpis.csv",
    "annual": "all_annual_kpi_master_targets.csv",
    "days": "all_daily_kpi_targets.csv",
    "weeks": "all_weekly_kpi_targets.csv",
    "months": "all_monthly_kpi_targets.csv",
    "quarters": "all_quarterly_kpi_targets.csv",
    "settings": "dict_settings.csv",
}

_CSV_EXPORT_BASE_PATH_OBJ = Path(CSV_EXPORT_BASE_PATH)

def _export_to_csv(output_filepath: Path, data: list[dict], header: list[str]):
    """Generic and safe function to export a list of dictionaries to a CSV file."""
    if not data:
        print(f"INFO: No data provided for {output_filepath.name}, skipping file creation.")
        return
    try:
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
            # extrasaction='ignore' prevents errors if data dicts have extra keys not in the header.
            writer = csv.DictWriter(csvfile, fieldnames=header, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
    except Exception as e:
        print(f"ERROR writing to {output_filepath.name}: {e}")
        traceback.print_exc()

def export_all_data_to_global_csvs(base_export_path_str: str = None):
    """Generates/Overwrites global CSV files with all data, fetched via data_retriever."""
    if not _data_retriever_available:
        print("CRITICAL ERROR: data_retriever module not available. Aborting export.")
        return

    target_export_path = Path(base_export_path_str) if base_export_path_str else _CSV_EXPORT_BASE_PATH_OBJ
    target_export_path.mkdir(parents=True, exist_ok=True)
    print(f"INFO: Starting global CSV export to: {target_export_path}")

    # KPI Structure (Normalized)
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["kpi_groups"], get_all_kpi_groups(), ["id", "name"])
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["kpi_subgroups"], get_all_kpi_subgroups(), ["id", "name", "group_id", "indicator_template_id"])
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["kpi_indicators"], get_all_kpi_indicators(), ["id", "name", "subgroup_id"])
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["kpis"], get_all_kpis(), ["id", "indicator_id", "description", "calculation_type", "unit_of_measure", "visible"])

    # Plants
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["plants"], get_all_plants(visible_only=False), ["id", "name", "description", "visible", "color"])

    # Annual Targets
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["annual"], get_all_annual_target_entries_for_export(), [
        "id", "year", "plant_id", "kpi_id", "annual_target1", "annual_target2", "repartition_logic",
        "repartition_values", "distribution_profile", "profile_params", "is_target1_manual", "is_target2_manual",
        "target1_is_formula_based", "target1_formula", "target1_formula_inputs", "target2_is_formula_based",
        "target2_formula", "target2_formula_inputs"
    ])

    # Periodic Targets
    periodic_map = {"days": "date_value", "weeks": "week_value", "months": "month_value", "quarters": "quarter_value"}
    for period_type, period_col in periodic_map.items():
        data = get_all_periodic_targets_for_export(period_type)
        header = ["year", "plant_id", "kpi_id", "target_number", period_col, "target_value"]
        _export_to_csv(target_export_path / GLOBAL_CSV_FILES[period_type], data, header)

    print("INFO: Global CSV export finished.")


def package_all_csvs_as_zip(csv_base_path_str: str = None, output_zip_filepath_str: str = None, return_bytes_for_streamlit: bool = False):
    """Packages all globally defined CSV files into a ZIP archive."""
    source_csv_path = Path(csv_base_path_str) if csv_base_path_str else _CSV_EXPORT_BASE_PATH_OBJ
    files_to_zip = [source_csv_path / fname for fname in GLOBAL_CSV_FILES.values() if (source_csv_path / fname).exists()]

    if not files_to_zip:
        return False, "No CSV files found to package."

    zip_target = io.BytesIO() if return_bytes_for_streamlit else Path(output_zip_filepath_str)
    
    try:
        with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files_to_zip:
                zipf.write(file_path, arcname=file_path.name)
        
        if return_bytes_for_streamlit:
            return True, zip_target.getvalue()
        else:
            return True, f"ZIP file created: {zip_target}"
    except Exception as e:
        traceback.print_exc()
        return False, f"Failed to create ZIP file: {e}"

