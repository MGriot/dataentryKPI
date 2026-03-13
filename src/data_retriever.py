# src/data_retriever.py
import sqlite3
import json
import datetime
import calendar
import traceback
from pathlib import Path

from src.config import settings as app_config
from src.config.settings import get_database_path

def _handle_db_connection_error(db_name_str: str, func_name: str) -> bool:
    try:
        app_config.get_database_path(db_name_str)
        return False
    except Exception as e:
        print(f"ERROR ({func_name}): Database path error for {db_name_str}: {e}")
        return True

# --- Recursive Hierarchy Access ---

def get_hierarchy_nodes(parent_id=None) -> list:
    """Fetches hierarchy nodes (groups/subgroups/folders) for a specific parent."""
    if _handle_db_connection_error("db_kpis.db", "get_hierarchy_nodes"): return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            if parent_id is None:
                return conn.execute("SELECT * FROM kpi_nodes WHERE parent_id IS NULL ORDER BY name").fetchall()
            else:
                return conn.execute("SELECT * FROM kpi_nodes WHERE parent_id = ? ORDER BY name", (parent_id,)).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_hierarchy_nodes): {e}")
        return []

def get_indicators_by_node(node_id: int) -> list:
    """Fetches indicators directly attached to a hierarchy node."""
    if _handle_db_connection_error("db_kpis.db", "get_indicators_by_node"): return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute("SELECT * FROM kpi_indicators WHERE node_id = ? ORDER BY name", (node_id,)).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_indicators_by_node): {e}")
        return []

# --- KPI Specifications ---

def get_all_kpis_detailed(only_visible=False, plant_id: int = None) -> list:
    """
    Fetches all KPI specifications with their full flattened hierarchy.
    """
    if _handle_db_connection_error("db_kpis.db", "get_all_kpis_detailed"): return []
    
    # We use a recursive CTE to build the path for each node
    query = """
    WITH RECURSIVE hierarchy_path(id, path) AS (
        SELECT id, name FROM kpi_nodes WHERE parent_id IS NULL
        UNION ALL
        SELECT n.id, hp.path || ' > ' || n.name
        FROM kpi_nodes n JOIN hierarchy_path hp ON n.parent_id = hp.id
    )
    SELECT k.id, hp.path as full_path, i.name as indicator_name,
           k.indicator_id, i.id as actual_indicator_id,
           k.description, k.calculation_type, k.unit_of_measure, k.visible,
           k.formula_json, k.formula_string, k.is_calculated, k.default_distribution_profile,
           i.node_id
    FROM kpis k
    JOIN kpi_indicators i ON k.indicator_id = i.id
    JOIN hierarchy_path hp ON i.node_id = hp.id
    """
    
    conditions = []
    params = []

    if only_visible:
        conditions.append("k.visible = 1")
    
    if plant_id is not None:
        query += " LEFT JOIN kpi_plant_visibility ksv ON k.id = ksv.kpi_id AND ksv.plant_id = ?"
        conditions.append("(ksv.is_enabled = 1 OR (ksv.is_enabled IS NULL AND k.visible = 1))")
        params.append(plant_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY hp.path, i.name"
    
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query, params).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_all_kpis_detailed): {e}")
        return []

def get_kpi_detailed_by_id(kpi_spec_id: int):
    """Fetches a specific KPI specification by ID (kpis.id)."""
    if _handle_db_connection_error("db_kpis.db", "get_kpi_detailed_by_id"): return None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            # Simplified for now, just get basic info + path
            query = """
            WITH RECURSIVE hierarchy_path(id, path) AS (
                SELECT id, name FROM kpi_nodes WHERE parent_id IS NULL
                UNION ALL
                SELECT n.id, hp.path || ' > ' || n.name
                FROM kpi_nodes n JOIN hierarchy_path hp ON n.parent_id = hp.id
            )
            SELECT k.*, i.name as indicator_name, hp.path as full_path
            FROM kpis k
            JOIN kpi_indicators i ON k.indicator_id = i.id
            JOIN hierarchy_path hp ON i.node_id = hp.id
            WHERE k.id = ?
            """
            return conn.execute(query, (kpi_spec_id,)).fetchone()
    except sqlite3.Error as e:
        print(f"ERROR (get_kpi_detailed_by_id): {e}")
        return None

# --- Plants ---

def get_all_plants(visible_only=False) -> list:
    if _handle_db_connection_error("db_plants.db", "get_all_plants"): return []
    query = "SELECT * FROM plants"
    if visible_only: query += " WHERE visible = 1"
    query += " ORDER BY name"
    try:
        with sqlite3.connect(app_config.get_database_path("db_plants.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_all_plants): {e}")
        return []

# --- Targets ---

def get_annual_targets(plant_id, year):
    if _handle_db_connection_error("db_kpi_targets.db", "get_annual_targets"): return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute("SELECT * FROM annual_targets WHERE plant_id = ? AND year = ?", (plant_id, year)).fetchall()
    except sqlite3.Error as e: return []

def get_annual_target_entry(year: int, plant_id: int, kpi_spec_id: int):
    if _handle_db_connection_error("db_kpi_targets.db", "get_annual_target_entry"): return None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute("SELECT * FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?", (year, plant_id, kpi_spec_id)).fetchone()
    except sqlite3.Error as e: return None

def get_periodic_targets_for_kpi(year, plant_id, kpi_id, period_type, target_num):
    db_map = {"Day": ("db_kpi_days.db", "daily_targets", "date_value"),
              "Week": ("db_kpi_weeks.db", "weekly_targets", "week_value"),
              "Month": ("db_kpi_months.db", "monthly_targets", "month_value"),
              "Quarter": ("db_kpi_quarters.db", "quarterly_targets", "quarter_value")}
    if period_type not in db_map: return []
    db, tbl, col = db_map[period_type]
    try:
        with sqlite3.connect(app_config.get_database_path(db)) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(f"SELECT {col} AS Period, target_value AS Target FROM {tbl} WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=? ORDER BY {col}", (year, plant_id, kpi_id, target_num)).fetchall()
    except: return []

def get_periodic_targets_for_kpi_all_plants(kpi_id, period_type, year=None):
    db_map = {"Day": ("db_kpi_days.db", "daily_targets", "date_value"),
              "Week": ("db_kpi_weeks.db", "weekly_targets", "week_value"),
              "Month": ("db_kpi_months.db", "monthly_targets", "month_value"),
              "Quarter": ("db_kpi_quarters.db", "quarterly_targets", "quarter_value")}
    if period_type not in db_map: return []
    db, tbl, col = db_map[period_type]
    try:
        with sqlite3.connect(app_config.get_database_path(db)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(f"ATTACH DATABASE '{get_database_path('db_plants.db')}' AS pdb")
            q = f"SELECT t.*, p.name as plant_name, t.{col} as period FROM {tbl} t JOIN pdb.plants p ON t.plant_id = p.id WHERE t.kpi_id = ?"
            params = [kpi_id]
            if year: q += " AND t.year = ?"; params.append(year)
            res = conn.execute(q, params).fetchall()
            conn.execute("DETACH DATABASE pdb")
            return res
    except: return []

# --- Helpers ---
def get_kpi_indicator_templates():
    with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_indicator_templates ORDER BY name").fetchall()

def get_template_defined_indicators(template_id):
    with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM template_defined_indicators WHERE template_id = ?", (template_id,)).fetchall()

def get_linked_sub_kpis_detailed(master_id):
    # This needs path-CTE logic if we want full path, for now simple:
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT k.*, i.name as indicator_name, l.distribution_weight FROM kpi_master_sub_links l JOIN kpis k ON l.sub_kpi_spec_id = k.id JOIN kpi_indicators i ON k.indicator_id = i.id WHERE l.master_kpi_spec_id = ?", (master_id,)).fetchall()

def get_kpi_role_details(kpi_id):
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        is_m = conn.execute("SELECT 1 FROM kpi_master_sub_links WHERE master_kpi_spec_id = ?", (kpi_id,)).fetchone()
        m_id = conn.execute("SELECT master_kpi_spec_id FROM kpi_master_sub_links WHERE sub_kpi_spec_id = ?", (kpi_id,)).fetchone()
        return {"role": "master" if is_m else ("sub" if m_id else "none"), "master_id": m_id[0] if m_id else None}

def get_distinct_years():
    with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT DISTINCT year FROM annual_targets ORDER BY year DESC").fetchall()
