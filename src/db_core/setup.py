# src/db_core/setup.py
import sqlite3
import traceback  # For more detailed error reporting if needed
from pathlib import Path  # To ensure CSV_EXPORT_BASE_PATH is handled as a Path object

# Import configurations from app_config.py
import app_config 

from gui.shared.constants import (
        CALC_TYPE_INCREMENTALE,
        CALC_TYPE_MEDIA,
        REPARTITION_LOGIC_ANNO,
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
    print("Inizio setup_databases...")

    csv_export_path = app_config.get_csv_export_path()
    if csv_export_path:
        try:
            csv_export_path.mkdir(parents=True, exist_ok=True)
            print(f"INFO: Assicurata directory per export CSV: {csv_export_path}")
        except Exception as e:
            print(
                f"WARN: Impossibile creare/verificare la directory CSV_EXPORT_BASE_PATH {csv_export_path}: {e}"
            )
            print(traceback.format_exc())

    # --- DB_KPI_TEMPLATES Setup ---
    db_kpi_templates_path = app_config.get_database_path("db_kpi_templates.db")
    print(f"Setup tabelle in {db_kpi_templates_path}...")
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
                    default_calculation_type TEXT NOT NULL CHECK(default_calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}')),
                    default_unit_of_measure TEXT,
                    default_visible BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (template_id) REFERENCES kpi_indicator_templates(id) ON DELETE CASCADE,
                    UNIQUE (template_id, indicator_name_in_template)
                )"""
            )
            conn.commit()
        print(f"Setup tabelle in {db_kpi_templates_path} completato.")
    except sqlite3.Error as e:
        print(f"ERRORE durante il setup di {db_kpi_templates_path}: {e}")
        print(traceback.format_exc())

    # --- DB_KPIS Setup ---
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    print(f"Setup tabelle in {db_kpis_path}...")
    try:
        with sqlite3.connect(db_kpis_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "PRAGMA foreign_keys = ON;"
            )  # Ensure FK constraints are active during setup for consistency

            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_subgroups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    group_id INTEGER NOT NULL,
                    indicator_template_id INTEGER,
                    FOREIGN KEY (group_id) REFERENCES kpi_groups(id) ON DELETE CASCADE,
                    FOREIGN KEY (indicator_template_id) REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL,
                    UNIQUE (name, group_id)
                )"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    subgroup_id INTEGER NOT NULL,
                    FOREIGN KEY (subgroup_id) REFERENCES kpi_subgroups(id) ON DELETE CASCADE,
                    UNIQUE (name, subgroup_id)
                )"""
            )
            cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS kpis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    indicator_id INTEGER NOT NULL,
                    description TEXT,
                    calculation_type TEXT NOT NULL CHECK(calculation_type IN ('{CALC_TYPE_INCREMENTALE}', '{CALC_TYPE_MEDIA}')),
                    unit_of_measure TEXT,
                    visible BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE,
                    UNIQUE (indicator_id)
                )"""
            )

            # Check and add 'indicator_template_id' to 'kpi_subgroups' if missing
            cursor.execute("PRAGMA table_info(kpi_subgroups)")
            subgroup_columns = {col[1] for col in cursor.fetchall()}
            if "indicator_template_id" not in subgroup_columns:
                try:
                    # Note: SQLite does not support adding FK constraints via ALTER TABLE directly in older versions.
                    # The FK is defined in CREATE TABLE. If altering, one would typically recreate the table.
                    # However, adding a column that REFERENCES another table (without explicit constraint enforcement by ALTER) is fine.
                    # The schema from CREATE TABLE already defines the FK.
                    cursor.execute(
                        "ALTER TABLE kpi_subgroups ADD COLUMN indicator_template_id INTEGER REFERENCES kpi_indicator_templates(id) ON DELETE SET NULL"
                    )
                    print("Aggiunta colonna 'indicator_template_id' a 'kpi_subgroups'.")
                except sqlite3.OperationalError as e:
                    print(
                        f"WARN: Impossibile aggiungere 'indicator_template_id' a 'kpi_subgroups', potrebbe già esistere o altro problema: {e}"
                    )

            # Check and add 'unit_of_measure' to 'kpis' if missing
            cursor.execute("PRAGMA table_info(kpis)")
            kpi_columns_set = {col[1] for col in cursor.fetchall()}
            if "unit_of_measure" not in kpi_columns_set:
                try:
                    cursor.execute("ALTER TABLE kpis ADD COLUMN unit_of_measure TEXT")
                    print("Aggiunta colonna 'unit_of_measure' a 'kpis'.")
                except (
                    sqlite3.OperationalError
                ) as e:  # Usually means it already exists or other schema issue
                    print(
                        f"WARN: Impossibile aggiungere 'unit_of_measure' a 'kpis', potrebbe già esistere o altro problema: {e}"
                    )

            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_master_sub_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    master_kpi_spec_id INTEGER NOT NULL,
                    sub_kpi_spec_id INTEGER NOT NULL,
                    distribution_weight REAL NOT NULL DEFAULT 1.0,
                    FOREIGN KEY (master_kpi_spec_id) REFERENCES kpis(id) ON DELETE CASCADE,
                    FOREIGN KEY (sub_kpi_spec_id) REFERENCES kpis(id) ON DELETE CASCADE,
                    UNIQUE (master_kpi_spec_id, sub_kpi_spec_id)
                )"""
            )
            # Check and add 'distribution_weight' to 'kpi_master_sub_links' if missing
            cursor.execute("PRAGMA table_info(kpi_master_sub_links)")
            link_columns = {col[1] for col in cursor.fetchall()}
            if "distribution_weight" not in link_columns:
                try:
                    cursor.execute(
                        "ALTER TABLE kpi_master_sub_links ADD COLUMN distribution_weight REAL NOT NULL DEFAULT 1.0"
                    )
                    print(
                        "Aggiunta colonna 'distribution_weight' a 'kpi_master_sub_links'."
                    )
                except sqlite3.OperationalError as e:
                    print(
                        f"WARN: Impossibile aggiungere 'distribution_weight' a 'kpi_master_sub_links', potrebbe già esistere o altro problema: {e}"
                    )
            conn.commit()

            # --- New table for KPI-Stabilimento Visibility ---
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kpi_stabilimento_visibility (
                    kpi_id INTEGER NOT NULL,
                    stabilimento_id INTEGER NOT NULL,
                    is_enabled BOOLEAN NOT NULL DEFAULT 1,
                    PRIMARY KEY (kpi_id, stabilimento_id),
                    FOREIGN KEY (kpi_id) REFERENCES kpis(id) ON DELETE CASCADE,
                    FOREIGN KEY (stabilimento_id) REFERENCES stabilimenti(id) ON DELETE CASCADE
                )"""
            )
            conn.commit()

        print(f"Setup tabelle in {db_kpis_path} completato.")
    except sqlite3.Error as e:
        print(f"ERRORE durante il setup di {db_kpis_path}: {e}")
        print(traceback.format_exc())

    # --- DB_STABILIMENTI Setup ---
    db_stabilimenti_path = app_config.get_database_path("db_stabilimenti.db")
    print(f"Setup tabelle in {db_stabilimenti_path}...")
    try:
        with sqlite3.connect(db_stabilimenti_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS stabilimenti (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    visible BOOLEAN NOT NULL DEFAULT 1,
                    color TEXT NOT NULL DEFAULT '#000000'
                )"""
            )
            # Check and add 'description' to 'stabilimenti' if missing
            cursor.execute("PRAGMA table_info(stabilimenti)")
            stabilimenti_cols = {col[1] for col in cursor.fetchall()}
            if "description" not in stabilimenti_cols:
                try:
                    cursor.execute(
                        "ALTER TABLE stabilimenti ADD COLUMN description TEXT"
                    )
                    print("Aggiunta colonna 'description' a 'stabilimenti'.")
                except sqlite3.OperationalError as e:
                    print(
                        f"WARN: Impossibile aggiungere 'description' a 'stabilimenti', potrebbe già esistere o altro problema: {e}"
                    )
            # Check and add 'color' column if missing
            if "color" not in stabilimenti_cols:
                try:
                    cursor.execute(
                        "ALTER TABLE stabilimenti ADD COLUMN color TEXT NOT NULL DEFAULT '#000000'"
                    )
                    print("Aggiunta colonna 'color' a 'stabilimenti'.")
                except sqlite3.OperationalError as e:
                    print(
                        f"WARN: Impossibile aggiungere 'color' a 'stabilimenti', potrebbe già esistere o altro problema: {e}"
                    )
            conn.commit()
        print(f"Setup tabelle in {db_stabilimenti_path} completato.")
    except sqlite3.Error as e:
        print(f"ERRORE durante il setup di {db_stabilimenti_path}: {e}")
        print(traceback.format_exc())

    # --- DB_TARGETS Setup (Annual Targets) ---
    db_targets_path = app_config.get_database_path("db_kpi_targets.db")
    print(f"Setup tabelle in {db_targets_path}...")
    try:
        with sqlite3.connect(db_targets_path) as conn:
            cursor = conn.cursor()
            try:
                from gui.shared.constants import (
                    PROFILE_ANNUAL_PROGRESSIVE,
                    REPARTITION_LOGIC_ANNO,
                )

                cursor.execute(
                    f"""CREATE TABLE IF NOT EXISTS annual_targets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        year INTEGER NOT NULL,
                        stabilimento_id INTEGER NOT NULL,
                        kpi_id INTEGER NOT NULL,
                        annual_target1 REAL NOT NULL DEFAULT 0,
                        annual_target2 REAL NOT NULL DEFAULT 0,
                        repartition_logic TEXT NOT NULL DEFAULT '{REPARTITION_LOGIC_ANNO}',
                        repartition_values TEXT NOT NULL DEFAULT '{{}}',
                        distribution_profile TEXT NOT NULL DEFAULT '{PROFILE_ANNUAL_PROGRESSIVE}',
                        profile_params TEXT DEFAULT '{{}}',
                        is_target1_manual BOOLEAN NOT NULL DEFAULT 0,
                        is_target2_manual BOOLEAN NOT NULL DEFAULT 0,
                        target1_is_formula_based BOOLEAN NOT NULL DEFAULT 0,
                        target1_formula TEXT,
                        target1_formula_inputs TEXT DEFAULT '[]',
                        target2_is_formula_based BOOLEAN NOT NULL DEFAULT 0,
                        target2_formula TEXT,
                        target2_formula_inputs TEXT DEFAULT '[]',
                        UNIQUE(year, stabilimento_id, kpi_id)
                    )"""
                )
            except sqlite3.OperationalError as e_create:
                if "table annual_targets already exists" not in str(e_create).lower():
                    raise  # Re-raise if it's not the 'already exists' error

            # Check and add columns to 'annual_targets'
            cursor.execute("PRAGMA table_info(annual_targets)")
            target_columns_info = {col[1].lower(): col for col in cursor.fetchall()}

            columns_to_add_with_defaults = {
                "profile_params": "TEXT DEFAULT '{}'",  # Added default
                "is_target1_manual": "BOOLEAN NOT NULL DEFAULT 0",
                "is_target2_manual": "BOOLEAN NOT NULL DEFAULT 0",
                "target1_is_formula_based": "BOOLEAN NOT NULL DEFAULT 0",
                "target1_formula": "TEXT",
                "target1_formula_inputs": "TEXT DEFAULT '[]'",  # Added default
                "target2_is_formula_based": "BOOLEAN NOT NULL DEFAULT 0",
                "target2_formula": "TEXT",
                "target2_formula_inputs": "TEXT DEFAULT '[]'",  # Added default
            }
            # Also ensure older columns have their defaults if added via ALTER
            # (though defaults in CREATE IF NOT EXISTS are better)
            older_columns_with_potential_missing_defaults = {
                "repartition_logic": f"TEXT NOT NULL DEFAULT '{REPARTITION_LOGIC_ANNO}'",  # from app_config
                "repartition_values": "TEXT NOT NULL DEFAULT '{}'",
                "distribution_profile": f"TEXT NOT NULL DEFAULT '{PROFILE_ANNUAL_PROGRESSIVE}'",  # from app_config
            }
            all_columns_to_check = {
                **columns_to_add_with_defaults,
                **older_columns_with_potential_missing_defaults,
            }

            for col_name, col_def_with_default in all_columns_to_check.items():
                if col_name not in target_columns_info:
                    try:
                        cursor.execute(
                            f"ALTER TABLE annual_targets ADD COLUMN {col_name} {col_def_with_default}"
                        )
                        print(
                            f"Aggiunta colonna '{col_name}' con definizione '{col_def_with_default}' a 'annual_targets'."
                        )
                    except sqlite3.OperationalError as e_alter:
                        print(
                            f"WARN: Impossibile aggiungere colonna '{col_name}' a 'annual_targets': {e_alter}. Potrebbe già esistere o esserci un problema di default."
                        )
            conn.commit()
        print(f"Setup tabelle in {db_targets_path} completato.")
    except sqlite3.Error as e:
        print(f"ERRORE durante il setup di {db_targets_path}: {e}")
        print(traceback.format_exc())
    except (
        NameError
    ) as ne:  # Catches if PROFILE_ANNUAL_PROGRESSIVE or REPARTITION_LOGIC_ANNO are not imported
        print(
            f"ERRORE di configurazione (NameError) per DB_TARGETS: {ne}. Assicurarsi che le costanti siano in app_config.py."
        )
        print(traceback.format_exc())

    # --- Setup Tabelle Periodiche (Days, Weeks, Months, Quarters) ---
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
        print(f"Setup tabella '{table_name}' in {db_path}...")
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                period_col_name_for_unique = period_col_def.split()[
                    0
                ]  # e.g., "date_value"
                # Ensure the UNIQUE constraint includes target_number as one KPI can have Target 1 and Target 2 for the same period
                cursor.execute(
                    f"""CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        year INTEGER NOT NULL,
                        stabilimento_id INTEGER NOT NULL,
                        kpi_id INTEGER NOT NULL,
                        target_number INTEGER NOT NULL CHECK(target_number IN (1, 2)),
                        {period_col_def.replace(' UNIQUE', '')},
                        target_value REAL NOT NULL,
                        UNIQUE(year, stabilimento_id, kpi_id, target_number, {period_col_name_for_unique})
                    )"""
                )
                conn.commit()
            print(f"Setup tabella '{table_name}' in {db_path} completato.")
        except sqlite3.Error as e:
            print(f"ERRORE durante il setup di {table_name} in {db_path}: {e}")
            print(traceback.format_exc())

    print("Controllo e setup database completato.")


if __name__ == "__main__":
    print("Esecuzione di db_core/setup.py come script principale (per setup/test).")
    # This will attempt to import from app_config.py located relative to this script
    # or in the PYTHONPATH. For robust testing, ensure app_config.py is accessible.
    try:
        setup_databases()
        print(
            "\n--- Setup database completato con successo (eseguito da db_core/setup.py) ---"
        )
    except Exception as e:
        print(
            f"\n--- ERRORE CRITICO durante l'esecuzione di setup_databases da db_core/setup.py: {e} ---"
        )
        print(traceback.format_exc())