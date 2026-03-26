# src/export_manager.py
import csv
import zipfile
import io
import traceback
from pathlib import Path
import json
import datetime

# Configuration import
try:
    from src.config.settings import CSV_EXPORT_BASE_PATH
except ImportError:
    print("CRITICAL WARNING: app_config.py not found. Using fallback for CSV_EXPORT_BASE_PATH.")
    CSV_EXPORT_BASE_PATH = "./fallback_csv_exports"

# Data retrieval import
try:
    from src.data_retriever import (
        get_all_plants,
        get_all_kpi_nodes,
        get_all_kpi_definitions_for_export,
        get_all_kpi_plant_visibility,
        get_all_annual_targets_enriched,
        get_all_periodic_targets_unified,
    )
    _data_retriever_available = True
except ImportError as e:
    print(f"CRITICAL WARNING: data_retriever.py or its functions not found. Export will fail. Error: {e}")
    traceback.print_exc()
    _data_retriever_available = False

# Optimized CSV File Set
GLOBAL_CSV_FILES = {
    "plants": "dict_plants.csv",
    "kpi_nodes": "dict_kpi_hierarchy.csv",
    "kpi_definitions": "dict_kpi_definitions.csv",
    "kpi_plant_visibility": "dict_kpi_plant_visibility.csv",
    "annual": "all_annual_targets.csv",
    "periodic": "all_periodic_targets.csv",
    "manifest": "export_manifest.json"
}

_CSV_EXPORT_BASE_PATH_OBJ = Path(CSV_EXPORT_BASE_PATH)

def _export_to_csv(output_filepath: Path, data: list, header: list[str]):
    """Generic and safe function to export a list of dictionaries to a CSV file."""
    if not data:
        print(f"INFO: No data provided for {output_filepath.name}, skipping file creation.")
        return
    try:
        dict_data = [dict(row) if not isinstance(row, dict) else row for row in data]
        with open(output_filepath, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=header, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(dict_data)
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

    # 1. Plants
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["plants"], 
                   get_all_plants(visible_only=False), 
                   ["id", "name", "description", "visible", "color"])

    # 2. KPI Hierarchy (Nodes)
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["kpi_nodes"], 
                   get_all_kpi_nodes(), 
                   ["id", "name", "parent_id", "node_type"])

    # 3. KPI Definitions (Merged & Enriched)
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["kpi_definitions"], 
                   get_all_kpi_definitions_for_export(), 
                   ["kpi_id", "indicator_name", "hierarchy_path", "description", "calculation_type", "unit_of_measure", "visible"])

    # 5. Plant Visibility
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["kpi_plant_visibility"], 
                   get_all_kpi_plant_visibility(), 
                   ["kpi_id", "plant_id", "is_enabled"])

    # 6. Annual Targets (Enriched)
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["annual"], 
                   get_all_annual_targets_enriched(), 
                   ["id", "year", "plant_id", "plant_name", "kpi_id", "indicator_name", "annual_target1", "annual_target2", "repartition_logic"])

    # 7. Periodic Targets (Unified)
    _export_to_csv(target_export_path / GLOBAL_CSV_FILES["periodic"], 
                   get_all_periodic_targets_unified(), 
                   ["year", "plant_id", "kpi_id", "target_number", "period_type", "period_value", "target_value"])

    # 8. Manifest
    manifest = {
        "export_date": datetime.datetime.now().isoformat(),
        "files": list(GLOBAL_CSV_FILES.values()),
        "schema_version": "2.0",
        "system": "dataentryKPI"
    }
    with open(target_export_path / GLOBAL_CSV_FILES["manifest"], "w") as f:
        json.dump(manifest, f, indent=4)

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
