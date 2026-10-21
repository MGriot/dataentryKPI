"""
Creates and migrates every SQLite database the app uses. Safe to run on every start
(the REST API and the MCP server both do), and safe on databases created by any earlier
version: all steps are idempotent.

Migrations that can't be done with ALTER TABLE (dropping a CHECK constraint, removing a
foreign key that points at a table living in another database file, typing a column)
rebuild the table with SQLite's recommended procedure -- create the new table, copy the
rows, drop the old one, rename the new one -- with foreign-key enforcement off. (An earlier
version renamed the *old* table first, which made SQLite rewrite other tables' foreign
keys to point at the temporary name; that is what left `kpis` referencing a dropped
`kpi_indicators_old` table in some databases. The rebuild below repairs that too.)
"""
import calendar
import json
import logging
import sqlite3

from src.config import settings as app_config
from src.config.constants import (
    CALC_TYPE_SUM,
    DEFAULT_DISTRIBUTION_PROFILE,
    DEFAULT_REPARTITION_LOGIC,
    normalize_calc_type,
)
from src.data_access import db

log = logging.getLogger(__name__)


# --- Canonical table definitions (format with the table name) ---

TEMPLATE_TABLES = {
    "kpi_indicator_templates": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT
    )""",
    "template_defined_indicators": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        indicator_name_in_template TEXT NOT NULL,
        default_description TEXT,
        default_calculation_type TEXT NOT NULL DEFAULT 'Sum',
        default_unit_of_measure TEXT,
        default_visible BOOLEAN NOT NULL DEFAULT 1,
        FOREIGN KEY (template_id) REFERENCES kpi_indicator_templates(id) ON DELETE CASCADE,
        UNIQUE (template_id, indicator_name_in_template)
    )""",
    "global_kpi_splits": f"""CREATE TABLE IF NOT EXISTS {{name}} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        year INTEGER,
        repartition_logic TEXT NOT NULL DEFAULT '{DEFAULT_REPARTITION_LOGIC}',
        repartition_values TEXT NOT NULL DEFAULT '{{{{}}}}',
        distribution_profile TEXT NOT NULL DEFAULT '{DEFAULT_DISTRIBUTION_PROFILE}',
        profile_params TEXT NOT NULL DEFAULT '{{{{}}}}'
    )""",
    "global_split_years": """CREATE TABLE IF NOT EXISTS {name} (
        global_split_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        PRIMARY KEY (global_split_id, year),
        FOREIGN KEY (global_split_id) REFERENCES global_kpi_splits(id) ON DELETE CASCADE
    )""",
    "global_split_indicators": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        global_split_id INTEGER NOT NULL,
        indicator_id INTEGER NOT NULL,
        override_distribution_profile TEXT,
        FOREIGN KEY (global_split_id) REFERENCES global_kpi_splits(id) ON DELETE CASCADE,
        UNIQUE (global_split_id, indicator_id)
    )""",
    "app_meta": """CREATE TABLE IF NOT EXISTS {name} (
        key TEXT PRIMARY KEY,
        value TEXT
    )""",
}

KPI_TABLES = {
    "kpi_nodes": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        parent_id INTEGER,
        node_type TEXT CHECK(node_type IN ('group', 'subgroup', 'folder')),
        custom_level_label TEXT,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        indicator_template_id INTEGER,
        FOREIGN KEY (parent_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE,
        UNIQUE (name, parent_id)
    )""",
    "kpi_indicators": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        node_id INTEGER NOT NULL,
        subgroup_id INTEGER,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        FOREIGN KEY (node_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE,
        UNIQUE (name, node_id)
    )""",
    "kpis": f"""CREATE TABLE IF NOT EXISTS {{name}} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator_id INTEGER NOT NULL,
        description TEXT,
        calculation_type TEXT NOT NULL DEFAULT '{CALC_TYPE_SUM}',
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
    )""",
    "units_of_measure": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )""",
    # plant_id points at db_plants.db, so it can't be a declared foreign key (SQLite FKs
    # can't cross database files); referential cleanup is done in plants_management.crud.
    "kpi_plant_visibility": """CREATE TABLE IF NOT EXISTS {name} (
        kpi_id INTEGER NOT NULL,
        plant_id INTEGER NOT NULL,
        is_enabled BOOLEAN NOT NULL DEFAULT 1,
        PRIMARY KEY (kpi_id, plant_id),
        FOREIGN KEY (kpi_id) REFERENCES kpis(id) ON DELETE CASCADE
    )""",
}

PLANT_TABLES = {
    "plants": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        visible BOOLEAN NOT NULL DEFAULT 1,
        color TEXT NOT NULL DEFAULT '#3b82f6',
        is_active BOOLEAN NOT NULL DEFAULT 1
    )""",
}

TARGET_TABLES = {
    # global_split_id points at db_kpi_templates.db -> not a declared FK (see above).
    "annual_targets": f"""CREATE TABLE IF NOT EXISTS {{name}} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        plant_id INTEGER NOT NULL,
        kpi_id INTEGER NOT NULL,
        repartition_logic TEXT NOT NULL DEFAULT '{DEFAULT_REPARTITION_LOGIC}',
        repartition_values TEXT NOT NULL DEFAULT '{{{{}}}}',
        distribution_profile TEXT NOT NULL DEFAULT '{DEFAULT_DISTRIBUTION_PROFILE}',
        profile_params TEXT DEFAULT '{{{{}}}}',
        global_split_id INTEGER,
        UNIQUE (year, plant_id, kpi_id)
    )""",
    "kpi_annual_target_values": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        annual_target_id INTEGER NOT NULL,
        target_number INTEGER NOT NULL,
        target_value REAL,
        is_manual BOOLEAN NOT NULL DEFAULT 1,
        is_formula_based BOOLEAN NOT NULL DEFAULT 0,
        formula TEXT,
        formula_inputs TEXT DEFAULT '[]',
        FOREIGN KEY (annual_target_id) REFERENCES annual_targets(id) ON DELETE CASCADE,
        UNIQUE (annual_target_id, target_number)
    )""",
    "kpi_targets": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kpi_id INTEGER NOT NULL,
        plant_id INTEGER NOT NULL,
        target_number INTEGER NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        target_value REAL NOT NULL,
        UNIQUE (kpi_id, plant_id, target_number, period_start)
    )""",
}

ACTUAL_TABLES = {
    "actual_measurements": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kpi_id INTEGER NOT NULL,
        plant_id INTEGER NOT NULL,
        measurement_date TEXT NOT NULL,
        actual_value REAL NOT NULL,
        UNIQUE (kpi_id, plant_id, measurement_date)
    )""",
}

HISTORY_TABLES = {
    "kpi_definition_history": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kpi_id INTEGER NOT NULL,
        changed_at TEXT NOT NULL,
        changed_by TEXT,
        change_type TEXT NOT NULL,
        old_value_json TEXT,
        new_value_json TEXT
    )""",
    "target_value_history": """CREATE TABLE IF NOT EXISTS {name} (
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
    )""",
}

USER_TABLES = {
    "users": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        email TEXT,
        color TEXT NOT NULL DEFAULT '#3b82f6',
        password_hash TEXT,
        password_salt TEXT,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        is_admin BOOLEAN NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""",
    "api_keys": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        key_prefix TEXT NOT NULL,
        key_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        last_used_at TEXT,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""",
    "sessions": """CREATE TABLE IF NOT EXISTS {name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""",
}


def _period_table_ddl(period_col: str) -> str:
    return f"""CREATE TABLE IF NOT EXISTS {{name}} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        plant_id INTEGER NOT NULL,
        kpi_id INTEGER NOT NULL,
        target_number INTEGER NOT NULL CHECK(target_number > 0),
        {period_col} TEXT NOT NULL,
        target_value REAL NOT NULL,
        UNIQUE (year, plant_id, kpi_id, target_number, {period_col})
    )"""


# --- Generic helpers ---

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _table_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return (row["sql"] or "") if row else ""


def _has_dangling_foreign_key(conn: sqlite3.Connection, table: str) -> bool:
    for fk in conn.execute(f"PRAGMA foreign_key_list({db.ident(table)})"):
        if not _table_exists(conn, fk["table"]):
            return True
    return False


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: dict):
    existing = set(db.table_columns(conn, table))
    for col, decl in columns.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE {db.ident(table)} ADD COLUMN {db.ident(col)} {decl}")
            log.info("Added column %s.%s", table, col)


def _rebuild_table(conn: sqlite3.Connection, table: str, ddl: str):
    """Recreates `table` from its canonical DDL, keeping every row (columns both versions share)."""
    tmp = f"{table}__rebuild"
    conn.execute(f"DROP TABLE IF EXISTS {db.ident(tmp)}")
    conn.execute(ddl.format(name=tmp))
    old_cols = set(db.table_columns(conn, table))
    shared = [c for c in db.table_columns(conn, tmp) if c in old_cols]
    cols = ", ".join(db.ident(c) for c in shared)
    conn.execute(f"INSERT INTO {db.ident(tmp)} ({cols}) SELECT {cols} FROM {db.ident(table)}")
    conn.execute(f"DROP TABLE {db.ident(table)}")
    conn.execute(f"ALTER TABLE {db.ident(tmp)} RENAME TO {db.ident(table)}")
    log.info("Rebuilt table %s", table)


def _ensure_tables(conn: sqlite3.Connection, tables: dict, rebuild_if=None):
    for table, ddl in tables.items():
        if _table_exists(conn, table) and (
            _has_dangling_foreign_key(conn, table) or (rebuild_if and rebuild_if(table, _table_sql(conn, table)))
        ):
            _rebuild_table(conn, table, ddl)
        conn.execute(ddl.format(name=table))


# --- Per-database setup ---

def _setup_templates():
    with db.connect(db.TEMPLATES, foreign_keys=False) as conn:
        def needs_rebuild(table, sql):
            # Old versions restricted default_calculation_type to ('Incremental','Average').
            return table == "template_defined_indicators" and "CHECK" in sql.upper()

        _ensure_tables(conn, TEMPLATE_TABLES, needs_rebuild)
        for row in conn.execute("SELECT id, default_calculation_type FROM template_defined_indicators").fetchall():
            try:
                canonical = normalize_calc_type(row["default_calculation_type"])
            except ValueError:
                canonical = CALC_TYPE_SUM
            if canonical != row["default_calculation_type"]:
                conn.execute("UPDATE template_defined_indicators SET default_calculation_type=? WHERE id=?", (canonical, row["id"]))

        # Legacy single-year column -> multi-year mapping table.
        conn.execute(
            "INSERT OR IGNORE INTO global_split_years (global_split_id, year) "
            "SELECT id, year FROM global_kpi_splits WHERE year IS NOT NULL"
        )
        conn.execute("UPDATE global_kpi_splits SET profile_params='{}' WHERE profile_params IS NULL OR profile_params=''")
        conn.execute("UPDATE global_kpi_splits SET repartition_values='{}' WHERE repartition_values IS NULL OR repartition_values=''")
        _seed_split_presets_once(conn)


def _seed_split_presets_once(conn: sqlite3.Connection):
    """Seeds the built-in curves as ordinary, editable templates -- once. Deleting a preset sticks."""
    if conn.execute("SELECT 1 FROM app_meta WHERE key='split_presets_seeded'").fetchone():
        return
    from src.utils.repartition_utils import ramp_proportions, sinusoidal_proportions

    months = [calendar.month_name[i] for i in range(1, 13)]
    presets = [
        ("Preset: Uniform / Even", "even_distribution", [1.0 / 12] * 12),
        ("Preset: Annual Progressive", "annual_progressive", ramp_proportions(12, 0.8, 1.2)),
        ("Preset: Annual Progressive (Weekday Bias)", "annual_progressive_weekday_bias", ramp_proportions(12, 0.8, 1.2)),
        ("Preset: Sinusoidal Seasonal Curve", "true_annual_sinusoidal", sinusoidal_proportions(12, 0.1, 0.0)),
        ("Preset: Event Based (Shutdowns)", "event_based_spikes_or_dips", [1.0 / 12] * 12),
    ]
    for name, profile, props in presets:
        weights = {months[i]: round(props[i] * 100, 4) for i in range(12)}
        conn.execute(
            "INSERT OR IGNORE INTO global_kpi_splits (name, year, repartition_logic, repartition_values, distribution_profile, profile_params) "
            "VALUES (?, NULL, 'Month', ?, ?, '{}')",
            (name, json.dumps(weights), profile),
        )
    conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES ('split_presets_seeded', '1')")


def _setup_kpis():
    with db.connect(db.KPIS, foreign_keys=False) as conn:
        if _table_exists(conn, "kpi_nodes"):
            _add_missing_columns(conn, "kpi_nodes", {
                "custom_level_label": "TEXT",
                "is_active": "BOOLEAN NOT NULL DEFAULT 1",
                "indicator_template_id": "INTEGER",
            })
        conn.execute(KPI_TABLES["kpi_nodes"].format(name="kpi_nodes"))

        # Pre-hierarchy databases: copy groups/subgroups into kpi_nodes (subgroup ids offset by 1000).
        if _table_exists(conn, "kpi_groups"):
            conn.execute("INSERT OR IGNORE INTO kpi_nodes (id, name, node_type) SELECT id, name, 'group' FROM kpi_groups")
            if _table_exists(conn, "kpi_subgroups"):
                conn.execute(
                    "INSERT OR IGNORE INTO kpi_nodes (id, name, parent_id, node_type) "
                    "SELECT id + 1000, name, group_id, 'subgroup' FROM kpi_subgroups"
                )

        if _table_exists(conn, "kpi_indicators"):
            _add_missing_columns(conn, "kpi_indicators", {"is_active": "BOOLEAN NOT NULL DEFAULT 1", "node_id": "INTEGER"})
            if "subgroup_id" in db.table_columns(conn, "kpi_indicators"):
                conn.execute(
                    "UPDATE kpi_indicators SET node_id = subgroup_id + 1000 "
                    "WHERE (node_id IS NULL OR node_id = 0) AND subgroup_id IS NOT NULL"
                )

        if _table_exists(conn, "kpis"):
            _add_missing_columns(conn, "kpis", {
                "unit_of_measure": "TEXT",
                "formula_json": "TEXT",
                "formula_string": "TEXT",
                "is_calculated": "BOOLEAN NOT NULL DEFAULT 0",
                "default_distribution_profile": "TEXT",
                "owner": "TEXT",
                "direction": "TEXT DEFAULT 'Higher is Better'",
                "threshold_json": "TEXT",
                "target_granularity": "TEXT DEFAULT 'Monthly'",
                "target_count": "INTEGER DEFAULT 1",
                "time_filter_type": "TEXT DEFAULT 'None'",
                "time_filter_value": "TEXT",
                "target_labels": "TEXT",
            })

        def needs_rebuild(table, sql):
            if table == "kpi_indicators":
                # Very old schema: subgroup_id NOT NULL blocks creating indicators in folders.
                return any(c["name"] == "subgroup_id" and c["notnull"] for c in conn.execute("PRAGMA table_info(kpi_indicators)"))
            if table == "kpis":
                return "CHECK" in sql.upper()  # legacy CHECK(calculation_type IN ('Incremental','Average'))
            if table == "kpi_plant_visibility":
                return "REFERENCES PLANTS" in " ".join(sql.upper().split())
            return False

        _ensure_tables(conn, KPI_TABLES, needs_rebuild)

        for row in conn.execute("SELECT id, calculation_type FROM kpis").fetchall():
            try:
                canonical = normalize_calc_type(row["calculation_type"])
            except ValueError:
                canonical = CALC_TYPE_SUM
            if canonical != row["calculation_type"]:
                conn.execute("UPDATE kpis SET calculation_type=? WHERE id=?", (canonical, row["id"]))
        # A KPI is "calculated" exactly when it has a formula.
        conn.execute(
            "UPDATE kpis SET is_calculated = CASE WHEN COALESCE(TRIM(formula_string), '') != '' "
            "OR COALESCE(TRIM(formula_json), '') != '' THEN 1 ELSE 0 END"
        )

        if conn.execute("SELECT COUNT(*) FROM units_of_measure").fetchone()[0] == 0:
            existing = [r[0] for r in conn.execute(
                "SELECT DISTINCT unit_of_measure FROM kpis WHERE unit_of_measure IS NOT NULL AND TRIM(unit_of_measure) != ''"
            )]
            for unit in existing or ["Units"]:
                conn.execute("INSERT OR IGNORE INTO units_of_measure (name) VALUES (?)", (unit,))


def _setup_plants():
    with db.connect(db.PLANTS, foreign_keys=False) as conn:
        if _table_exists(conn, "plants"):
            _add_missing_columns(conn, "plants", {
                "description": "TEXT",
                "color": "TEXT NOT NULL DEFAULT '#3b82f6'",
                "is_active": "BOOLEAN NOT NULL DEFAULT 1",
            })
        _ensure_tables(conn, PLANT_TABLES)


def _setup_targets():
    with db.connect(db.TARGETS, foreign_keys=False) as conn:
        if _table_exists(conn, "annual_targets"):
            cols = set(db.table_columns(conn, "annual_targets"))
            if "stabilimento_id" in cols and "plant_id" not in cols:
                conn.execute("ALTER TABLE annual_targets RENAME COLUMN stabilimento_id TO plant_id")
        conn.execute(TARGET_TABLES["kpi_annual_target_values"].format(name="kpi_annual_target_values"))

        # Legacy fixed annual_target1/2 columns -> normalized values table (before any rebuild
        # drops those columns).
        if _table_exists(conn, "annual_targets") and "annual_target1" in db.table_columns(conn, "annual_targets"):
            if conn.execute("SELECT COUNT(*) FROM kpi_annual_target_values").fetchone()[0] == 0:
                for tn in (1, 2):
                    conn.execute(
                        f"""INSERT OR IGNORE INTO kpi_annual_target_values
                            (annual_target_id, target_number, target_value, is_manual, is_formula_based, formula, formula_inputs)
                            SELECT id, {tn}, annual_target{tn}, COALESCE(is_target{tn}_manual, 1),
                                   COALESCE(target{tn}_is_formula_based, 0), target{tn}_formula,
                                   COALESCE(target{tn}_formula_inputs, '[]')
                            FROM annual_targets WHERE annual_target{tn} IS NOT NULL"""
                    )

        def needs_rebuild(table, sql):
            # Legacy fixed-target columns are now dead weight once migrated above.
            return table == "annual_targets" and "annual_target1" in db.table_columns(conn, "annual_targets")

        _ensure_tables(conn, TARGET_TABLES, needs_rebuild)
        conn.execute("UPDATE annual_targets SET profile_params='{}' WHERE profile_params IS NULL OR profile_params=''")
        conn.execute("UPDATE annual_targets SET repartition_values='{}' WHERE repartition_values IS NULL OR repartition_values=''")


def _setup_simple(db_name: str, tables: dict):
    with db.connect(db_name, foreign_keys=False) as conn:
        _ensure_tables(conn, tables)


def _setup_periodic():
    for db_name, table, period_col in db.PERIOD_TABLES.values():
        with db.connect(db_name, foreign_keys=False) as conn:
            if _table_exists(conn, table):
                cols = set(db.table_columns(conn, table))
                if "stabilimento_id" in cols and "plant_id" not in cols:
                    conn.execute(f"ALTER TABLE {table} RENAME COLUMN stabilimento_id TO plant_id")

            def needs_rebuild(t, sql, _col=period_col):
                info = {c["name"]: c for c in conn.execute(f"PRAGMA table_info({db.ident(t)})")}
                col = info.get(_col)
                return col is not None and (not col["type"] or not col["notnull"])

            _ensure_tables(conn, {table: _period_table_ddl(period_col)}, needs_rebuild)


def _setup_users():
    with db.connect(db.USERS, foreign_keys=False) as conn:
        added_admin_column = False
        if _table_exists(conn, "users"):
            existing = set(db.table_columns(conn, "users"))
            added_admin_column = "is_admin" not in existing
            _add_missing_columns(conn, "users", {
                "password_hash": "TEXT",
                "password_salt": "TEXT",
                "is_admin": "BOOLEAN NOT NULL DEFAULT 0",
            })
        _ensure_tables(conn, USER_TABLES)
        # Upgrading a database from before roles existed: keep it administrable by making the
        # oldest active account the admin (instead of locking everyone out of user management).
        if added_admin_column and not conn.execute("SELECT 1 FROM users WHERE is_admin = 1").fetchone():
            conn.execute(
                "UPDATE users SET is_admin = 1 WHERE id = (SELECT MIN(id) FROM users WHERE is_active = 1)"
            )


def setup_databases():
    """Creates/migrates all databases. Idempotent; raises if a migration fails."""
    db_dir = app_config.get_database_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    log.info("Setting up databases in %s", db_dir)

    _setup_templates()
    _setup_kpis()
    _setup_plants()
    _setup_targets()
    _setup_simple(db.ACTUALS, ACTUAL_TABLES)
    _setup_simple(db.HISTORY, HISTORY_TABLES)
    _setup_periodic()
    _setup_users()
    log.info("Database setup completed.")
