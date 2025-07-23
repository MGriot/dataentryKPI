
from pathlib import Path
import json

# --- Database Paths ---
# Define the base directory for the databases relative to the project root.
DATABASE_DIR = Path(__file__).resolve().parent.parent / "databases"
DATABASE_DIR.mkdir(parents=True, exist_ok=True) # Ensure the directory exists

DB_KPI_TEMPLATES = DATABASE_DIR / "db_kpi_templates.db"
DB_KPIS = DATABASE_DIR / "db_kpis.db"
DB_STABILIMENTI = DATABASE_DIR / "db_stabilimenti.db"
DB_TARGETS = DATABASE_DIR / "db_kpi_targets.db"
DB_KPI_DAYS = DATABASE_DIR / "db_kpi_days.db"
DB_KPI_WEEKS = DATABASE_DIR / "db_kpi_weeks.db"
DB_KPI_MONTHS = DATABASE_DIR / "db_kpi_months.db"
DB_KPI_QUARTERS = DATABASE_DIR / "db_kpi_quarters.db"

# --- CSV Export Path ---
CSV_EXPORT_BASE_PATH = Path(__file__).resolve().parent.parent / "csv_exports"

# --- Settings File Path ---
SETTINGS_FILE = Path(__file__).resolve().parent.parent / "settings.json"

# --- Default Settings ---
DEFAULT_SETTINGS = {
    "display_names": {
        "target1": "Target 1",
        "target2": "Target 2"
    },
    "database_path": str(DATABASE_DIR),
    "stabilimento_colors": {}
}

# --- Load Settings ---
def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_SETTINGS

# --- App Settings ---
SETTINGS = load_settings()
