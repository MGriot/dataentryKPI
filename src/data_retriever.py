"""Read-only query facade used by the REST API, the MCP server and the engine."""
import calendar
import json
from typing import Optional

from src.config.constants import PERIOD_TYPES
from src.data_access import db

_MONTH_INDEX = {calendar.month_name[i]: i for i in range(1, 13)}

_KPI_SELECT = """
    WITH RECURSIVE NodePaths AS (
        SELECT id, name, parent_id, name AS path FROM kpi_nodes WHERE parent_id IS NULL
        UNION ALL
        SELECT n.id, n.name, n.parent_id, np.path || ' > ' || n.name
        FROM kpi_nodes n JOIN NodePaths np ON n.parent_id = np.id
    )
    SELECT s.*,
           i.id AS indicator_id,
           i.id AS actual_indicator_id,
           i.name AS indicator_name,
           i.node_id,
           i.is_active AS is_active,
           np.path AS hierarchy_path
    FROM kpis s
    JOIN kpi_indicators i ON s.indicator_id = i.id
    LEFT JOIN NodePaths np ON i.node_id = np.id
"""

_BOOL_FIELDS = ("visible", "is_calculated", "is_active")


def _kpi_row(row) -> dict:
    d = dict(row)
    for field in _BOOL_FIELDS:
        if field in d and d[field] is not None:
            d[field] = bool(d[field])
    return d


def period_sort_key(period_type: str, period: str):
    if period_type == "Month":
        return _MONTH_INDEX.get(period, 99)
    return period or ""


def validate_period_type(period_type: str) -> str:
    if period_type not in PERIOD_TYPES:
        raise ValueError(f"Unknown period_type '{period_type}'. Use one of: {', '.join(PERIOD_TYPES)}.")
    return period_type


# --- KPI Specifications ---

def get_all_kpis_detailed(only_visible: bool = False, plant_id: Optional[int] = None, include_inactive: bool = False) -> list:
    """All KPI specs with hierarchy path. Soft-deleted KPIs are excluded unless include_inactive."""
    conditions, params = [], []
    if not include_inactive:
        conditions.append("i.is_active = 1")
    if only_visible:
        conditions.append("s.visible = 1")
    if plant_id:
        conditions.append(
            "s.id NOT IN (SELECT kpi_id FROM kpi_plant_visibility WHERE plant_id = ? AND is_enabled = 0)"
        )
        params.append(plant_id)
    query = _KPI_SELECT + (" WHERE " + " AND ".join(conditions) if conditions else "") + " ORDER BY np.path, i.name"
    with db.connect(db.KPIS) as conn:
        return [_kpi_row(r) for r in conn.execute(query, params)]


def get_kpi_detailed_by_id(kpi_spec_id: int, plant_id: Optional[int] = None, include_inactive: bool = False):
    """A single KPI spec (or None). With plant_id, returns None if the KPI is disabled for that plant."""
    conditions, params = ["s.id = ?"], [kpi_spec_id]
    if not include_inactive:
        conditions.append("i.is_active = 1")
    if plant_id:
        conditions.append("s.id NOT IN (SELECT kpi_id FROM kpi_plant_visibility WHERE plant_id = ? AND is_enabled = 0)")
        params.append(plant_id)
    with db.connect(db.KPIS) as conn:
        row = conn.execute(_KPI_SELECT + " WHERE " + " AND ".join(conditions), params).fetchone()
    return _kpi_row(row) if row else None


# --- Plants ---

def get_all_plants(visible_only: bool = False) -> list:
    query = "SELECT * FROM plants" + (" WHERE visible = 1" if visible_only else "") + " ORDER BY name"
    with db.connect(db.PLANTS) as conn:
        out = db.rows(conn.execute(query))
    for p in out:
        p["visible"] = bool(p["visible"])
    return out


# --- Templates ---

def get_kpi_indicator_templates() -> list:
    with db.connect(db.TEMPLATES) as conn:
        return db.rows(conn.execute("SELECT * FROM kpi_indicator_templates ORDER BY name"))


def get_template_defined_indicators(template_id: int) -> list:
    with db.connect(db.TEMPLATES) as conn:
        return db.rows(conn.execute(
            "SELECT * FROM template_defined_indicators WHERE template_id = ? ORDER BY indicator_name_in_template",
            (template_id,),
        ))


# --- Annual targets ---

def _annual_with_values(conn, row, schema: str = "main") -> dict:
    data = dict(row)
    values = db.rows(conn.execute(
        f"SELECT * FROM {db.ident(schema)}.kpi_annual_target_values WHERE annual_target_id = ? ORDER BY target_number",
        (row["id"],),
    ))
    data["target_values"] = values
    # Flat aliases kept for API compatibility (annual_target1, target1_is_formula_based, ...).
    for tv in values:
        tn = tv["target_number"]
        data[f"annual_target{tn}"] = tv["target_value"]
        data[f"is_target{tn}_manual"] = tv["is_manual"]
        data[f"target{tn}_is_formula_based"] = tv["is_formula_based"]
        data[f"target{tn}_formula"] = tv["formula"]
        data[f"target{tn}_formula_inputs"] = tv["formula_inputs"]
    return data


def get_annual_target_entry(year: int, plant_id: int, kpi_id: int, conn=None, schema: str = "main"):
    """The annual target record (with all target_values) for a KPI/plant/year, or None.

    Pass an open connection (and the schema alias the targets DB is attached under) to read
    inside an ongoing write transaction.
    """
    if conn is not None:
        row = conn.execute(
            f"SELECT * FROM {db.ident(schema)}.annual_targets WHERE year=? AND plant_id=? AND kpi_id=?",
            (year, plant_id, kpi_id),
        ).fetchone()
        return _annual_with_values(conn, row, schema) if row else None
    with db.connect(db.TARGETS) as c:
        row = c.execute("SELECT * FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?", (year, plant_id, kpi_id)).fetchone()
        return _annual_with_values(c, row) if row else None


def get_annual_targets(plant_id: int, year: int) -> list:
    with db.connect(db.TARGETS) as conn:
        return [_annual_with_values(conn, r) for r in conn.execute(
            "SELECT * FROM annual_targets WHERE plant_id=? AND year=? ORDER BY kpi_id", (plant_id, year)
        ).fetchall()]


def get_available_target_numbers_for_kpi(year: int, plant_id: int, kpi_id: int) -> list:
    with db.connect(db.TARGETS) as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT v.target_number FROM kpi_annual_target_values v "
            "JOIN annual_targets t ON v.annual_target_id = t.id "
            "WHERE t.kpi_id=? AND t.year=? AND t.plant_id=? ORDER BY v.target_number",
            (kpi_id, year, plant_id),
        )]


# --- Periodic targets ---

def get_periodic_targets_for_kpi(year: int, plant_id: int, kpi_id: int, period_type: str, target_number: int) -> list:
    """[{period, target_value}] in chronological order."""
    validate_period_type(period_type)
    if period_type == "Year":
        with db.connect(db.TARGETS) as conn:
            return db.rows(conn.execute(
                "SELECT 'Year' AS period, v.target_value FROM kpi_annual_target_values v "
                "JOIN annual_targets t ON v.annual_target_id = t.id "
                "WHERE t.year=? AND t.plant_id=? AND t.kpi_id=? AND v.target_number=?",
                (year, plant_id, kpi_id, target_number),
            ))
    db_name, table, col = db.PERIOD_TABLES[period_type]
    with db.connect(db_name) as conn:
        out = db.rows(conn.execute(
            f"SELECT {col} AS period, target_value FROM {table} WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=?",
            (year, plant_id, kpi_id, target_number),
        ))
    return sorted(out, key=lambda r: period_sort_key(period_type, r["period"]))


def get_periodic_targets_for_kpi_all_plants(kpi_spec_id: int, period_type: str, year: Optional[int] = None) -> list:
    """Periodic targets for one KPI across all plants (with plant names), chronologically per plant."""
    validate_period_type(period_type)
    params = [kpi_spec_id]
    year_filter = ""
    if year:
        year_filter = " AND t.year = ?"
        params.append(year)
    if period_type == "Year":
        query = (
            "SELECT t.year, t.plant_id, p.name AS plant_name, t.kpi_id, v.target_number, 'Year' AS period, v.target_value "
            "FROM kpi_annual_target_values v JOIN annual_targets t ON v.annual_target_id = t.id "
            "LEFT JOIN plants_db.plants p ON t.plant_id = p.id WHERE t.kpi_id = ?" + year_filter
        )
        db_name = db.TARGETS
    else:
        db_name, table, col = db.PERIOD_TABLES[period_type]
        query = (
            f"SELECT t.year, t.plant_id, p.name AS plant_name, t.kpi_id, t.target_number, t.{col} AS period, t.target_value "
            f"FROM {table} t LEFT JOIN plants_db.plants p ON t.plant_id = p.id WHERE t.kpi_id = ?" + year_filter
        )
    with db.connect(db_name, attach={"plants_db": db.PLANTS}) as conn:
        out = db.rows(conn.execute(query, params))
    return sorted(out, key=lambda r: (r["year"], r["plant_name"] or "", r["target_number"], period_sort_key(period_type, r["period"])))


def get_daily_targets_for_kpi(year: int, plant_id: int, kpi_id: int, target_number: int) -> list:
    with db.connect(db.DAYS) as conn:
        return db.rows(conn.execute(
            "SELECT date_value, target_value FROM daily_targets "
            "WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=? ORDER BY date_value",
            (year, plant_id, kpi_id, target_number),
        ))


def get_all_periodic_targets_for_export(period_type: str) -> list:
    """period_type: Day/Week/Month/Quarter."""
    db_name, table, col = db.PERIOD_TABLES[period_type]
    with db.connect(db_name) as conn:
        out = db.rows(conn.execute(
            f"SELECT year, plant_id, kpi_id, target_number, {col} AS period_value, target_value FROM {table}"
        ))
    return sorted(out, key=lambda r: (r["year"], r["plant_id"], r["kpi_id"], r["target_number"],
                                      period_sort_key(period_type, r["period_value"])))


def get_all_periodic_targets_unified() -> list:
    unified = []
    for period_type in ("Day", "Week", "Month", "Quarter"):
        for row in get_all_periodic_targets_for_export(period_type):
            row["period_type"] = period_type
            unified.append(row)
    return unified


def get_distinct_years() -> list:
    with db.connect(db.TARGETS) as conn:
        return db.rows(conn.execute("SELECT DISTINCT year FROM annual_targets ORDER BY year DESC"))


# --- Export helpers ---

def get_all_kpi_nodes() -> list:
    with db.connect(db.KPIS) as conn:
        return db.rows(conn.execute("SELECT * FROM kpi_nodes ORDER BY id"))


def get_all_kpi_plant_visibility() -> list:
    with db.connect(db.KPIS) as conn:
        return db.rows(conn.execute("SELECT * FROM kpi_plant_visibility ORDER BY kpi_id, plant_id"))


def get_all_kpi_definitions_for_export() -> list:
    return [
        {
            "kpi_id": k["id"], "indicator_name": k["indicator_name"], "hierarchy_path": k["hierarchy_path"],
            "description": k["description"], "calculation_type": k["calculation_type"],
            "unit_of_measure": k["unit_of_measure"], "visible": int(bool(k["visible"])),
            "formula_string": k.get("formula_string"),
        }
        for k in get_all_kpis_detailed()
    ]


def get_all_annual_targets_enriched() -> list:
    """One row per annual target value (KPI x plant x year x target number) with names."""
    with db.connect(db.TARGETS, attach={"plants_db": db.PLANTS, "kpis_db": db.KPIS}) as conn:
        return db.rows(conn.execute("""
            SELECT t.id AS annual_target_id, t.year, t.plant_id, p.name AS plant_name, t.kpi_id,
                   i.name AS indicator_name, v.target_number, v.target_value, v.is_manual, v.is_formula_based
            FROM annual_targets t
            JOIN kpi_annual_target_values v ON v.annual_target_id = t.id
            LEFT JOIN plants_db.plants p ON t.plant_id = p.id
            LEFT JOIN kpis_db.kpis s ON t.kpi_id = s.id
            LEFT JOIN kpis_db.kpi_indicators i ON s.indicator_id = i.id
            WHERE i.id IS NULL OR i.is_active = 1
            ORDER BY t.year, p.name, i.name, v.target_number
        """))


def get_lean_targets() -> list:
    """Minimal, BI-friendly rows: Indicator, Plant, Year, PeriodType, PeriodValue, TargetID, Value."""
    plants = {p["id"]: p["name"] for p in get_all_plants()}
    kpis = {k["id"]: k["indicator_name"] for k in get_all_kpis_detailed()}
    return [
        {
            "Indicator": kpis[row["kpi_id"]],
            "Plant": plants.get(row["plant_id"], f"ID:{row['plant_id']}"),
            "Year": row["year"],
            "PeriodType": row["period_type"],
            "PeriodValue": row["period_value"],
            "TargetID": row["target_number"],
            "Value": row["target_value"],
        }
        for row in get_all_periodic_targets_unified()
        if row["kpi_id"] in kpis  # skip soft-deleted KPIs
    ]


# --- Actuals & performance status ---

def get_actual_measurements(kpi_id: int, plant_id: int, start_date: str = None, end_date: str = None) -> list:
    from src.services import actuals_service
    return actuals_service.get_actual_measurements(kpi_id, plant_id, start_date, end_date)


def get_kpi_performance_status(kpi_id: int, plant_id: int, target_value: float = None, target_number: int = 1) -> dict:
    """Latest actual vs target_value, or (if None) the stored target `target_number` for that day.

    Raises LookupError when no target is passed and none is stored.
    """
    from src.services import actuals_service
    kpi_spec = get_kpi_detailed_by_id(kpi_id)
    if not kpi_spec:
        return {"error": f"KPI Spec with ID {kpi_id} not found"}
    return actuals_service.get_performance_status_for_kpi(
        kpi_id=kpi_id,
        plant_id=plant_id,
        target_value=target_value,
        direction=kpi_spec.get("direction") or "Higher is Better",
        threshold_json=kpi_spec.get("threshold_json"),
        time_filter_type=kpi_spec.get("time_filter_type") or "None",
        time_filter_value=kpi_spec.get("time_filter_value"),
        calc_type=kpi_spec.get("calculation_type"),
        target_number=target_number,
    )


def get_modern_kpi_targets(kpi_id: int = None, plant_id: int = None) -> list:
    """Rows of the legacy flat kpi_targets table (not used by repartition)."""
    query, params = "SELECT * FROM kpi_targets WHERE 1=1", []
    if kpi_id is not None:
        query += " AND kpi_id = ?"
        params.append(kpi_id)
    if plant_id is not None:
        query += " AND plant_id = ?"
        params.append(plant_id)
    with db.connect(db.TARGETS) as conn:
        return db.rows(conn.execute(query, params))


def parse_json_field(value, default):
    """json.loads that tolerates None/''/invalid JSON (nullable TEXT columns)."""
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
