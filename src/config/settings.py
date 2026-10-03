"""
Runtime settings: where the SQLite databases and CSV exports live.

Resolution order for each directory (first match wins):
  1. Environment variable (KPI_DB_DIR / KPI_EXPORT_DIR) -- what the containers use.
  2. Optional user_config/settings.json ("database_base_dir" / "csv_export_base_dir";
     the legacy "database_path" key is still honoured as an alias).
  3. <project root>/databases and <project root>/csv_exports.

Paths are resolved on every call (not frozen at import time), so tests and settings
reloads take effect immediately everywhere.
"""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "user_config" / "settings.json"

DEFAULT_SETTINGS = {
    "database_base_dir": str(PROJECT_ROOT / "databases"),
    "csv_export_base_dir": str(PROJECT_ROOT / "csv_exports"),
}


def load_settings() -> dict:
    merged = DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            user_settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return merged
    if isinstance(user_settings, dict):
        legacy_db_path = user_settings.get("database_path")
        if legacy_db_path and not user_settings.get("database_base_dir"):
            user_settings["database_base_dir"] = legacy_db_path
        merged.update({k: v for k, v in user_settings.items() if v})
    return merged


SETTINGS = load_settings()


def reload_app_settings():
    global SETTINGS
    SETTINGS = load_settings()


def get_database_dir() -> Path:
    return Path(os.environ.get("KPI_DB_DIR") or SETTINGS["database_base_dir"])


def get_database_path(db_name: str) -> Path:
    """Returns the full Path for a given database file name."""
    return get_database_dir() / db_name


def get_csv_export_path() -> Path:
    """Returns the full Path for the CSV export directory."""
    return Path(os.environ.get("KPI_EXPORT_DIR") or SETTINGS["csv_export_base_dir"])
