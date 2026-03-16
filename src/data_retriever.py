# src/data_retriever.py
import sqlite3
import json
import datetime
import calendar
import traceback
from pathlib import Path

from src.config import settings as app_config
from src.config.settings import get_database_path

def _handle_db_connection_error(db_name, func_name):
    path = app_config.get_database_path(db_name)
    if not isinstance(path, Path) or not path.exists():
        print(f"ERROR ({func_name}): Database {db_name} not found at {path}")
        return True
    return False

# --- Hierarchy & Legacy ---
def get_hierarchy_nodes(parent_id=None):
    if _handle_db_connection_error("db_kpis.db", "get_hierarchy_nodes"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM kpi_nodes WHERE parent_id IS ?" if parent_id is None else "SELECT * FROM kpi_nodes WHERE parent_id = ?"
        return conn.execute(sql, (parent_id,)).fetchall()

def get_indicators_by_node(node_id):
    if _handle_db_connection_error("db_kpis.db", "get_indicators_by_node"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_indicators WHERE node_id = ?", (node_id,)).fetchall()

def get_kpi_indicators_by_subgroup(subgroup_id: int):
    """Legacy support for retrieving KPI indicators by subgroup_id."""
    return get_indicators_by_node(subgroup_id + 1000)

def get_kpi_groups():
    """Legacy support: returns groups from kpi_nodes."""
    if _handle_db_connection_error("db_kpis.db", "get_kpi_groups"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT id, name FROM kpi_nodes WHERE node_type = 'group'").fetchall()

def get_all_kpi_subgroups():
    """Legacy support: returns subgroups from kpi_nodes."""
    if _handle_db_connection_error("db_kpis.db", "get_all_kpi_subgroups"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT id, name, parent_id as group_id FROM kpi_nodes WHERE node_type = 'subgroup'").fetchall()

def get_all_kpi_indicators():
    """Returns all indicator names and IDs."""
    if _handle_db_connection_error("db_kpis.db", "get_all_kpi_indicators"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT id, name, node_id, subgroup_id FROM kpi_indicators").fetchall()

def get_all_kpis():
    """Returns all records from the kpis table."""
    if _handle_db_connection_error("db_kpis.db", "get_all_kpis"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpis").fetchall()

# --- KPI Specifications ---
def get_all_kpis_detailed(only_visible=False, plant_id: int = None) -> list:
    """Fetches all KPI specs with hierarchy names."""
    if _handle_db_connection_error("db_kpis.db", "get_all_kpis_detailed"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        
        base_query = """
            WITH RECURSIVE NodePaths AS (
                SELECT id, name, parent_id, name as path
                FROM kpi_nodes
                WHERE parent_id IS NULL
                UNION ALL
                SELECT n.id, n.name, n.parent_id, np.path || ' > ' || n.name
                FROM kpi_nodes n
                JOIN NodePaths np ON n.parent_id = np.id
            )
            SELECT
                s.id,
                i.id as indicator_id,
                i.name as indicator_name,
                i.node_id,
                np.path as hierarchy_path,
                s.*
            FROM kpis s
            JOIN kpi_indicators i ON s.indicator_id = i.id
            LEFT JOIN NodePaths np ON i.node_id = np.id
        """
        
        conditions = []
        params = []

        if only_visible:
            conditions.append("s.visible = 1")
        
        if plant_id:
            conditions.append("""
                (s.id NOT IN (SELECT kpi_id FROM kpi_plant_visibility) OR 
                 s.id IN (SELECT kpi_id FROM kpi_plant_visibility WHERE plant_id = ? AND is_enabled = 1))
            """)
            params.append(plant_id)
        
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        return conn.execute(base_query, params).fetchall()

def get_kpi_detailed_by_id(kpi_spec_id: int, plant_id: int = None):
    """Fetches a single KPI spec by its ID."""
    all_kpis = get_all_kpis_detailed(plant_id=plant_id)
    for k in all_kpis:
        if k['id'] == kpi_spec_id:
            return k
    return None

# --- Plants ---
def get_all_plants(visible_only=False):
    if _handle_db_connection_error("db_plants.db", "get_all_plants"): return []
    with sqlite3.connect(app_config.get_database_path("db_plants.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM plants" + (" WHERE visible = 1" if visible_only else "") + " ORDER BY name").fetchall()

# --- Links & Roles ---
def get_linked_sub_kpis_detailed(master_id):
    if _handle_db_connection_error("db_kpis.db", "get_linked_sub_kpis_detailed"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("""
            SELECT 
                k.id, 
                i.name as indicator_name, 
                l.distribution_weight,
                (SELECT n.path FROM (
                    WITH RECURSIVE NodePaths(id, path) AS (
                        SELECT id, name FROM kpi_nodes WHERE parent_id IS NULL
                        UNION ALL
                        SELECT n.id, np.path || ' > ' || n.name FROM kpi_nodes n JOIN NodePaths np ON n.parent_id = np.id
                    ) SELECT * FROM NodePaths
                ) n WHERE n.id = i.node_id) as hierarchy_path
            FROM kpi_master_sub_links l 
            JOIN kpis k ON l.sub_kpi_spec_id = k.id 
            JOIN kpi_indicators i ON k.indicator_id = i.id 
            WHERE l.master_kpi_spec_id = ?
        """, (master_id,)).fetchall()

def get_sub_kpis_for_master(master_kpi_spec_id: int) -> list:
    """Returns a list of sub_kpi_spec_id linked to a master_kpi_spec_id."""
    if _handle_db_connection_error("db_kpis.db", "get_sub_kpis_for_master"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT sub_kpi_spec_id FROM kpi_master_sub_links WHERE master_kpi_spec_id = ?", (master_kpi_spec_id,)).fetchall()
        return [row['sub_kpi_spec_id'] for row in rows]

def get_kpi_role_details(kpi_spec_id: int):
    """Determines if a KPI is a master, a sub, or neither."""
    is_master = False
    master_id = None
    
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        # Check if it's a master
        master_check = conn.execute("SELECT 1 FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? LIMIT 1", (kpi_spec_id,)).fetchone()
        if master_check:
            is_master = True
        
        # Check if it's a sub
        sub_check = conn.execute("SELECT master_kpi_spec_id FROM kpi_master_sub_links WHERE sub_kpi_spec_id = ? LIMIT 1", (kpi_spec_id,)).fetchone()
        if sub_check:
            master_id = sub_check['master_kpi_spec_id']

    role = "none"
    if is_master:
        role = "master"
    elif master_id is not None:
        role = "sub"
        
    return {"role": role, "master_id": master_id}

# --- Templates ---
def get_kpi_indicator_templates():
    if _handle_db_connection_error("db_kpi_templates.db", "get_kpi_indicator_templates"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_indicator_templates ORDER BY name").fetchall()

def get_template_defined_indicators(template_id):
    if _handle_db_connection_error("db_kpi_templates.db", "get_template_defined_indicators"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM template_defined_indicators WHERE template_id = ?", (template_id,)).fetchall()

# --- Targets ---
def get_annual_target_entry(year, plant_id, kpi_id):
    if _handle_db_connection_error("db_kpi_targets.db", "get_annual_target_entry"): return None
    with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?", (year, plant_id, kpi_id)).fetchone()

def get_annual_targets(plant_id, year):
    if _handle_db_connection_error("db_kpi_targets.db", "get_annual_targets"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM annual_targets WHERE plant_id=? AND year=?", (plant_id, year)).fetchall()

def get_periodic_targets_for_kpi(year, plant_id, kpi_id, period_type, target_number):
    db_map = { "Day": "days", "Week": "weeks", "Month": "months", "Quarter": "quarters" }
    col_map = { "Day": "date_value", "Week": "week_value", "Month": "month_value", "Quarter": "quarter_value" }
    
    db_name = f"db_kpi_{db_map.get(period_type)}.db"
    table_name = "daily_targets" if period_type == "Day" else f"{period_type.lower()}ly_targets"
    col_name = col_map.get(period_type, "period")
    
    if not db_name or _handle_db_connection_error(db_name, "get_periodic_targets_for_kpi"): return []
    
    with sqlite3.connect(app_config.get_database_path(db_name)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(f"SELECT {col_name} as period, target_value as Target FROM {table_name} WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=?", (year, plant_id, kpi_id, target_number)).fetchall()

def get_periodic_targets_for_kpi_all_plants(kpi_spec_id: int, period_type: str, year: int = None):
    """Fetches periodic targets for a specific KPI across all plants, including plant names."""
    db_map = { "Day": "days", "Week": "weeks", "Month": "months", "Quarter": "quarters" }
    col_map = { "Day": "date_value", "Week": "week_value", "Month": "month_value", "Quarter": "quarter_value" }
    
    db_name = f"db_kpi_{db_map.get(period_type)}.db"
    table_name = "daily_targets" if period_type == "Day" else f"{period_type.lower()}ly_targets"
    col_name = col_map.get(period_type, "period")
    
    if _handle_db_connection_error(db_name, "get_periodic_targets_for_kpi_all_plants"): return []
    
    # We need to ATTACH db_plants.db to get plant names
    plants_db_path = app_config.get_database_path("db_plants.db")
    
    query = f"""
        SELECT t.year, t.plant_id, p.name as plant_name, t.kpi_id, t.target_number, t.{col_name} as period, t.target_value 
        FROM {table_name} t
        LEFT JOIN plants p ON t.plant_id = p.id
        WHERE t.kpi_id = ?
    """
    params = [kpi_spec_id]
    if year:
        query += " AND t.year = ?"
        params.append(year)
        
    with sqlite3.connect(app_config.get_database_path(db_name)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(f"ATTACH DATABASE '{plants_db_path}' AS plants_db")
        # Adjust query to use the attached DB for plants
        query = query.replace("FROM plants p", "FROM plants_db.plants p")
        return conn.execute(query, params).fetchall()

def get_all_annual_target_entries_for_export() -> list:
    """Fetches all records from annual_targets for CSV export."""
    if _handle_db_connection_error("db_kpi_targets.db", "get_all_annual_target_entries_for_export"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM annual_targets").fetchall()

def get_all_periodic_targets_for_export(period_type: str) -> list:
    """Fetches all records from a specific periodic target table for CSV export."""
    db_map = { "days": "days", "weeks": "weeks", "months": "months", "quarters": "quarters" }
    col_map = { "days": "date_value", "weeks": "week_value", "months": "month_value", "quarters": "quarter_value" }
    
    db_name = f"db_kpi_{db_map.get(period_type)}.db"
    table_name = "daily_targets" if period_type == "days" else f"{period_type.lower()[:-1]}ly_targets"
    col_name = col_map.get(period_type)
    
    if _handle_db_connection_error(db_name, "get_all_periodic_targets_for_export"): return []
    
    with sqlite3.connect(app_config.get_database_path(db_name)) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(f"SELECT year, plant_id, kpi_id, target_number, {col_name}, target_value FROM {table_name}").fetchall()

def get_all_kpi_nodes():
    """Returns all records from the kpi_nodes table."""
    if _handle_db_connection_error("db_kpis.db", "get_all_kpi_nodes"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_nodes").fetchall()

def get_all_kpi_master_sub_links():
    """Returns all records from the kpi_master_sub_links table."""
    if _handle_db_connection_error("db_kpis.db", "get_all_kpi_master_sub_links"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_master_sub_links").fetchall()

def get_all_kpi_plant_visibility():
    """Returns all records from the kpi_plant_visibility table."""
    if _handle_db_connection_error("db_kpis.db", "get_all_kpi_plant_visibility"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_plant_visibility").fetchall()

def get_distinct_years():
    if _handle_db_connection_error("db_kpi_targets.db", "get_distinct_years"): return []
    with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT DISTINCT year FROM annual_targets ORDER BY year DESC").fetchall()
