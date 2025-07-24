from pathlib import Path
import json

# --- Settings File Path ---
SETTINGS_FILE = Path(__file__).resolve().parent.parent / "settings.json"

# --- Default Settings ---
DEFAULT_SETTINGS = {
    "display_names": {
        "target1": "Target 1",
        "target2": "Target 2"
    },
    "database_base_dir": str(Path(__file__).resolve().parent.parent / "databases"),
    "csv_export_base_dir": str(Path(__file__).resolve().parent.parent / "csv_exports"),
    "stabilimento_colors": {}
}

# --- Load Settings ---
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            # Merge with defaults to ensure new settings are present
            merged_settings = DEFAULT_SETTINGS.copy()
            merged_settings.update(settings)
            return merged_settings
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()

# --- App Settings (Global Access) ---
SETTINGS = load_settings()

# --- Dynamic Path Getters ---
def get_database_path(db_name: str) -> Path:
    """Returns the full Path for a given database file name."""
    return Path(SETTINGS["database_base_dir"]) / db_name

def get_csv_export_path() -> Path:
    """Returns the full Path for the CSV export directory."""
    return Path(SETTINGS["csv_export_base_dir"])

# --- Constants for Direct Import ---
CSV_EXPORT_BASE_PATH = get_csv_export_path()
