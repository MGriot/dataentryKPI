# src/services/actuals_service.py
"""Actual measurements and performance status (actual vs target, trend)."""
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.data_access import db


def record_actual_measurement(kpi_id: int, plant_id: int, measurement_date: str, actual_value: float) -> int:
    """Inserts or updates an actual measurement entry."""
    with db.connect(db.ACTUALS) as conn:
        conn.execute(
            """INSERT INTO actual_measurements (kpi_id, plant_id, measurement_date, actual_value)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(kpi_id, plant_id, measurement_date) DO UPDATE SET actual_value = excluded.actual_value""",
            (kpi_id, plant_id, measurement_date, actual_value),
        )
        return conn.execute(
            "SELECT id FROM actual_measurements WHERE kpi_id=? AND plant_id=? AND measurement_date=?",
            (kpi_id, plant_id, measurement_date),
        ).fetchone()[0]


def get_actual_measurements(kpi_id: int, plant_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT * FROM actual_measurements WHERE kpi_id = ? AND plant_id = ?"
    params: list = [kpi_id, plant_id]
    if start_date:
        query += " AND measurement_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND measurement_date <= ?"
        params.append(end_date)
    query += " ORDER BY measurement_date ASC"
    with db.connect(db.ACTUALS) as conn:
        return db.rows(conn.execute(query, params))


def calculate_trend_slope(values: List[float]) -> float:
    """Linear regression slope of a series (positive = upward)."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / float(n)
    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return numerator / denominator if denominator else 0.0


def _thresholds(threshold_json) -> dict:
    if isinstance(threshold_json, dict):
        return threshold_json
    if not threshold_json:
        return {}
    try:
        parsed = json.loads(threshold_json)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _num(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_performance_status(
    actual: float,
    target: float,
    direction: str = "Higher is Better",
    threshold_json: Optional[str] = None,
) -> Dict[str, Any]:
    """Compares an actual against a target. Status: 'on_track', 'warning' or 'out_of_range'.

    Margins are relative to |target|, so the bands are correct for negative targets too.
    """
    thresholds = _thresholds(threshold_json)
    warning_margin = abs(_num(thresholds.get("warning_margin"), 0.05))
    error_margin = abs(_num(thresholds.get("error_margin"), 0.15))
    band = abs(target) * warning_margin
    direction_clean = (direction or "Higher is Better").strip().lower()

    if direction_clean == "lower is better":
        if actual <= target:
            status = "on_track"
        elif actual <= target + band:
            status = "warning"
        else:
            status = "out_of_range"
        diff_pct = ((target - actual) / abs(target) * 100.0) if target else 0.0
    elif direction_clean == "range":
        min_val = _num(thresholds.get("min_target"), target - band)
        max_val = _num(thresholds.get("max_target"), target + band)
        span = abs(max_val - min_val) or abs(target) or 1.0
        if min_val <= actual <= max_val:
            status = "on_track"
        elif min_val - span * error_margin <= actual <= max_val + span * error_margin:
            status = "warning"
        else:
            status = "out_of_range"
        diff_pct = 0.0
    else:  # higher is better (default)
        if actual >= target:
            status = "on_track"
        elif actual >= target - band:
            status = "warning"
        else:
            status = "out_of_range"
        diff_pct = ((actual - target) / abs(target) * 100.0) if target else 0.0

    return {"actual": actual, "target": target, "direction": direction, "status": status, "diff_pct": round(diff_pct, 2)}


def get_performance_status_for_kpi(
    kpi_id: int,
    plant_id: int,
    target_value: float,
    direction: str = "Higher is Better",
    threshold_json: Optional[str] = None,
    time_filter_type: str = "None",
    time_filter_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Latest actual vs target_value (within the KPI's time filter), plus trend."""
    all_measurements = get_actual_measurements(kpi_id, plant_id)
    if not all_measurements:
        return {
            "kpi_id": kpi_id, "plant_id": plant_id, "status": "no_data", "actual_count": 0,
            "latest_actual": None, "target": target_value, "trend_slope": 0.0, "trend_direction": "stable",
        }

    filtered = all_measurements
    if (time_filter_type or "none").strip().lower() == "rolling" and time_filter_value:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=int(time_filter_value))).strftime("%Y-%m-%d")
            filtered = [m for m in all_measurements if m["measurement_date"] >= cutoff]
        except ValueError:
            filtered = all_measurements

    values = [m["actual_value"] for m in filtered]
    latest_actual = values[-1] if values else None
    if latest_actual is not None:
        eval_res = evaluate_performance_status(latest_actual, target_value, direction, threshold_json)
        status, diff_pct = eval_res["status"], eval_res["diff_pct"]
    else:
        status, diff_pct = "no_data", 0.0

    higher_is_better = (direction or "Higher is Better").strip().lower() != "lower is better"
    slope = calculate_trend_slope(values)
    if slope > 0.01:
        trend_dir = "improving" if higher_is_better else "declining"
    elif slope < -0.01:
        trend_dir = "declining" if higher_is_better else "improving"
    else:
        trend_dir = "stable"

    return {
        "kpi_id": kpi_id, "plant_id": plant_id, "status": status, "diff_pct": diff_pct,
        "actual_count": len(filtered), "latest_actual": latest_actual, "target": target_value,
        "trend_slope": round(slope, 4), "trend_direction": trend_dir,
    }
