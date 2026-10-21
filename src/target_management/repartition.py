# src/target_management/repartition.py
"""
Repartition engine: turns an annual target into daily values, then aggregates them into
weekly / monthly / quarterly targets.

How a day's value is built
--------------------------
1. A *profile* gives each day a relative shape (even, linear ramp, sine, weekday bias).
2. A *repartition logic* (Year / Month / Quarter / Week) plus per-period weights decides how
   much of the year each period gets. Within a period, days follow the profile's shape --
   so "Monthly weights + weekday bias" means the months follow the weights and, inside each
   month, weekdays get more than weekends.
3. Optional events (date ranges with a multiplier/addition) are applied.
4. The series is reconciled to the annual target by *scaling* (never by shifting every day,
   which could push days negative).

Calculation types
-----------------
* Additive (Sum, Count): periods SUM to the annual target; weights are shares.
* Level (Average, Last, Min, Max): the annual target is a level; weights are relative
  levels (normalised so the year still averages to the target); periods are aggregated
  with their own rule (mean / last day / min / max).

Week weights use year-agnostic keys "W01".."W53" (matched by each day's ISO week number);
legacy "YYYY-Www" / unpadded keys are still read.
"""
import calendar
import datetime
import re
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from src.config.constants import (
    CALC_TYPE_LAST,
    CALC_TYPE_MAX,
    CALC_TYPE_MIN,
    DEFAULT_DISTRIBUTION_PROFILE,
    DEFAULT_REPARTITION_LOGIC,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    REPARTITION_LOGIC_MONTH,
    REPARTITION_LOGIC_QUARTER,
    REPARTITION_LOGIC_WEEK,
    is_additive,
    normalize_calc_type,
)
from src.data_access import db
from src.utils.repartition_utils import days_of_year, iso_week_label, quarter_of, weekday_weights

# Schema aliases used by engine_connection().
TARGETS_SCHEMA = "main"
HISTORY_SCHEMA = "hist"

_MONTH_KEYS = {calendar.month_name[i].lower(): i for i in range(1, 13)}
_MONTH_KEYS.update({calendar.month_abbr[i].lower(): i for i in range(1, 13)})
_WEEK_KEY = re.compile(r"^(?:\d{4}-)?W(\d{1,2})$", re.IGNORECASE)
_QUARTER_KEY = re.compile(r"^Q([1-4])$", re.IGNORECASE)


def engine_connection():
    """One connection (targets + all periodic DBs + history attached) so a save commits atomically."""
    attach = {alias: db.PERIOD_TABLES[pt][0] for pt, alias in db.PERIOD_ALIASES.items()}
    attach[HISTORY_SCHEMA] = db.HISTORY
    return db.connect(db.TARGETS, attach=attach)


# --- Shape & weights ---

def _profile_shape(dates: List[datetime.date], profile: str, params: dict) -> np.ndarray:
    n = len(dates)
    t = np.arange(n) / max(n - 1, 1)
    if profile == PROFILE_ANNUAL_PROGRESSIVE:
        return 0.8 + 0.4 * t
    if profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
        return (0.8 + 0.4 * t) * weekday_weights(
            dates, params.get("weekday_weight", 1.3), params.get("weekend_weight", 0.7)
        )
    if profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
        amplitude = min(abs(float(params.get("sine_amplitude", 0.1) or 0.1)), 0.95)
        phase = float(params.get("sine_phase", 0.0) or 0.0)
        return 1.0 + amplitude * np.sin(2 * np.pi * t + phase)
    return np.ones(n)  # even / event-based / unknown


def _period_of(date: datetime.date, logic: str) -> int:
    if logic == REPARTITION_LOGIC_MONTH:
        return date.month
    if logic == REPARTITION_LOGIC_QUARTER:
        return quarter_of(date)
    if logic == REPARTITION_LOGIC_WEEK:
        return date.isocalendar()[1]
    return 0


def parse_period_weights(logic: str, values: Optional[dict]) -> Dict[int, float]:
    """{period index: weight} from user-entered keys (month names, Q1..Q4, W01..W53)."""
    out: Dict[int, float] = {}
    for key, raw in (values or {}).items():
        try:
            weight = float(raw)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(weight) or weight < 0:
            continue
        key = str(key).strip()
        idx = None
        if logic == REPARTITION_LOGIC_MONTH:
            idx = _MONTH_KEYS.get(key.lower())
            if idx is None and key.isdigit() and 1 <= int(key) <= 12:
                idx = int(key)
        elif logic == REPARTITION_LOGIC_QUARTER:
            m = _QUARTER_KEY.match(key)
            idx = int(m.group(1)) if m else None
        elif logic == REPARTITION_LOGIC_WEEK:
            m = _WEEK_KEY.match(key)
            idx = int(m.group(1)) if m and 1 <= int(m.group(1)) <= 53 else None
        if idx is not None:
            out[idx] = out.get(idx, 0.0) + weight
    return out


def compute_daily_values(
    year: int,
    annual_target: float,
    calc_type: str,
    logic: str = DEFAULT_REPARTITION_LOGIC,
    values: Optional[dict] = None,
    profile: str = DEFAULT_DISTRIBUTION_PROFILE,
    params: Optional[dict] = None,
) -> Tuple[List[datetime.date], np.ndarray]:
    """Daily values for one KPI/year whose sum (additive) or mean (level types) equals annual_target."""
    params = params or {}
    dates = days_of_year(year)
    n = len(dates)
    additive = is_additive(calc_type)
    shape = _profile_shape(dates, profile, params)

    groups = np.array([_period_of(d, logic) for d in dates])
    present = sorted(set(groups.tolist()))
    weights = parse_period_weights(logic, values) if logic in (REPARTITION_LOGIC_MONTH, REPARTITION_LOGIC_QUARTER, REPARTITION_LOGIC_WEEK) else {}
    weights = {g: w for g, w in weights.items() if g in present}
    if not weights or sum(weights.values()) <= 0:
        groups = np.zeros(n, dtype=int)
        present, weights = [0], {0: 1.0}

    daily = np.zeros(n)
    if additive:
        total_w = sum(weights.get(g, 0.0) for g in present)
        for g in present:
            mask = groups == g
            share = weights.get(g, 0.0) / total_w
            daily[mask] = annual_target * share * shape[mask] / shape[mask].sum()
    else:
        provided = [w for w in weights.values()]
        default_w = sum(provided) / len(provided)
        w_by_group = {g: weights.get(g, default_w) for g in present}
        day_weighted_mean = sum(w_by_group[g] * np.count_nonzero(groups == g) for g in present) / n
        for g in present:
            mask = groups == g
            level = w_by_group[g] / day_weighted_mean if day_weighted_mean else 1.0
            daily[mask] = annual_target * level * shape[mask] / shape[mask].mean()

    daily = _apply_events(daily, dates, params.get("events") or [])
    return dates, reconcile(daily, annual_target, additive)


def _apply_events(daily: np.ndarray, dates: List[datetime.date], events: list) -> np.ndarray:
    if not events:
        return daily
    adjusted = daily.copy()
    for ev in events:
        try:
            start = datetime.date.fromisoformat(ev["start_date"])
            end = datetime.date.fromisoformat(ev["end_date"])
            mult = float(ev.get("multiplier", 1.0))
            add = float(ev.get("addition", 0.0))
        except (KeyError, TypeError, ValueError):
            continue
        for i, d in enumerate(dates):
            if start <= d <= end:
                adjusted[i] = adjusted[i] * mult + add
    return adjusted


def reconcile(daily: np.ndarray, annual_target: float, additive: bool) -> np.ndarray:
    """Scales the series so its sum (additive) or mean (level) equals annual_target."""
    if daily.size == 0:
        return daily
    current = daily.sum() if additive else daily.mean()
    if abs(current) > 1e-12:
        return daily * (annual_target / current)
    fill = annual_target / daily.size if additive else annual_target
    return np.full(daily.size, fill, dtype=float)


def aggregate(values: List[float], calc_type: str) -> float:
    calc = normalize_calc_type(calc_type)
    if is_additive(calc):
        return float(np.sum(values))
    if calc == CALC_TYPE_LAST:
        return float(values[-1])
    if calc == CALC_TYPE_MIN:
        return float(np.min(values))
    if calc == CALC_TYPE_MAX:
        return float(np.max(values))
    return float(np.mean(values))  # Average


def aggregate_periods(dates: List[datetime.date], daily: np.ndarray, calc_type: str) -> Dict[str, Dict[str, float]]:
    """{'Week': {'2026-W01': v, ...}, 'Month': {'January': v, ...}, 'Quarter': {'Q1': v, ...}}"""
    buckets: Dict[str, Dict[str, list]] = {"Week": {}, "Month": {}, "Quarter": {}}
    for d, v in zip(dates, daily):
        buckets["Week"].setdefault(iso_week_label(d), []).append(float(v))
        buckets["Month"].setdefault(calendar.month_name[d.month], []).append(float(v))
        buckets["Quarter"].setdefault(f"Q{quarter_of(d)}", []).append(float(v))
    return {pt: {k: aggregate(vs, calc_type) for k, vs in b.items()} for pt, b in buckets.items()}


# --- Persistence ---

def save_periodic_targets(conn, year: int, plant_id: int, kpi_id: int, target_number: int,
                          dates: List[datetime.date], daily: np.ndarray, calc_type: str):
    """Replaces this KPI/plant/year/target's day/week/month/quarter rows (on an engine_connection)."""
    delete_periodic_targets(conn, year, plant_id, kpi_id, target_number)
    day_alias = db.PERIOD_ALIASES["Day"]
    conn.executemany(
        f"INSERT INTO {day_alias}.daily_targets (year, plant_id, kpi_id, target_number, date_value, target_value) VALUES (?,?,?,?,?,?)",
        [(year, plant_id, kpi_id, target_number, d.isoformat(), float(v)) for d, v in zip(dates, daily)],
    )
    for period_type, by_period in aggregate_periods(dates, daily, calc_type).items():
        _, table, col = db.PERIOD_TABLES[period_type]
        alias = db.PERIOD_ALIASES[period_type]
        conn.executemany(
            f"INSERT INTO {alias}.{table} (year, plant_id, kpi_id, target_number, {col}, target_value) VALUES (?,?,?,?,?,?)",
            [(year, plant_id, kpi_id, target_number, period, value) for period, value in by_period.items()],
        )


def delete_periodic_targets(conn, year: int, plant_id: int, kpi_id: int, target_number: Optional[int] = None):
    for period_type, (_, table, _) in db.PERIOD_TABLES.items():
        alias = db.PERIOD_ALIASES[period_type]
        sql = f"DELETE FROM {alias}.{table} WHERE year=? AND plant_id=? AND kpi_id=?"
        params = [year, plant_id, kpi_id]
        if target_number is not None:
            sql += " AND target_number=?"
            params.append(target_number)
        conn.execute(sql, params)


def read_daily_series(conn, year: int, plant_id: int, kpi_id: int, target_number: int) -> Optional[np.ndarray]:
    """Daily values already stored (in this transaction) for a KPI, aligned to days_of_year; None if absent."""
    rows = conn.execute(
        f"SELECT date_value, target_value FROM {db.PERIOD_ALIASES['Day']}.daily_targets "
        "WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=?",
        (year, plant_id, kpi_id, target_number),
    ).fetchall()
    if not rows:
        return None
    by_date = {r["date_value"]: r["target_value"] for r in rows}
    return np.array([float(by_date.get(d.isoformat(), 0.0)) for d in days_of_year(year)])


def resolve_distribution(kpi: dict, annual_entry: Optional[dict], year: int,
                         split_lookup: Callable[[int, int], Optional[dict]]) -> Tuple[str, dict, str, dict]:
    """(logic, values, profile, params) for a KPI/year.

    Precedence: the split template assigned to the KPI in KPI Explorer (if it covers the
    year) > the annual record's own config (legacy API field) > the KPI's default profile >
    an even split over the year.
    """
    from src.data_retriever import parse_json_field

    split = split_lookup(kpi["indicator_id"], year) if kpi.get("indicator_id") else None
    if split:
        profile = split.get("override_distribution_profile") or split["distribution_profile"]
        return split["repartition_logic"], split["repartition_values"] or {}, profile, split["profile_params"] or {}
    if annual_entry and annual_entry.get("global_split_id"):
        from src.kpi_management.splits import get_global_split
        legacy = get_global_split(annual_entry["global_split_id"])
        if legacy:
            return legacy["repartition_logic"], legacy["repartition_values"] or {}, legacy["distribution_profile"], legacy["profile_params"] or {}
    if annual_entry:
        logic = annual_entry.get("repartition_logic") or DEFAULT_REPARTITION_LOGIC
        profile = annual_entry.get("distribution_profile") or kpi.get("default_distribution_profile") or DEFAULT_DISTRIBUTION_PROFILE
        return (logic, parse_json_field(annual_entry.get("repartition_values"), {}), profile,
                parse_json_field(annual_entry.get("profile_params"), {}))
    return DEFAULT_REPARTITION_LOGIC, {}, kpi.get("default_distribution_profile") or DEFAULT_DISTRIBUTION_PROFILE, {}

