# app_config.py
import configparser
from pathlib import Path
import numpy as np

# --- FILE PATHS CONFIGURATION ---
# APP_BASE_DIR is the directory where app_config.py resides
APP_BASE_DIR = Path(__file__).resolve().parent

# PROJECT_ROOT_DIR is one level above APP_BASE_DIR
PROJECT_ROOT_DIR = APP_BASE_DIR.parent

CONFIG_FILE_PATH = APP_BASE_DIR / "config.ini"

config_parser = configparser.ConfigParser()

# Default content for config.ini if it doesn't exist
DEFAULT_CONFIG_CONTENT = f"""
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

[GeneralPaths]
LOG_DIR_NAME = logs

[Interface.Streamlit]
SCRIPT_NAME = app_streamlit.py
COMMAND_MODULE_ARGS = streamlit run
APP_NAME = Streamlit

[Interface.Tkinter]
SCRIPT_NAME = app_tkinter.py
COMMAND_MODULE_ARGS =
APP_NAME = Tkinter
"""

if not CONFIG_FILE_PATH.exists():
    print(
        f"WARNING: Configuration file {CONFIG_FILE_PATH} not found. Creating a default one."
    )
    with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f_cfg:
        f_cfg.write(DEFAULT_CONFIG_CONTENT.strip())

config_parser.read(CONFIG_FILE_PATH, encoding="utf-8")

# --- General Paths (Loaded from config.ini) ---
try:
    general_paths_config = config_parser["GeneralPaths"]
    LOG_DIR_NAME_FROM_CONFIG = general_paths_config.get("LOG_DIR_NAME", "logs")
except (KeyError, configparser.NoSectionError) as e:
    print(
        f"Warning: Missing [GeneralPaths] section or LOG_DIR_NAME key in {CONFIG_FILE_PATH}. Using default 'logs'. Error: {e}"
    )
    LOG_DIR_NAME_FROM_CONFIG = "logs"  # Fallback

# --- Project Structure (Subfolders and Paths relative to PROJECT_ROOT_DIR) ---
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

DATABASE_DIR = PROJECT_ROOT_DIR / DATABASE_SUBFOLDER_NAME
CSV_EXPORT_BASE_PATH = PROJECT_ROOT_DIR / CSV_EXPORT_SUBFOLDER_NAME
LOG_DIR_PATH = (
    PROJECT_ROOT_DIR / LOG_DIR_NAME_FROM_CONFIG
)  # Log directory at project root level

# Ensure these directories exist
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
CSV_EXPORT_BASE_PATH.mkdir(parents=True, exist_ok=True)
LOG_DIR_PATH.mkdir(parents=True, exist_ok=True)  # Create log directory here


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

# --- Interface Configurations (Loaded from config.ini) ---
INTERFACE_CONFIGURATIONS = {}
for section_name in config_parser.sections():
    if section_name.startswith("Interface."):
        interface_key = section_name.split(".", 1)[1].lower()  # e.g., "streamlit"
        try:
            config = config_parser[section_name]
            INTERFACE_CONFIGURATIONS[interface_key] = {
                "script_name": config.get("SCRIPT_NAME", f"app_{interface_key}.py"),
                "command_module_args": config.get("COMMAND_MODULE_ARGS", "").strip(),
                "app_name": config.get("APP_NAME", interface_key.capitalize()),
            }
        except (KeyError, configparser.NoOptionError) as e:
            print(
                f"Warning: Incomplete configuration for interface section {section_name} in {CONFIG_FILE_PATH}. Error: {e}"
            )
            INTERFACE_CONFIGURATIONS[interface_key] = {  # Minimal fallback
                "script_name": f"app_{interface_key}.py",
                "command_module_args": "",
                "app_name": interface_key.capitalize(),
            }

# --- REPARTITION PARAMETERS (Python Constants) ---
WEIGHT_INITIAL_FACTOR_INC = 1.5
# ... (rest of your repartition and string constants remain the same) ...
SINE_PHASE_OFFSET = -np.pi / 2
WEEKDAY_BIAS_FACTOR_MEDIA = 0.8

# Distribution Profile Parameters (Example Values - Adjust as needed)
WEIGHT_INITIAL_FACTOR_INC = (
    0.5  # For incremental, progressive start (less at beginning)
)
WEIGHT_FINAL_FACTOR_INC = 1.5  # For incremental, progressive end (more at end)

WEIGHT_INITIAL_FACTOR_AVG = (
    1.6  # For average, progressive start (slightly more than avg)
)
WEIGHT_FINAL_FACTOR_AVG = 0.4  # For average, progressive end (slightly less than avg)

SINE_AMPLITUDE_INCREMENTAL = 0.3  # Amplitude for sinusoidal distribution (incremental)
SINE_AMPLITUDE_MEDIA = 0.2  # Amplitude for sinusoidal distribution (average)
SINE_PHASE_OFFSET = 0  # Phase offset for sinusoidal distributions (in radians)

WEEKDAY_BIAS_FACTOR_INCREMENTAL = (
    0.8  # e.g., weekends get 80% of a normal day's incremental target
)
WEEKDAY_BIAS_FACTOR_MEDIA = 1.1  # e.g., weekends have a media target 10% higher

DEVIATION_SCALE_FACTOR_AVG = (
    0.2  # How much the avg profile deviates from base avg (e.g. 20%)
)

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
PERIOD_TYPES_RESULTS = ["Giorno", "Settimana", "Mese", "Trimestre"]


if __name__ == "__main__":
    print("Loaded Configuration from app_config.py (reading from config.ini):")
    print(f"APP_BASE_DIR (where app_config.py is): {APP_BASE_DIR}")
    print(f"PROJECT_ROOT_DIR: {PROJECT_ROOT_DIR}")
    print(f"CONFIG_FILE_PATH: {CONFIG_FILE_PATH}")
    print(f"LOG_DIR_NAME from config: {LOG_DIR_NAME_FROM_CONFIG}")
    print(f"LOG_DIR_PATH (created at project root level): {LOG_DIR_PATH}")  # New print
    print(f"DATABASE_DIR: {DATABASE_DIR}")
    print(f"CSV_EXPORT_BASE_PATH: {CSV_EXPORT_BASE_PATH}")
    print("\nInterface Configurations:")
    for key, value in INTERFACE_CONFIGURATIONS.items():
        print(f"  {key}: {value}")
