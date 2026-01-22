from pathlib import Path
import json
CALC_TYPE_INCREMENTAL = "Incremental"
CALC_TYPE_AVERAGE = "Average"

# --- Settings File Path ---
SETTINGS_FILE = Path(__file__).resolve().parents[1] / "settings.json"
USER_CONSTANTS_FILE = Path(__file__).resolve().parent / "user_constants.json"

# --- Default Settings ---
DEFAULT_SETTINGS = {
    "display_names": {
        "target1": "Target 1",
        "target2": "Target 2"
    },
    "database_base_dir": str(Path(__file__).resolve().parent / "databases"),
    "csv_export_base_dir": str(Path(__file__).resolve().parent / "csv_exports"),
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

# --- Load Calculation Constants ---
def load_calculation_constants():
    try:
        with open(USER_CONSTANTS_FILE, 'r') as f:
            user_constants = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        user_constants = {} # Start with empty dict if file not found or invalid

    # Define default constants, including CALC_TYPEs
    default_constants = {
        'WEIGHT_INITIAL_FACTOR_INC': 1.6,
        'WEIGHT_FINAL_FACTOR_INC': 0.4,
        'WEIGHT_INITIAL_FACTOR_AVG': 1.6,
        'WEIGHT_FINAL_FACTOR_AVG': 0.4,
        'SINE_AMPLITUDE_INCREMENTAL': 0.3,
        'SINE_AMPLITUDE_MEDIA': 0.2,
        'SINE_PHASE_OFFSET': 0,
        'WEEKDAY_BIAS_FACTOR_INCREMENTAL': 0.8,
        'WEEKDAY_BIAS_FACTOR_MEDIA': 1.1,
        'DEVIATION_SCALE_FACTOR_AVG': 0.2,
        # Add CALC_TYPEs here
        'CALC_TYPE_INCREMENTAL': CALC_TYPE_INCREMENTAL, # Use the directly defined constant
        'CALC_TYPE_AVERAGE': CALC_TYPE_AVERAGE,       # Use the directly defined constant
        # Add other PROFILE and REPARTITION_LOGIC constants here as well
        'PROFILE_EVEN': "even_distribution",
        'PROFILE_ANNUAL_PROGRESSIVE': "annual_progressive",
        'PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS': "annual_progressive_weekday_bias",
        'PROFILE_TRUE_ANNUAL_SINUSOIDAL': "true_annual_sinusoidal",
        'PROFILE_MONTHLY_SINUSOIDAL': "monthly_sinusoidal",
        'PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE': "legacy_intra_period_progressive",
        'PROFILE_QUARTERLY_PROGRESSIVE': "quarterly_progressive",
        'PROFILE_QUARTERLY_SINUSOIDAL': "quarterly_sinusoidal",
        'REPARTITION_LOGIC_YEAR': "Year",
        'REPARTITION_LOGIC_MONTH': "Month",
        'REPARTITION_LOGIC_QUARTER': "Quarter",
        'REPARTITION_LOGIC_WEEK': "Week",
    }

    # Merge user constants over defaults
    merged_constants = default_constants.copy()
    merged_constants.update(user_constants)
    return merged_constants

# --- App Settings (Global Access) ---
SETTINGS = load_settings()
CALCULATION_CONSTANTS = load_calculation_constants()

def reload_app_settings():
    global SETTINGS
    global CALCULATION_CONSTANTS
    SETTINGS = load_settings()
    CALCULATION_CONSTANTS = load_calculation_constants()
    print(f"DEBUG: CALCULATION_CONSTANTS loaded: {CALCULATION_CONSTANTS}")

# --- Dynamic Path Getters ---
def get_database_path(db_name: str) -> Path:
    """Returns the full Path for a given database file name."""
    return Path(SETTINGS["database_base_dir"]) / db_name

def get_csv_export_path() -> Path:
    """Returns the full Path for the CSV export directory."""
    return Path(SETTINGS["csv_export_base_dir"])

# --- Constants for Direct Import ---
CSV_EXPORT_BASE_PATH = get_csv_export_path()