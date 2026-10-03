# src/services/history_service.py
"""Audit trail: KPI definition changes and target value edits (db_kpi_history.db).

The record_* functions accept an optional open connection plus the schema alias the
history database is attached under, so audit rows commit atomically with the change
they describe.
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.data_access import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_definition_change(
    kpi_id: int,
    change_type: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    changed_by: Optional[str] = "system",
    conn=None,
    schema: str = "main",
) -> int:
    """Logs a structural or configuration change to a KPI."""
    params = (
        kpi_id, _now(), changed_by, change_type,
        json.dumps(old_value, default=str) if old_value is not None else None,
        json.dumps(new_value, default=str) if new_value is not None else None,
    )
    sql = (
        f"INSERT INTO {db.ident(schema)}.kpi_definition_history "
        "(kpi_id, changed_at, changed_by, change_type, old_value_json, new_value_json) VALUES (?, ?, ?, ?, ?, ?)"
    )
    if conn is not None:
        return conn.execute(sql, params).lastrowid
    with db.connect(db.HISTORY) as c:
        return c.execute(sql.replace(f"{schema}.", "main.", 1), params).lastrowid


def record_target_change(
    kpi_id: int,
    plant_id: int,
    target_number: int,
    period_start: str,
    period_end: str,
    old_value: Optional[float],
    new_value: Optional[float],
    changed_by: Optional[str] = "system",
    conn=None,
    schema: str = "main",
) -> int:
    """Logs a target value edit."""
    params = (kpi_id, plant_id, target_number, period_start, period_end, old_value, new_value, _now(), changed_by)
    sql = (
        f"INSERT INTO {db.ident(schema)}.target_value_history "
        "(kpi_id, plant_id, target_number, period_start, period_end, old_value, new_value, changed_at, changed_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    if conn is not None:
        return conn.execute(sql, params).lastrowid
    with db.connect(db.HISTORY) as c:
        return c.execute(sql.replace(f"{schema}.", "main.", 1), params).lastrowid


def _decode(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def get_definition_history(kpi_id: int) -> List[Dict[str, Any]]:
    with db.connect(db.HISTORY) as conn:
        out = db.rows(conn.execute("SELECT * FROM kpi_definition_history WHERE kpi_id = ? ORDER BY id DESC", (kpi_id,)))
    for d in out:
        if d.get("old_value_json"):
            d["old_value"] = _decode(d["old_value_json"])
        if d.get("new_value_json"):
            d["new_value"] = _decode(d["new_value_json"])
    return out


def get_target_history(kpi_id: int, plant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    with db.connect(db.HISTORY) as conn:
        if plant_id is not None:
            return db.rows(conn.execute(
                "SELECT * FROM target_value_history WHERE kpi_id = ? AND plant_id = ? ORDER BY id DESC", (kpi_id, plant_id)
            ))
        return db.rows(conn.execute("SELECT * FROM target_value_history WHERE kpi_id = ? ORDER BY id DESC", (kpi_id,)))
