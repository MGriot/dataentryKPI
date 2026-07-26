# src/db_core/setup.py
import sqlite3
import json
import traceback  # For more detailed error reporting if needed
from pathlib import Path  # To ensure CSV_EXPORT_BASE_PATH is handled as a Path object

# Import configurations from app_config.py
from src.config import settings as app_config 

from src.interfaces.common_ui.constants import (
        CALC_TYPE_INCREMENTAL,
        CALC_TYPE_AVERAGE,
        REPARTITION_LOGIC_YEAR,
        PROFILE_ANNUAL_PROGRESSIVE,
        WEIGHT_INITIAL_FACTOR_INC,
        WEIGHT_FINAL_FACTOR_INC,
        SINE_AMPLITUDE_INCREMENTAL,
        SINE_PHASE_OFFSET,
        WEEKDAY_BIAS_FACTOR_INCREMENTAL,
        WEIGHT_INITIAL_FACTOR_AVG,
        WEIGHT_FINAL_FACTOR_AVG,
        DEVIATION_SCALE_FACTOR_AVG,
        SINE_AMPLITUDE_MEDIA,
        WEEKDAY_BIAS_FACTOR_MEDIA,
    )

def setup_databases():
    """
    Sets up all necessary SQLite databases and their tables.
    Creates tables if they don't exist and attempts to alter existing tables
    to add new columns if they are missing.
    """
    print("Starting database setup...")

    csv_export_path = app_config.get_csv_export_path()
    if csv_export_path:
        try:
            csv_export_path.mkdir(parents=True, exist_ok=True)
            print(f"INFO: Ensured directory for CSV export: {csv_export_path}")
        except Exception as e:
            print(
                f"WARN: Could not create/verify directory CSV_EXPORT_BASE_PATH {csv_export_path}: {e}"
            )
            print(traceback.format_exc())

    db_base_dir = Path(app_config.SETTINGS["database_base_dir"])
    if db_base_dir:
        try:
            db_base_dir.mkdir(parents=True, exist_ok=True)
            print(f"INFO: Ensured directory for databases: {db_base_dir}")
        except Exception as e:
            print(
                f"WARN: Could not create/verify directory for databases {db_base_dir}: {e}"
            )
            print(traceback.format_exc())

    # --- DB_KPI_TEMPLATES Setup ---
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    print(f"Setting up tables in {db_kpi_templates_path}...")
    try:
        with sqlite3.connect(db_kpi_templates_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_indicator_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT
                )"""
            )
            cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS template_defined_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_id INTEGER NOT NULL,
                    indicator_name_in_template TEXT NOT NULL,
                    default_description TEXT,
                    default_calculation_type TEXT NOT NULL CHECK(default_calculation_type IN ('{CALC_TYPE_INCREMENTAL}', '{CALC_TYPE_AVERAGE}')),
                    default_unit_of_measure TEXT,
                    default_visible BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (template_id) REFERENCES kpi_indicator_templates(id) ON DELETE CASCADE,
                    UNIQUE (template_id, indicator_name_in_template)
                )"""
            )
            
            # --- New table for Global Annual Splits ---
            cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS global_kpi_splits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    year INTEGER,
                    repartition_logic TEXT NOT NULL DEFAULT '{REPARTITION_LOGIC_YEAR}',
                    repartition_values TEXT NOT NULL DEFAULT '{{}}',
                    distribution_profile TEXT NOT NULL DEFAULT '{PROFILE_ANNUAL_PROGRESSIVE}',
                    profile_params TEXT DEFAULT '{{}}'
                )"""
            )

            # Support for multiple years per global split
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS global_split_years (
                    global_split_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    PRIMARY KEY (global_split_id, year),
                    FOREIGN KEY (global_split_id) REFERENCES global_kpi_splits(id) ON DELETE CASCADE
                )"""
            )

            # Migration: Move data from global_kpi_splits.year to global_split_years if any
            cursor.execute("SELECT id, year FROM global_kpi_splits WHERE year IS NOT NULL")
            existing_splits = cursor.fetchall()
            for split_id, year in existing_splits:
                cursor.execute("INSERT OR IGNORE INTO global_split_years (global_split_id, year) VALUES (?, ?)", (split_id, year))
            
            # Req 9: Indicators afflicted by a global split
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS global_split_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    global_split_id INTEGER NOT NULL,
                    indicator_id INTEGER NOT NULL,
                    override_distribution_profile TEXT,
                    FOREIGN KEY (global_split_id) REFERENCES global_kpi_splits(id) ON DELETE CASCADE,
                    UNIQUE(global_split_id, indicator_id)
                )"""
            )
            conn.commit()

            # Seed the built-in distribution curves as ordinary (editable, deletable) Global
            # Split Templates -- now that KPI Explorer only offers Global Split Templates rather
            # than a standalone curve picker, these presets are how the old curve options stay
            # available. year=NULL and no global_split_years rows means they're year-agnostic
            # and show up under every year filter (see get_all_global_splits).
            from src.utils.repartition_utils import get_weighted_proportions, get_sinusoidal_proportions
            import calendar as _calendar_for_presets
            _month_names = [_calendar_for_presets.month_name[i] for i in range(1, 13)]
            _presets = [
                ("Preset: Uniform / Even", "even_distribution", [1.0 / 12] * 12),
                ("Preset: Annual Progressive", "annual_progressive", get_weighted_proportions(12, 0.8, 1.2, decreasing=True)),
                ("Preset: Annual Progressive (Weekday Bias)", "annual_progressive_weekday_bias", [1.0 / 12] * 12),
                ("Preset: Sinusoidal Seasonal Curve", "true_annual_sinusoidal", get_sinusoidal_proportions(12, 0.1, 0.0)),
                ("Preset: Event Based (Shutdowns)", "event_based_spikes_or_dips", [1.0 / 12] * 12),
            ]
            for _name, _profile, _props in _presets:
                _weights = {_month_names[i]: round(_props[i] * 100, 4) for i in range(12)}
                cursor.execute(
                    """INSERT OR IGNORE INTO global_kpi_splits
                       (name, year, repartition_logic, repartition_values, distribution_profile, profile_params)
                       VALUES (?, NULL, 'Month', ?, ?, '{}')""",
                    (_name, json.dumps(_weights), _profile)
                )
            conn.commit()
        print(f"Table setup in {db_kpi_templates_path} completed.")
    except sqlite3.Error as e:
        print(f"ERROR during setup of {db_kpi_templates_path}: {e}")
        print(traceback.format_exc())

    # --- DB_KPIS Setup ---
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    print(f"Setting up tables in {db_kpis_path}...")
    try:
        with sqlite3.connect(db_kpis_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "PRAGMA foreign_keys = ON;"  # Ensure FK constraints are active during setup for consistency
            )

            # --- KPI Hierarchy (Recursive) ---
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    parent_id INTEGER,
                    node_type TEXT CHECK(node_type IN ('group', 'subgroup', 'folder')),
                    custom_level_label TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (parent_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE,
                    UNIQUE (name, parent_id)
                )"""
            )

            # Migration check for kpi_nodes columns
            cursor.execute("PRAGMA table_info(kpi_nodes)")
            node_cols = {col[1] for col in cursor.fetchall()}
            if "custom_level_label" not in node_cols:
                cursor.execute("ALTER TABLE kpi_nodes ADD COLUMN custom_level_label TEXT")
            if "is_active" not in node_cols:
                cursor.execute("ALTER TABLE kpi_nodes ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")

            # Migration: If kpi_groups and kpi_subgroups exist, migrate them to kpi_nodes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kpi_groups'")
            if cursor.fetchone():
                print("Migrating legacy groups and subgroups to recursive kpi_nodes...")
                # Migrate groups
                cursor.execute("INSERT OR IGNORE INTO kpi_nodes (id, name, node_type) SELECT id, name, 'group' FROM kpi_groups")
                # Migrate subgroups
                cursor.execute("INSERT OR IGNORE INTO kpi_nodes (id, name, parent_id, node_type) SELECT id + 1000, name, group_id, 'subgroup' FROM kpi_subgroups")
                
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    node_id INTEGER NOT NULL,
                    subgroup_id INTEGER,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (node_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE,
                    UNIQUE (name, node_id)
                )"""
            )
            # Migration check for kpi_indicators columns
            cursor.execute("PRAGMA table_info(kpi_indicators)")
            indicator_cols_info = {col[1]: col for col in cursor.fetchall()}
            
            if 'subgroup_id' in indicator_cols_info and indicator_cols_info['subgroup_id'][3] == 1:
                # subgroup_id is NOT NULL (col[3] is the 'notnull' flag) - RECREATE to fix
                print("Recreating kpi_indicators to fix NOT NULL constraint on subgroup_id...")
                cursor.execute("ALTER TABLE kpi_indicators RENAME TO kpi_indicators_old")
                cursor.execute(
                    """CREATE TABLE kpi_indicators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        node_id INTEGER NOT NULL,
                        subgroup_id INTEGER,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        FOREIGN KEY (node_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE,
                        UNIQUE (name, node_id)
                    )"""
                )
                cursor.execute("INSERT INTO kpi_indicators (id, name, node_id, subgroup_id) SELECT id, name, node_id, subgroup_id FROM kpi_indicators_old")
                cursor.execute("DROP TABLE kpi_indicators_old")
            
            cursor.execute("PRAGMA table_info(kpi_indicators)")
            indicator_cols = {col[1] for col in cursor.fetchall()}
            if "is_active" not in indicator_cols:
                cursor.execute("ALTER TABLE kpi_indicators ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")

            # Ensure node_id is populated from subgroup_id if it's missing (legacy data)
            if 'subgroup_id' in indicator_cols:
                cursor.execute("UPDATE kpi_indicators SET node_id = subgroup_id + 1000 WHERE (node_id IS NULL OR node_id = 0) AND subgroup_id IS NOT NULL")
            cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS kpis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    indicator_id INTEGER NOT NULL,
                    description TEXT,
                    calculation_type TEXT NOT NULL DEFAULT '{CALC_TYPE_INCREMENTAL}',
                    unit_of_measure TEXT,
                    visible BOOLEAN NOT NULL DEFAULT 1,
                    formula_json TEXT,
                    formula_string TEXT,
                    is_calculated BOOLEAN NOT NULL DEFAULT 0,
                    default_distribution_profile TEXT,
                    owner TEXT,
                    direction TEXT DEFAULT 'Higher is Better',
                    threshold_json TEXT,
                    target_granularity TEXT DEFAULT 'Monthly',
                    target_count INTEGER DEFAULT 1,
                    time_filter_type TEXT DEFAULT 'None',
                    time_filter_value TEXT,
                    target_labels TEXT,
                    FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE,
                    UNIQUE (indicator_id)
                )"""
            )

            # Check and add columns to 'kpis' if missing
            cursor.execute("PRAGMA table_info(kpis)")
            kpi_columns_info = {col[1] for col in cursor.fetchall()}
            if "formula_json" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN formula_json TEXT")
            if "formula_string" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN formula_string TEXT")
            if "is_calculated" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN is_calculated BOOLEAN NOT NULL DEFAULT 0")
            if "default_distribution_profile" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN default_distribution_profile TEXT")
            if "owner" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN owner TEXT")
            if "direction" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN direction TEXT DEFAULT 'Higher is Better'")
            if "threshold_json" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN threshold_json TEXT")
            if "target_granularity" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN target_granularity TEXT DEFAULT 'Monthly'")
            if "target_count" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN target_count INTEGER DEFAULT 1")
            if "time_filter_type" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN time_filter_type TEXT DEFAULT 'None'")
            if "time_filter_value" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN time_filter_value TEXT")
            if "target_labels" not in kpi_columns_info:
                cursor.execute("ALTER TABLE kpis ADD COLUMN target_labels TEXT")

            # Check and add 'indicator_template_id' to 'kpi_subgroups' if missing
            cursor.execute("PRAGMA table_info(kpi_subgroups)")
            subgroup_columns = {col[1] for col in cursor.fetchall()}
            if "indicator_template_id" not in subgroup_columns:
                try:
                    cursor.execute(
                        "ALTER TABLE kpi_subgroups ADD COLUMN indicator_template_id INTEGER REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL"
                    )
                    print("Added column 'indicator_template_id' to 'kpi_subgroups'.")
                except sqlite3.OperationalError as e:
                    print(
                        f"WARN: Could not add 'indicator_template_id' to 'kpi_subgroups', it might already exist or another issue occurred: {e}"
                    )

            # Check and add 'unit_of_measure' to 'kpis' if missing
            cursor.execute("PRAGMA table_info(kpis)")
            kpi_columns_set = {col[1] for col in cursor.fetchall()}
            if "unit_of_measure" not in kpi_columns_set:
                try:
                    cursor.execute("ALTER TABLE kpis ADD COLUMN unit_of_measure TEXT")
                    print("Added column 'unit_of_measure' to 'kpis'.")
                except (
                    sqlite3.OperationalError
                ) as e:
                    print(
                        f"WARN: Could not add 'unit_of_measure' to 'kpis', it might already exist or another issue occurred: {e}"
                    )

            conn.commit()

            # --- Units of Measure registry (KPI Explorer: replaces free-text UoM entry) ---
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS units_of_measure (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )"""
            )
            cursor.execute("SELECT COUNT(*) FROM units_of_measure")
            if cursor.fetchone()[0] == 0:
                cursor.execute("SELECT DISTINCT unit_of_measure FROM kpis WHERE unit_of_measure IS NOT NULL AND TRIM(unit_of_measure) != ''")
                existing_units = [r[0] for r in cursor.fetchall()]
                for u in existing_units or ["Units"]:
                    cursor.execute("INSERT OR IGNORE INTO units_of_measure (name) VALUES (?)", (u,))
            conn.commit()

            # --- New table for KPI-Plant Visibility ---
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_plant_visibility (
                    kpi_id INTEGER NOT NULL,
                    plant_id INTEGER NOT NULL,
                    is_enabled BOOLEAN NOT NULL DEFAULT 1,
                    PRIMARY KEY (kpi_id, plant_id),
                    FOREIGN KEY (kpi_id) REFERENCES kpis(id) ON DELETE CASCADE,
                    FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
                )"""
            )
            conn.commit()

        print(f"Table setup in {db_kpis_path} completed.")
    except sqlite3.Error as e:
        print(f"ERROR during setup of {db_kpis_path}: {e}")
        print(traceback.format_exc())

    # --- DB_PLANTS Setup ---
    db_plants_path = app_config.get_database_path("db_plants.db")
    print(f"Setting up tables in {db_plants_path}...")
    try:
        with sqlite3.connect(db_plants_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS plants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    visible BOOLEAN NOT NULL DEFAULT 1,
                    color TEXT NOT NULL DEFAULT '#000000',
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )"""
            )
            # Check and add 'description', 'color', 'is_active' to 'plants' if missing
            cursor.execute("PRAGMA table_info(plants)")
            plants_cols = {col[1] for col in cursor.fetchall()}
            if "description" not in plants_cols:
                try:
                    cursor.execute(
                        "ALTER TABLE plants ADD COLUMN description TEXT"
                    )
                    print("Added column 'description' to 'plants'.")
                except sqlite3.OperationalError as e:
                    print(
                        f"WARN: Could not add 'description' to 'plants', it might already exist or another issue occurred: {e}"
                    )
            if "color" not in plants_cols:
                try:
                    cursor.execute(
                        "ALTER TABLE plants ADD COLUMN color TEXT NOT NULL DEFAULT '#000000'"
                    )
                    print("Added column 'color' to 'plants'.")
                except sqlite3.OperationalError as e:
                    print(
                        f"WARN: Could not add 'color' to 'plants', it might already exist or another issue occurred: {e}"
                    )
            if "is_active" not in plants_cols:
                try:
                    cursor.execute(
                        "ALTER TABLE plants ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
                    )
                    print("Added column 'is_active' to 'plants'.")
                except sqlite3.OperationalError as e:
                    print(
                        f"WARN: Could not add 'is_active' to 'plants', it might already exist or another issue occurred: {e}"
                    )
            conn.commit()
        print(f"Table setup in {db_plants_path} completed.")
    except sqlite3.Error as e:
        print(f"ERROR during setup of {db_plants_path}: {e}")
        print(traceback.format_exc())

    # --- DB_TARGETS Setup (Annual Targets & Period Targets) ---
    db_targets_path = app_config.get_database_path("db_kpi_targets.db")
    print(f"Setting up tables in {db_targets_path}...")
    try:
        with sqlite3.connect(db_targets_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"""CREATE TABLE IF NOT EXISTS annual_targets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        year INTEGER NOT NULL,
                        plant_id INTEGER NOT NULL,
                        kpi_id INTEGER NOT NULL,
                        repartition_logic TEXT NOT NULL DEFAULT '{REPARTITION_LOGIC_YEAR}',
                        repartition_values TEXT NOT NULL DEFAULT '{{}}',
                        distribution_profile TEXT NOT NULL DEFAULT '{PROFILE_ANNUAL_PROGRESSIVE}',
                        profile_params TEXT DEFAULT '{{}}',
                        global_split_id INTEGER,
                        UNIQUE(year, plant_id, kpi_id)
                    )"""
                )
            except sqlite3.OperationalError as e_create:
                if "table annual_targets already exists" not in str(e_create).lower():
                    raise

            # --- Table for Normalized Annual Target Values ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_annual_target_values (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annual_target_id INTEGER NOT NULL,
                    target_number INTEGER NOT NULL,
                    target_value REAL,
                    is_manual BOOLEAN NOT NULL DEFAULT 1,
                    is_formula_based BOOLEAN NOT NULL DEFAULT 0,
                    formula TEXT,
                    formula_inputs TEXT DEFAULT '[]',
                    FOREIGN KEY (annual_target_id) REFERENCES annual_targets(id) ON DELETE CASCADE,
                    UNIQUE(annual_target_id, target_number)
                )
            """)

            # --- Modern kpi_targets table for explicit start/end boundaries ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kpi_id INTEGER NOT NULL,
                    plant_id INTEGER NOT NULL,
                    target_number INTEGER NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    target_value REAL NOT NULL,
                    UNIQUE(kpi_id, plant_id, target_number, period_start)
                )
            """)

            # Check and rename 'stabilimento_id' to 'plant_id' if it exists
            cursor.execute("PRAGMA table_info(annual_targets)")
            annual_targets_cols_info = cursor.fetchall()
            annual_targets_cols = {col[1] for col in annual_targets_cols_info}
            
            if "stabilimento_id" in annual_targets_cols and "plant_id" not in annual_targets_cols:
                try:
                    cursor.execute("ALTER TABLE annual_targets RENAME COLUMN stabilimento_id TO plant_id")
                    print("Renamed column 'stabilimento_id' to 'plant_id' in 'annual_targets'.")
                except sqlite3.OperationalError as e:
                    print(f"WARN: Could not rename 'stabilimento_id' to 'plant_id' in 'annual_targets': {e}")
            
            # Check for legacy columns and migrate if new table is empty
            if "annual_target1" in annual_targets_cols:
                cursor.execute("SELECT COUNT(*) FROM kpi_annual_target_values")
                if cursor.fetchone()[0] == 0:
                    print("Found legacy target columns. Migrating to kpi_annual_target_values...")
                    cursor.execute("""
                        INSERT INTO kpi_annual_target_values 
                        (annual_target_id, target_number, target_value, is_manual, is_formula_based, formula, formula_inputs)
                        SELECT id, 1, annual_target1, is_target1_manual, target1_is_formula_based, target1_formula, target1_formula_inputs FROM annual_targets
                    """)
                    cursor.execute("""
                        INSERT INTO kpi_annual_target_values 
                        (annual_target_id, target_number, target_value, is_manual, is_formula_based, formula, formula_inputs)
                        SELECT id, 2, annual_target2, is_target2_manual, target2_is_formula_based, target2_formula, target2_formula_inputs FROM annual_targets
                    """)
                    print("Migration of legacy columns completed.")

            conn.commit()
        print(f"Table setup in {db_targets_path} completed.")
    except sqlite3.Error as e:
        print(f"ERROR during setup of {db_targets_path}: {e}")
        print(traceback.format_exc())

    # --- DB_ACTUALS Setup (Actual Measurements) ---
    db_actuals_path = app_config.get_database_path("db_kpi_actuals.db")
    print(f"Setting up tables in {db_actuals_path}...")
    try:
        with sqlite3.connect(db_actuals_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actual_measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kpi_id INTEGER NOT NULL,
                    plant_id INTEGER NOT NULL,
                    measurement_date TEXT NOT NULL,
                    actual_value REAL NOT NULL,
                    UNIQUE(kpi_id, plant_id, measurement_date)
                )
            """)
            conn.commit()
        print(f"Table setup in {db_actuals_path} completed.")
    except sqlite3.Error as e:
        print(f"ERROR during setup of {db_actuals_path}: {e}")
        print(traceback.format_exc())

    # --- DB_HISTORY Setup (Audit & History Logs) ---
    db_history_path = app_config.get_database_path("db_kpi_history.db")
    print(f"Setting up tables in {db_history_path}...")
    try:
        with sqlite3.connect(db_history_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kpi_definition_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kpi_id INTEGER NOT NULL,
                    changed_at TEXT NOT NULL,
                    changed_by TEXT,
                    change_type TEXT NOT NULL,
                    old_value_json TEXT,
                    new_value_json TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS target_value_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kpi_id INTEGER NOT NULL,
                    plant_id INTEGER NOT NULL,
                    target_number INTEGER NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    old_value REAL,
                    new_value REAL,
                    changed_at TEXT NOT NULL,
                    changed_by TEXT
                )
            """)
            conn.commit()
        print(f"Table setup in {db_history_path} completed.")
    except sqlite3.Error as e:
        print(f"ERROR during setup of {db_history_path}: {e}")
        print(traceback.format_exc())

    # --- Setup Periodic Tables (Days, Weeks, Months, Quarters) ---
    db_kpi_days_path = app_config.get_database_path("db_kpi_days.db")
    db_kpi_weeks_path = app_config.get_database_path("db_kpi_weeks.db")
    db_kpi_months_path = app_config.get_database_path("db_kpi_months.db")
    db_kpi_quarters_path = app_config.get_database_path("db_kpi_quarters.db")

    db_configs_periods = [
        (db_kpi_days_path, "daily_targets", "date_value TEXT NOT NULL"),
        (
            db_kpi_weeks_path,
            "weekly_targets",
            "week_value TEXT NOT NULL",
        ),  # Example: "2023-W52"
        (
            db_kpi_months_path,
            "monthly_targets",
            "month_value TEXT NOT NULL",
        ),  # Example: "January"
        (
            db_kpi_quarters_path,
            "quarterly_targets",
            "quarter_value TEXT NOT NULL",
        ),  # Example: "Q1"
    ]

    for db_path, table_name, period_col_def in db_configs_periods:
        print(f"Setting up table '{table_name}' in {db_path}...")
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                period_col_name_for_unique = period_col_def.split()[0]  # e.g., "date_value"
                # Check and rename 'stabilimento_id' to 'plant_id' if it exists
                cursor.execute(f"PRAGMA table_info({table_name})")
                periodic_cols = {col[1] for col in cursor.fetchall()}
                if "stabilimento_id" in periodic_cols and "plant_id" not in periodic_cols:
                    try:
                        cursor.execute(f"ALTER TABLE {table_name} RENAME COLUMN stabilimento_id TO plant_id")
                        print(f"Renamed column 'stabilimento_id' to 'plant_id' in '{table_name}'.")
                    except sqlite3.OperationalError as e:
                        print(f"WARN: Could not rename 'stabilimento_id' to 'plant_id' in '{table_name}': {e}")
                conn.commit() # Commit rename before creating/checking table

                # Ensure the UNIQUE constraint includes target_number as one KPI can have Target 1 and Target 2 for the same period
                cursor.execute(
                    f"""CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        year INTEGER NOT NULL,
                        plant_id INTEGER NOT NULL,
                        kpi_id INTEGER NOT NULL,
                        target_number INTEGER NOT NULL CHECK(target_number > 0),
                        {period_col_name_for_unique.replace(' UNIQUE', '')},
                        target_value REAL NOT NULL,
                        UNIQUE(year, plant_id, kpi_id, target_number, {period_col_name_for_unique})
                    )"""
                )
                conn.commit()
            print(f"Table setup in '{table_name}' in {db_path} completed.")
        except sqlite3.Error as e:
            print(f"ERROR during setup of {table_name} in {db_path}: {e}")
            print(traceback.format_exc())

    # --- DB_USERS Setup (Named profiles & MCP API keys) ---
    db_users_path = app_config.get_database_path("db_users.db")
    print(f"Setting up tables in {db_users_path}...")
    try:
        with sqlite3.connect(db_users_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    email TEXT,
                    color TEXT NOT NULL DEFAULT '#3b82f6',
                    password_hash TEXT,
                    password_salt TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )"""
            )
            # Migration: add password columns to a users table created before login existed
            cursor.execute("PRAGMA table_info(users)")
            user_cols = {col[1] for col in cursor.fetchall()}
            if "password_hash" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
            if "password_salt" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN password_salt TEXT")

            cursor.execute(
                """CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )"""
            )

            # Login sessions -- separate from api_keys (long-lived, MCP-only). Sessions are
            # short-lived and issued by /auth/login, used to authenticate the React app + REST API.
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )"""
            )
            conn.commit()
        print(f"Table setup in {db_users_path} completed.")
    except sqlite3.Error as e:
        print(f"ERROR during setup of {db_users_path}: {e}")
        print(traceback.format_exc())

    print("Database check and setup completed.")


if __name__ == "__main__":
    print("Running db_core/setup.py as main script (for setup/test).")
    # This will attempt to import from app_config.py located relative to this script
    # or in the PYTHONPATH. For robust testing, ensure app_config.py is accessible.
    try:
        setup_databases()
        print(
            "\n--- Database setup completed successfully (run from db_core/setup.py) ---"
        )
    except Exception as e:
        print(
            f"\n--- CRITICAL ERROR during execution of setup_databases from db_core/setup.py: {e} ---"
        )
        print(traceback.format_exc())
