"""
Single entry point for SQLite access.

`connect()` always: sets a busy timeout (several processes -- REST API and MCP server --
share the same files), enables foreign keys, returns rows as sqlite3.Row, commits on
success / rolls back on error, and CLOSES the connection (the bare
`with sqlite3.connect(...)` idiom only commits; it never closes).

Writes that touch several database files go through one connection with the other files
ATTACHed, so SQLite commits them atomically (rollback-journal mode, not WAL: WAL does not
guarantee atomicity across attached databases).
"""
import re
import sqlite3
from contextlib import contextmanager
from typing import Iterator, Mapping, Optional

from src.config import settings as app_config

# --- Database files ---
KPIS = "db_kpis.db"
PLANTS = "db_plants.db"
TARGETS = "db_kpi_targets.db"
TEMPLATES = "db_kpi_templates.db"
DAYS = "db_kpi_days.db"
WEEKS = "db_kpi_weeks.db"
MONTHS = "db_kpi_months.db"
QUARTERS = "db_kpi_quarters.db"
ACTUALS = "db_kpi_actuals.db"
HISTORY = "db_kpi_history.db"
USERS = "db_users.db"

ALL_DATABASES = (KPIS, PLANTS, TARGETS, TEMPLATES, DAYS, WEEKS, MONTHS, QUARTERS, ACTUALS, HISTORY, USERS)

# period type -> (database file, table, period column)
PERIOD_TABLES = {
    "Day": (DAYS, "daily_targets", "date_value"),
    "Week": (WEEKS, "weekly_targets", "week_value"),
    "Month": (MONTHS, "monthly_targets", "month_value"),
    "Quarter": (QUARTERS, "quarterly_targets", "quarter_value"),
}

# Schema aliases used when the periodic databases are attached to one connection.
PERIOD_ALIASES = {"Day": "days", "Week": "weeks", "Month": "months", "Quarter": "quarters"}

BUSY_TIMEOUT_SECONDS = 15
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def path(db_name: str):
    return app_config.get_database_path(db_name)


def ident(name: str) -> str:
    """Validates an SQL identifier (table/column/schema name) that can't be bound as a parameter."""
    if not _IDENT.match(name or ""):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _open(db_name: str, foreign_keys: bool) -> sqlite3.Connection:
    conn = sqlite3.connect(path(db_name), timeout=BUSY_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_SECONDS * 1000}")
    conn.execute(f"PRAGMA foreign_keys = {'ON' if foreign_keys else 'OFF'}")
    return conn


@contextmanager
def connect(
    db_name: str,
    attach: Optional[Mapping[str, str]] = None,
    foreign_keys: bool = True,
) -> Iterator[sqlite3.Connection]:
    """Opens `db_name` (optionally ATTACHing {alias: db_name}), commits/rolls back, and closes."""
    conn = _open(db_name, foreign_keys)
    try:
        for alias, other_db in (attach or {}).items():
            conn.execute(f"ATTACH DATABASE ? AS {ident(alias)}", (str(path(other_db)),))
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(cursor_or_list) -> list:
    return [dict(r) for r in cursor_or_list]


def table_columns(conn: sqlite3.Connection, table: str, schema: str = "main") -> list:
    return [r["name"] for r in conn.execute(f"PRAGMA {ident(schema)}.table_info({ident(table)})")]
