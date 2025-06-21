# app_config.py
import configparser
from pathlib import Path
import numpy as np

# --- FILE PATHS CONFIGURATION ---
# APP_BASE_DIR is the directory where app_config.py resides (e.g., your_project_root/src2/)
APP_BASE_DIR = Path(__file__).resolve().parent

# PROJECT_ROOT_DIR is one level above APP_BASE_DIR
PROJECT_ROOT_DIR = APP_BASE_DIR.parent

CONFIG_FILE_PATH = (
    APP_BASE_DIR / "config.ini"
)  # config.ini is still within src2/ with app_config.py

config_parser = configparser.ConfigParser()

if not CONFIG_FILE_PATH.exists():
    print(
        f"WARNING: Configuration file {CONFIG_FILE_PATH} not found. Creating a default one."
    )
    default_config_content = f"""
[ProjectStructure]
DATABASE_SUBFOLDER = databases
CSV_EXPORT_SUBFOLDER = csv_exports

[DatabaseFileNames]
DB_KPIS = db_kpis.db
DB_STABILIMENTI = db_stabilimenti.db
DB_TARGETS = db_kpi_targets.db
DB_KPI_TEMPLATES = db_kpi_templates.db
DB_KPI_DAYS = db_kpi_days.db
DB_KPI_WEEKS = db_kpi_weeks.db
DB_KPI_MONTHS = db_kpi_months.db
DB_KPI_QUARTERS = db_kpi_quarters.db
"""
    with open(CONFIG_FILE_PATH, "w") as f_cfg:
        f_cfg.write(default_config_content.strip())

config_parser.read(CONFIG_FILE_PATH)

# --- Project Structure (Subfolders) ---
try:
    project_struct_config = config_parser["ProjectStructure"]
    DATABASE_SUBFOLDER_NAME = project_struct_config.get(
        "DATABASE_SUBFOLDER", "databases"
    )
    CSV_EXPORT_SUBFOLDER_NAME = project_struct_config.get(
        "CSV_EXPORT_SUBFOLDER", "csv_exports"
    )
except (KeyError, configparser.NoSectionError) as e:
    raise RuntimeError(
        f"Critical error: Missing [ProjectStructure] section or keys in {CONFIG_FILE_PATH}. Error: {e}"
    )

# Paths are now relative to PROJECT_ROOT_DIR
DATABASE_DIR = PROJECT_ROOT_DIR / DATABASE_SUBFOLDER_NAME
CSV_EXPORT_BASE_PATH = PROJECT_ROOT_DIR / CSV_EXPORT_SUBFOLDER_NAME

# Ensure these directories exist
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
CSV_EXPORT_BASE_PATH.mkdir(parents=True, exist_ok=True)


# --- Database File Paths (Loaded from config.ini, using the subfolder relative to project root) ---
try:
    db_filenames_config = config_parser["DatabaseFileNames"]
    DB_KPIS = DATABASE_DIR / db_filenames_config.get("DB_KPIS", "db_kpis.db")
    DB_STABILIMENTI = DATABASE_DIR / db_filenames_config.get(
        "DB_STABILIMENTI", "db_stabilimenti.db"
    )
    DB_TARGETS = DATABASE_DIR / db_filenames_config.get(
        "DB_TARGETS", "db_kpi_targets.db"
    )
    DB_KPI_TEMPLATES = DATABASE_DIR / db_filenames_config.get(
        "DB_KPI_TEMPLATES", "db_kpi_templates.db"
    )
    DB_KPI_DAYS = DATABASE_DIR / db_filenames_config.get(
        "DB_KPI_DAYS", "db_kpi_days.db"
    )
    DB_KPI_WEEKS = DATABASE_DIR / db_filenames_config.get(
        "DB_KPI_WEEKS", "db_kpi_weeks.db"
    )
    DB_KPI_MONTHS = DATABASE_DIR / db_filenames_config.get(
        "DB_KPI_MONTHS", "db_kpi_months.db"
    )
    DB_KPI_QUARTERS = DATABASE_DIR / db_filenames_config.get(
        "DB_KPI_QUARTERS", "db_kpi_quarters.db"
    )
except (KeyError, configparser.NoSectionError) as e:
    raise RuntimeError(
        f"Critical error: Missing [DatabaseFileNames] section or key in {CONFIG_FILE_PATH}. Error: {e}"
    )


# --- REPARTITION PARAMETERS (Python Constants) ---
WEIGHT_INITIAL_FACTOR_INC = 1.5
WEIGHT_FINAL_FACTOR_INC = 0.5
# ... (rest of the repartition and string constants remain the same) ...
WEIGHT_INITIAL_FACTOR_AVG = 1.2
WEIGHT_FINAL_FACTOR_AVG = 0.8
DEVIATION_SCALE_FACTOR_AVG = 0.2

SINE_AMPLITUDE_INCREMENTAL = 0.5
SINE_AMPLITUDE_MEDIA = 0.1
SINE_PHASE_OFFSET = -np.pi / 2

WEEKDAY_BIAS_FACTOR_INCREMENTAL = 0.5
WEEKDAY_BIAS_FACTOR_MEDIA = 0.8

# --- STRING CONSTANTS (Python Constants, critical for DB and logic) ---
CALC_TYPE_INCREMENTALE = "Incrementale"
CALC_TYPE_MEDIA = "Media"

REPARTITION_LOGIC_ANNO = "Anno"
REPARTITION_LOGIC_MESE = "Mese"
REPARTITION_LOGIC_TRIMESTRE = "Trimestre"
REPARTITION_LOGIC_SETTIMANA = "Settimana"

PROFILE_EVEN = "even_distribution"
PROFILE_ANNUAL_PROGRESSIVE = "annual_progressive"
PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS = "annual_progressive_weekday_bias"
PROFILE_TRUE_ANNUAL_SINUSOIDAL = "true_annual_sinusoidal"
PROFILE_MONTHLY_SINUSOIDAL = "monthly_sinusoidal"
PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE = "legacy_intra_period_progressive"
PROFILE_QUARTERLY_PROGRESSIVE = "quarterly_progressive"
PROFILE_QUARTERLY_SINUSOIDAL = "quarterly_sinusoidal"


if __name__ == "__main__":
    print("Loaded Configuration from app_config.py:")
    print(f"APP_BASE_DIR (where app_config.py is): {APP_BASE_DIR}")
    print(f"PROJECT_ROOT_DIR: {PROJECT_ROOT_DIR}")
    print(f"DATABASE_DIR: {DATABASE_DIR}")
    print(f"DB_KPIS: {DB_KPIS}")
    # ... print other DB paths ...
    print(f"CSV_EXPORT_BASE_PATH: {CSV_EXPORT_BASE_PATH}")
