# src/db_core/setup.py
import sqlite3
import traceback  # For more detailed error reporting if needed
from pathlib import Path  # To ensure CSV_EXPORT_BASE_PATH is handled as a Path object

# Import configurations from app_config.py
# Assuming app_config.py is in the parent directory or accessible via PYTHONPATH
# If src is not directly in PYTHONPATH, you might need relative imports
# or to adjust your project structure/PYTHONPATH for imports to work.
# For simplicity, assuming direct import works:
from app_config import (
    DB_KPIS,
    DB_STABILIMENTI,
    DB_TARGETS,
    DB_KPI_DAYS,
    DB_KPI_WEEKS,
    DB_KPI_MONTHS,
    DB_KPI_QUARTERS,
    DB_KPI_TEMPLATES,
    CSV_EXPORT_BASE_PATH,  # Make sure this is a Path object in app_config or convert it here
    CALC_TYPE_INCREMENTALE,
    CALC_TYPE_MEDIA,
    # Add other constants if they are directly used in table definitions (e.g., specific check constraints beyond calc_type)
    # For now, only CALC_TYPE_* are directly in CREATE TABLE CHECK constraints.
)

# It's good practice to ensure CSV_EXPORT_BASE_PATH is a Path object if it isn't already.
# If it's defined as a string in app_config.py, convert it.
# If it's already a Path object in app_config.py, this line is redundant but harmless.
_CSV_EXPORT_BASE_PATH = Path(CSV_EXPORT_BASE_PATH) if CSV_EXPORT_BASE_PATH else None


def setup_databases():
    """
    Sets up all necessary SQLite databases and their tables.
    Creates tables if they don't exist and attempts to alter existing tables
    to add new columns if they are missing.
    """
    print("Inizio setup_databases...")

    if _CSV_EXPORT_BASE_PATH:
        try:
            _CSV_EXPORT_BASE_PATH.mkdir(parents=True, exist_ok=True)
            print(f"INFO: Assicurata directory per export CSV: {_CSV_EXPORT_BASE_PATH}")
        except Exception as e:
            print(
                f"WARN: Impossibile creare/verificare la directory CSV_EXPORT_BASE_PATH {_CSV_EXPORT_BASE_PATH}: {e}"
            )
            print(traceback.format_exc())

    # --- DB_KPI_TEMPLATES Setup ---
    print(f"Setup tabelle in {DB_KPI_TEMPLATES}...")
    try:
        with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
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
        print(f"Setup tabelle in {DB_KPI_TEMPLATES} completato.")
    except sqlite3.Error as e:
        print(f"ERRORE durante il setup di {DB_KPI_TEMPLATES}: {e}")
        print(traceback.format_exc())

    # --- DB_KPIS Setup ---
    print(f"Setup tabelle in {DB_KPIS}...")
    try:
        with sqlite3.connect(DB_KPIS) as conn:
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
        print(f"Setup tabelle in {DB_KPIS} completato.")
    except sqlite3.Error as e:
        print(f"ERRORE durante il setup di {DB_KPIS}: {e}")
        print(traceback.format_exc())

    # --- DB_STABILIMENTI Setup ---
    print(f"Setup tabelle in {DB_STABILIMENTI}...")
    try:
        with sqlite3.connect(DB_STABILIMENTI) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS stabilimenti (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    visible BOOLEAN NOT NULL DEFAULT 1
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
            conn.commit()
        print(f"Setup tabelle in {DB_STABILIMENTI} completato.")
    except sqlite3.Error as e:
        print(f"ERRORE durante il setup di {DB_STABILIMENTI}: {e}")
        print(traceback.format_exc())

    # --- DB_TARGETS Setup (Annual Targets) ---
    print(f"Setup tabelle in {DB_TARGETS}...")
    try:
        with sqlite3.connect(DB_TARGETS) as conn:
            cursor = conn.cursor()
            try:
                # PROFILE_ANNUAL_PROGRESSIVE should be defined in app_config
                from app_config import (
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
        print(f"Setup tabelle in {DB_TARGETS} completato.")
    except sqlite3.Error as e:
        print(f"ERRORE durante il setup di {DB_TARGETS}: {e}")
        print(traceback.format_exc())
    except (
        NameError
    ) as ne:  # Catches if PROFILE_ANNUAL_PROGRESSIVE or REPARTITION_LOGIC_ANNO are not imported
        print(
            f"ERRORE di configurazione (NameError) per DB_TARGETS: {ne}. Assicurarsi che le costanti siano in app_config.py."
        )
        print(traceback.format_exc())

    # --- Setup Tabelle Periodiche (Days, Weeks, Months, Quarters) ---
    db_configs_periods = [
        (DB_KPI_DAYS, "daily_targets", "date_value TEXT NOT NULL"),
        (
            DB_KPI_WEEKS,
            "weekly_targets",
            "week_value TEXT NOT NULL",
        ),  # Example: "2023-W52"
        (
            DB_KPI_MONTHS,
            "monthly_targets",
            "month_value TEXT NOT NULL",
        ),  # Example: "January"
        (
            DB_KPI_QUARTERS,
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
