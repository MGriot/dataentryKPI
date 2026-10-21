# src/kpi_management/splits.py
"""Global Split Templates: reusable seasonal weight curves assigned to KPIs."""
import calendar
import datetime
import json
from typing import Iterable, Optional

from src.config.constants import (
    DISTRIBUTION_PROFILES,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    REPARTITION_LOGICS,
)
from src.data_access import db
from src.data_retriever import parse_json_field

# Columns update_global_split may touch -- anything else is rejected (never interpolated).
_UPDATABLE_COLUMNS = ("name", "repartition_logic", "repartition_values", "distribution_profile", "profile_params")
_JSON_COLUMNS = {"repartition_values", "profile_params"}


def _validate(repartition_logic: Optional[str] = None, distribution_profile: Optional[str] = None,
              repartition_values=None, profile_params=None):
    if repartition_logic is not None and repartition_logic not in REPARTITION_LOGICS:
        raise ValueError(f"Unknown repartition_logic '{repartition_logic}'. Use one of: {', '.join(REPARTITION_LOGICS)}.")
    if distribution_profile is not None and distribution_profile not in DISTRIBUTION_PROFILES:
        raise ValueError(f"Unknown distribution_profile '{distribution_profile}'.")
    if repartition_values is not None:
        if not isinstance(repartition_values, dict):
            raise ValueError("repartition_values must be an object of {period: weight}.")
        for key, value in repartition_values.items():
            try:
                if value is not None and float(value) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise ValueError(f"Weight for '{key}' must be a non-negative number.") from None
    if profile_params is not None and not isinstance(profile_params, dict):
        raise ValueError("profile_params must be an object.")


def _row_to_split(conn, row) -> dict:
    res = dict(row)
    res["repartition_values"] = parse_json_field(res.get("repartition_values"), {})
    res["profile_params"] = parse_json_field(res.get("profile_params"), {})
    res["years"] = [r[0] for r in conn.execute(
        "SELECT year FROM global_split_years WHERE global_split_id = ? ORDER BY year", (res["id"],)
    )]
    return res


def add_global_split(name: str, repartition_logic: str, repartition_values: dict, distribution_profile: str,
                     profile_params: dict, years: list = None, year: int = None, afflicted_indicators: list = None) -> int:
    """Creates a split template (optionally for specific years) and optionally links indicators."""
    if not (name or "").strip():
        raise ValueError("Split name cannot be empty.")
    repartition_values = repartition_values or {}
    profile_params = profile_params or {}
    _validate(repartition_logic, distribution_profile, repartition_values, profile_params)
    years = years if years is not None else ([year] if year is not None else [])
    with db.connect(db.TEMPLATES) as conn:
        try:
            split_id = conn.execute(
                "INSERT INTO global_kpi_splits (name, year, repartition_logic, repartition_values, distribution_profile, profile_params) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name.strip(), years[0] if years else None, repartition_logic, json.dumps(repartition_values),
                 distribution_profile, json.dumps(profile_params)),
            ).lastrowid
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError(f"A split named '{name}' already exists.") from e
            raise
        for y in years:
            conn.execute("INSERT OR IGNORE INTO global_split_years (global_split_id, year) VALUES (?, ?)", (split_id, int(y)))
        if afflicted_indicators:
            _replace_split_indicators(conn, split_id, afflicted_indicators)
    return split_id


def update_global_split(split_id: int, name: str = None, repartition_logic: str = None, repartition_values: dict = None,
                        distribution_profile: str = None, profile_params: dict = None, years: list = None,
                        afflicted_indicators: list = None) -> bool:
    """Updates the given fields of a split template. Returns False if the split doesn't exist.

    Only the explicit parameters above can change; the column list is fixed in code.
    """
    _validate(repartition_logic, distribution_profile, repartition_values, profile_params)
    changes = {
        "name": name.strip() if isinstance(name, str) else None,
        "repartition_logic": repartition_logic,
        "repartition_values": repartition_values,
        "distribution_profile": distribution_profile,
        "profile_params": profile_params,
    }
    with db.connect(db.TEMPLATES) as conn:
        if not conn.execute("SELECT 1 FROM global_kpi_splits WHERE id = ?", (split_id,)).fetchone():
            return False
        sets, params = [], []
        for column in _UPDATABLE_COLUMNS:
            value = changes[column]
            if value is None:
                continue
            sets.append(f"{column} = ?")
            params.append(json.dumps(value) if column in _JSON_COLUMNS else value)
        if sets:
            try:
                conn.execute(f"UPDATE global_kpi_splits SET {', '.join(sets)} WHERE id = ?", (*params, split_id))
            except Exception as e:
                if "UNIQUE" in str(e):
                    raise ValueError(f"A split named '{name}' already exists.") from e
                raise
        if years is not None:
            conn.execute("UPDATE global_kpi_splits SET year = ? WHERE id = ?", (years[0] if years else None, split_id))
            conn.execute("DELETE FROM global_split_years WHERE global_split_id = ?", (split_id,))
            for y in years:
                conn.execute("INSERT OR IGNORE INTO global_split_years (global_split_id, year) VALUES (?, ?)", (split_id, int(y)))
        if afflicted_indicators is not None:
            _replace_split_indicators(conn, split_id, afflicted_indicators)
    return True


def delete_global_split(split_id: int) -> list:
    """Deletes a split (cascades to its years/links). Returns the indicator ids that were using it."""
    with db.connect(db.TEMPLATES) as conn:
        affected = [r[0] for r in conn.execute(
            "SELECT indicator_id FROM global_split_indicators WHERE global_split_id = ?", (split_id,)
        )]
        conn.execute("DELETE FROM global_kpi_splits WHERE id = ?", (split_id,))
    return affected


def _replace_split_indicators(conn, split_id: int, indicators_data: Iterable[dict]):
    conn.execute("DELETE FROM global_split_indicators WHERE global_split_id = ?", (split_id,))
    for ind in indicators_data:
        profile = ind.get("override_distribution_profile")
        if profile is not None and profile not in DISTRIBUTION_PROFILES:
            raise ValueError(f"Unknown distribution_profile '{profile}'.")
        conn.execute(
            "INSERT INTO global_split_indicators (global_split_id, indicator_id, override_distribution_profile) VALUES (?, ?, ?)",
            (split_id, int(ind["indicator_id"]), profile),
        )


def get_indicators_for_global_split(split_id: int) -> list:
    with db.connect(db.TEMPLATES) as conn:
        return db.rows(conn.execute("SELECT * FROM global_split_indicators WHERE global_split_id = ?", (split_id,)))


def update_global_split_indicators(split_id: int, indicators_data: list):
    """Replaces the list of indicators linked to a split ({indicator_id, override_distribution_profile})."""
    with db.connect(db.TEMPLATES) as conn:
        _replace_split_indicators(conn, split_id, indicators_data)


def set_kpi_global_split(indicator_id: int, global_split_id: Optional[int]):
    """Assigns (or clears, with None) the single split template used by an indicator."""
    with db.connect(db.TEMPLATES) as conn:
        if global_split_id is not None and not conn.execute(
            "SELECT 1 FROM global_kpi_splits WHERE id = ?", (global_split_id,)
        ).fetchone():
            raise ValueError(f"Global split {global_split_id} not found.")
        conn.execute("DELETE FROM global_split_indicators WHERE indicator_id = ?", (indicator_id,))
        if global_split_id is not None:
            conn.execute(
                "INSERT INTO global_split_indicators (global_split_id, indicator_id, override_distribution_profile) VALUES (?, ?, NULL)",
                (global_split_id, indicator_id),
            )


def get_global_split(split_id: int) -> Optional[dict]:
    with db.connect(db.TEMPLATES) as conn:
        row = conn.execute("SELECT * FROM global_kpi_splits WHERE id = ?", (split_id,)).fetchone()
        return _row_to_split(conn, row) if row else None


def get_global_splits_for_indicator(indicator_id: int) -> list:
    """Split template(s) assigned to an indicator, most recent assignment first (with any override)."""
    with db.connect(db.TEMPLATES) as conn:
        rows = conn.execute(
            "SELECT s.*, i.override_distribution_profile FROM global_kpi_splits s "
            "JOIN global_split_indicators i ON s.id = i.global_split_id WHERE i.indicator_id = ? ORDER BY i.id DESC",
            (indicator_id,),
        ).fetchall()
        return [_row_to_split(conn, r) for r in rows]


def split_applies_to_year(split: dict, year: int) -> bool:
    """A split with no years attached is year-agnostic (presets); otherwise it must list the year."""
    years = split.get("years") or []
    return not years or year in years


def get_split_for_indicator_year(indicator_id: int, year: int) -> Optional[dict]:
    """The assigned split that covers `year`, or None (-> the KPI uses the default even split)."""
    return next((s for s in get_global_splits_for_indicator(indicator_id) if split_applies_to_year(s, year)), None)


def get_all_global_splits(year: int = None) -> list:
    """All split templates; with `year`, only those covering it (year-agnostic presets always included)."""
    query, params = "SELECT s.* FROM global_kpi_splits s", []
    if year:
        query += (
            " WHERE NOT EXISTS (SELECT 1 FROM global_split_years y WHERE y.global_split_id = s.id)"
            " OR EXISTS (SELECT 1 FROM global_split_years y WHERE y.global_split_id = s.id AND y.year = ?)"
        )
        params.append(year)
    query += " ORDER BY s.name"
    with db.connect(db.TEMPLATES) as conn:
        return [_row_to_split(conn, r) for r in conn.execute(query, params).fetchall()]


def week_keys(year: int = None) -> list:
    """Year-agnostic week keys W01..W52 (W53 too when `year` has 53 ISO weeks, or when no year is given)."""
    n_weeks = datetime.date(year, 12, 28).isocalendar()[1] if year else 53
    return [f"W{w:02d}" for w in range(1, n_weeks + 1)]


def get_curve_weight_suggestions(profile: str, logic: str, year: int = None) -> dict:
    """Suggested per-period weights (summing to ~100) for a curve, to pre-fill a template's weights."""
    from src.utils.repartition_utils import ramp_proportions, sinusoidal_proportions

    if logic == "Month":
        keys = [calendar.month_name[i] for i in range(1, 13)]
    elif logic == "Quarter":
        keys = ["Q1", "Q2", "Q3", "Q4"]
    elif logic == "Week":
        keys = week_keys(year)
    else:
        return {}

    n = len(keys)
    if profile in (PROFILE_ANNUAL_PROGRESSIVE, PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS):
        props = ramp_proportions(n, 0.8, 1.2)
    elif profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
        props = sinusoidal_proportions(n, 0.1, 0.0)
    else:
        # Even and Event Based only vary *within* periods, so per-period weights are flat.
        props = [1.0 / n] * n
    return {k: round(p * 100, 4) for k, p in zip(keys, props)}
