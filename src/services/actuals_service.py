# src/services/actuals_service.py
import sqlite3
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from src.config import settings as app_config

def _get_actuals_db_connection() -> sqlite3.Connection:
    db_path = app_config.get_database_path("db_kpi_actuals.db")
    return sqlite3.connect(db_path)

def record_actual_measurement(
    kpi_id: int,
    plant_id: int,
    measurement_date: str,
    actual_value: float
) -> int:
    """
    Inserts or updates an actual measurement entry.
    """
    with _get_actuals_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO actual_measurements (kpi_id, plant_id, measurement_date, actual_value)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(kpi_id, plant_id, measurement_date) DO UPDATE SET actual_value = excluded.actual_value""",
            (kpi_id, plant_id, measurement_date, actual_value)
        )
        conn.commit()
        return cursor.lastrowid

def get_actual_measurements(
    kpi_id: int,
    plant_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves actual measurements for a given KPI and plant within optional date bounds.
    """
    query = "SELECT * FROM actual_measurements WHERE kpi_id = ? AND plant_id = ?"
    params = [kpi_id, plant_id]

    if start_date:
        query += " AND measurement_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND measurement_date <= ?"
        params.append(end_date)

    query += " ORDER BY measurement_date ASC"

    with _get_actuals_db_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]

def calculate_trend_slope(values: List[float]) -> float:
    """
    Calculates the linear regression slope for a time series of values.
    Positive slope indicates upward trend, negative indicates downward.
    """
    n = len(values)
    if n < 2:
        return 0.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / float(n)

    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    return numerator / denominator

def evaluate_performance_status(
    actual: float,
    target: float,
    direction: str = "Higher is Better",
    threshold_json: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates an actual value against a target using directional logic and threshold bands.
    Status can be 'on_track', 'warning', or 'out_of_range'.
    """
    thresholds = {}
    if threshold_json:
        try:
            thresholds = json.loads(threshold_json)
        except Exception:
            thresholds = {}

    warning_margin = thresholds.get("warning_margin", 0.05)  # 5% default margin
    error_margin = thresholds.get("error_margin", 0.15)      # 15% default margin

    direction_clean = direction.strip().lower() if direction else "higher is better"

    if direction_clean == "higher is better":
        if actual >= target:
            status = "on_track"
        elif actual >= target * (1.0 - warning_margin):
            status = "warning"
        else:
            status = "out_of_range"
        diff_pct = ((actual - target) / target * 100.0) if target != 0 else 0.0

    elif direction_clean == "lower is better":
        if actual <= target:
            status = "on_track"
        elif actual <= target * (1.0 + warning_margin):
            status = "warning"
        else:
            status = "out_of_range"
        diff_pct = ((target - actual) / target * 100.0) if target != 0 else 0.0

    elif direction_clean == "range":
        min_val = thresholds.get("min_target", target * (1 - warning_margin))
        max_val = thresholds.get("max_target", target * (1 + warning_margin))
        if min_val <= actual <= max_val:
            status = "on_track"
        elif (min_val * (1 - error_margin)) <= actual <= (max_val * (1 + error_margin)):
            status = "warning"
        else:
            status = "out_of_range"
        diff_pct = 0.0
    else:
        status = "on_track" if actual >= target else "out_of_range"
        diff_pct = 0.0

    return {
        "actual": actual,
        "target": target,
        "direction": direction,
        "status": status,
        "diff_pct": round(diff_pct, 2)
    }

def get_performance_status_for_kpi(
    kpi_id: int,
    plant_id: int,
    target_value: float,
    direction: str = "Higher is Better",
    threshold_json: Optional[str] = None,
    time_filter_type: str = "None",
    time_filter_value: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves recent actual measurements, applies time window filtering,
    evaluates status against target_value, and computes trend.
    """
    all_measurements = get_actual_measurements(kpi_id, plant_id)
    if not all_measurements:
        return {
            "kpi_id": kpi_id,
            "plant_id": plant_id,
            "status": "no_data",
            "actual_count": 0,
            "latest_actual": None,
            "target": target_value,
            "trend_slope": 0.0,
            "trend_direction": "stable"
        }

    # Apply time filter
    filter_type = time_filter_type.strip().lower() if time_filter_type else "none"
    filtered = all_measurements

    if filter_type == "rolling" and time_filter_value:
        try:
            days = int(time_filter_value)
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
            filtered = [m for m in all_measurements if m["measurement_date"] >= cutoff]
        except ValueError:
            filtered = all_measurements

    values = [m["actual_value"] for m in filtered]
    latest_actual = values[-1] if values else None

    if latest_actual is not None:
        eval_res = evaluate_performance_status(latest_actual, target_value, direction, threshold_json)
        status = eval_res["status"]
        diff_pct = eval_res["diff_pct"]
    else:
        status = "no_data"
        diff_pct = 0.0

    slope = calculate_trend_slope(values)
    if slope > 0.01:
        trend_dir = "improving" if direction.lower() == "higher is better" else "declining"
    elif slope < -0.01:
        trend_dir = "declining" if direction.lower() == "higher is better" else "improving"
    else:
        trend_dir = "stable"

    return {
        "kpi_id": kpi_id,
        "plant_id": plant_id,
        "status": status,
        "diff_pct": diff_pct,
        "actual_count": len(filtered),
        "latest_actual": latest_actual,
        "target": target_value,
        "trend_slope": round(slope, 4),
        "trend_direction": trend_dir
    }
