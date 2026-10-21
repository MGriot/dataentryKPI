# src/services/actuals_service.py
"""Actual measurements and performance status (actual vs target, trend)."""
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.config.constants import is_additive
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


def get_stored_target(
    kpi_id: int, plant_id: int, on_date: str, target_number: int = 1, calc_type: Optional[str] = None,
) -> Tuple[float, str]:
    """The stored target an actual measured on `on_date` (YYYY-MM-DD) is compared against: (value, source).

    The day's repartitioned target comes first ("daily"): for a level KPI it is the level for that
    day, for an additive KPI that day's share -- either way it matches one day's actual. Level KPIs
    (Average, Last, Min, Max) fall back to the annual target ("annual"), which is itself a level.
    Additive KPIs (Sum, Count) don't: an annual total isn't comparable with one day's actual.
    Raises LookupError if there is no usable target.
    """
    year = int(on_date[:4])
    with db.connect(db.DAYS) as conn:
        row = conn.execute(
            "SELECT target_value FROM daily_targets "
            "WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=? AND date_value=?",
            (year, plant_id, kpi_id, target_number, on_date),
        ).fetchone()
    if row and row[0] is not None:
        return float(row[0]), "daily"
    if not is_additive(calc_type):
        with db.connect(db.TARGETS) as conn:
            row = conn.execute(
                "SELECT v.target_value FROM kpi_annual_target_values v "
                "JOIN annual_targets t ON v.annual_target_id = t.id "
                "WHERE t.year=? AND t.plant_id=? AND t.kpi_id=? AND v.target_number=?",
                (year, plant_id, kpi_id, target_number),
            ).fetchone()
        if row and row[0] is not None:
            return float(row[0]), "annual"
    raise LookupError(
        f"No target {target_number} stored for KPI {kpi_id} at plant {plant_id} for {on_date}. "
        f"Save a {year} annual target for it, or pass target_value."
    )


def get_performance_status_for_kpi(
    kpi_id: int,
    plant_id: int,
    target_value: Optional[float] = None,
    direction: str = "Higher is Better",
    threshold_json: Optional[str] = None,
    time_filter_type: str = "None",
    time_filter_value: Optional[str] = None,
    calc_type: Optional[str] = None,
    target_number: int = 1,
) -> Dict[str, Any]:
    """Latest actual (within the KPI's time filter) vs a target, plus trend.

    An explicit target_value wins; otherwise the stored target for the latest actual's day is used
    (see get_stored_target), and LookupError is raised if there is none.
    """
    target_source = "explicit" if target_value is not None else None
    all_measurements = get_actual_measurements(kpi_id, plant_id)
    if not all_measurements:
        return {
            "kpi_id": kpi_id, "plant_id": plant_id, "status": "no_data", "actual_count": 0,
            "latest_actual": None, "target": target_value, "target_source": target_source,
            "trend_slope": 0.0, "trend_direction": "stable",
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
        if target_value is None:
            target_value, target_source = get_stored_target(
                kpi_id, plant_id, filtered[-1]["measurement_date"], target_number, calc_type
            )
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
        "target_source": target_source, "trend_slope": round(slope, 4), "trend_direction": trend_dir,
    }
