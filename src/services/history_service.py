# src/services/history_service.py
import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from src.config import settings as app_config

def _get_history_db_connection() -> sqlite3.Connection:
    db_path = app_config.get_database_path("db_kpi_history.db")
    return sqlite3.connect(db_path)

def record_definition_change(
    kpi_id: int,
    change_type: str,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    changed_by: Optional[str] = "system"
) -> int:
    """
    Logs a structural or configuration change to a KPI into kpi_definition_history.
    """
    changed_at = datetime.now(timezone.utc).isoformat()
    old_json = json.dumps(old_value) if old_value is not None else None
    new_json = json.dumps(new_value) if new_value is not None else None

    with _get_history_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO kpi_definition_history 
               (kpi_id, changed_at, changed_by, change_type, old_value_json, new_value_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (kpi_id, changed_at, changed_by, change_type, old_json, new_json)
        )
        conn.commit()
        return cursor.lastrowid

def record_target_change(
    kpi_id: int,
    plant_id: int,
    target_number: int,
    period_start: str,
    period_end: str,
    old_value: Optional[float],
    new_value: Optional[float],
    changed_by: Optional[str] = "system"
) -> int:
    """
    Logs a target value edit into target_value_history.
    """
    changed_at = datetime.now(timezone.utc).isoformat()
    with _get_history_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO target_value_history
               (kpi_id, plant_id, target_number, period_start, period_end, old_value, new_value, changed_at, changed_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (kpi_id, plant_id, target_number, period_start, period_end, old_value, new_value, changed_at, changed_by)
        )
        conn.commit()
        return cursor.lastrowid

def get_definition_history(kpi_id: int) -> List[Dict[str, Any]]:
    """
    Retrieves definition history for a specific KPI.
    """
    with _get_history_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM kpi_definition_history WHERE kpi_id = ? ORDER BY id DESC",
            (kpi_id,)
        )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("old_value_json"):
                try:
                    d["old_value"] = json.loads(d["old_value_json"])
                except Exception:
                    d["old_value"] = d["old_value_json"]
            if d.get("new_value_json"):
                try:
                    d["new_value"] = json.loads(d["new_value_json"])
                except Exception:
                    d["new_value"] = d["new_value_json"]
            result.append(d)
        return result

def get_target_history(kpi_id: int, plant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Retrieves target edit history for a specific KPI (and optionally plant).
    """
    with _get_history_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if plant_id is not None:
            cursor.execute(
                "SELECT * FROM target_value_history WHERE kpi_id = ? AND plant_id = ? ORDER BY id DESC",
                (kpi_id, plant_id)
            )
        else:
            cursor.execute(
                "SELECT * FROM target_value_history WHERE kpi_id = ? ORDER BY id DESC",
                (kpi_id,)
            )
        return [dict(r) for r in cursor.fetchall()]
