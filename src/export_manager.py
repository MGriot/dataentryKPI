# src/export_manager.py
"""
CSV exports (human-readable) and the raw ZIP backup consumed by import_manager.

Two formats:
* Human-readable CSVs (joined names, one file per "table key") -- for people and BI tools.
  Not restorable.
* Raw backup ZIP: a 1:1 dump of every table (all columns, primary/foreign keys kept) plus a
  manifest. NULL is written as \\N so it survives the round trip (an empty string is a
  real empty string). User accounts, sessions and API keys are deliberately NOT included.
"""
import csv
import datetime
import io
import json
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from src import data_retriever
from src.data_access import db

NULL_TOKEN = "\\N"
BACKUP_FORMAT_VERSION = 2
MANIFEST_NAME = "manifest.json"

# (table, database file, CSV name inside the ZIP)
RAW_BACKUP_TABLES: List[Tuple[str, str, str]] = [
    ("plants", db.PLANTS, "raw_plants.csv"),
    ("kpi_nodes", db.KPIS, "raw_kpi_nodes.csv"),
    ("kpi_indicators", db.KPIS, "raw_kpi_indicators.csv"),
    ("kpis", db.KPIS, "raw_kpis.csv"),
    ("kpi_plant_visibility", db.KPIS, "raw_kpi_plant_visibility.csv"),
    ("units_of_measure", db.KPIS, "raw_units_of_measure.csv"),
    ("kpi_indicator_templates", db.TEMPLATES, "raw_kpi_indicator_templates.csv"),
    ("template_defined_indicators", db.TEMPLATES, "raw_template_defined_indicators.csv"),
    ("global_kpi_splits", db.TEMPLATES, "raw_global_kpi_splits.csv"),
    ("global_split_years", db.TEMPLATES, "raw_global_split_years.csv"),
    ("global_split_indicators", db.TEMPLATES, "raw_global_split_indicators.csv"),
    ("app_meta", db.TEMPLATES, "raw_app_meta.csv"),
    ("annual_targets", db.TARGETS, "raw_annual_targets.csv"),
    ("kpi_annual_target_values", db.TARGETS, "raw_kpi_annual_target_values.csv"),
    ("kpi_targets", db.TARGETS, "raw_kpi_targets.csv"),
    ("daily_targets", db.DAYS, "raw_daily_targets.csv"),
    ("weekly_targets", db.WEEKS, "raw_weekly_targets.csv"),
    ("monthly_targets", db.MONTHS, "raw_monthly_targets.csv"),
    ("quarterly_targets", db.QUARTERS, "raw_quarterly_targets.csv"),
    ("actual_measurements", db.ACTUALS, "raw_actual_measurements.csv"),
    ("kpi_definition_history", db.HISTORY, "raw_kpi_definition_history.csv"),
    ("target_value_history", db.HISTORY, "raw_target_value_history.csv"),
]

LEAN_HEADER = ["Indicator", "Plant", "Year", "PeriodType", "PeriodValue", "TargetID", "Value"]

# table key -> (rows getter, header, file name)
SINGLE_TABLE_EXPORTS: Dict[str, Tuple[Callable[[], list], List[str], str]] = {
    "Plants": (lambda: data_retriever.get_all_plants(visible_only=False),
               ["id", "name", "description", "visible", "color"], "dict_plants.csv"),
    "KPI Hierarchy": (data_retriever.get_all_kpi_nodes,
                      ["id", "name", "parent_id", "node_type", "is_active"], "dict_kpi_hierarchy.csv"),
    "KPI Definitions": (data_retriever.get_all_kpi_definitions_for_export,
                        ["kpi_id", "indicator_name", "hierarchy_path", "description", "calculation_type",
                         "unit_of_measure", "visible", "formula_string"], "dict_kpi_definitions.csv"),
    "Plant Visibility": (data_retriever.get_all_kpi_plant_visibility,
                         ["kpi_id", "plant_id", "is_enabled"], "dict_kpi_plant_visibility.csv"),
    "Annual Targets": (data_retriever.get_all_annual_targets_enriched,
                       ["year", "plant_id", "plant_name", "kpi_id", "indicator_name", "target_number",
                        "target_value", "is_manual", "is_formula_based"], "all_annual_targets.csv"),
    "Periodic Targets": (data_retriever.get_all_periodic_targets_unified,
                         ["year", "plant_id", "kpi_id", "target_number", "period_type", "period_value",
                          "target_value"], "all_periodic_targets.csv"),
}


def _write_csv(path: Path, rows: list, header: List[str]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_lean_data_to_csv(target_dir: str) -> Path:
    path = Path(target_dir) / "lean_target_data.csv"
    _write_csv(path, data_retriever.get_lean_targets(), LEAN_HEADER)
    return path


def export_single_table(table_key: str, target_dir: str) -> Path:
    """Writes one human-readable table to target_dir and returns its path (header-only if empty)."""
    if table_key not in SINGLE_TABLE_EXPORTS:
        raise ValueError(f"Unknown table '{table_key}'. Use one of: {', '.join(SINGLE_TABLE_EXPORTS)}.")
    getter, header, filename = SINGLE_TABLE_EXPORTS[table_key]
    path = Path(target_dir) / filename
    _write_csv(path, getter(), header)
    return path


def build_backup_zip() -> bytes:
    """Raw dump of every table (see module docstring) as ZIP bytes."""
    buffer = io.BytesIO()
    manifest = {
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "system": "dataentryKPI",
        "null_token": NULL_TOKEN,
        "tables": {},
    }
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for table, db_name, csv_name in RAW_BACKUP_TABLES:
            if not db.path(db_name).exists():
                continue
            with db.connect(db_name) as conn:
                columns = db.table_columns(conn, table)
                if not columns:
                    continue
                cols_sql = ", ".join(db.ident(c) for c in columns)
                data = conn.execute(f"SELECT {cols_sql} FROM {db.ident(table)}").fetchall()
            text = io.StringIO()
            writer = csv.writer(text)
            writer.writerow(columns)
            for row in data:
                writer.writerow([NULL_TOKEN if v is None else v for v in row])
            zf.writestr(csv_name, text.getvalue())
            manifest["tables"][table] = {"file": csv_name, "rows": len(data), "columns": columns}
        zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
    return buffer.getvalue()
