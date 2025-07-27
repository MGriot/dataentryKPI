# src/data_retriever.py
import sqlite3
import json
import datetime
import calendar
import traceback
from pathlib import Path

# Import app_config for dynamic database paths
import app_config
from db_core.utils import get_database_path
from kpi_management import visibility as kpi_visibility


# --- Helper for DB Connection Errors ---
def _handle_db_connection_error(db_name_str: str, func_name: str) -> bool:
    # Get the actual Path object from app_config using the db_name_str
    # This function now expects the string name of the database file (e.g., "db_kpis.db")
    try:
        db_path_obj = get_database_path(db_name_str)
    except Exception as e:
        print(f"ERROR ({func_name}): Could not get database path for {db_name_str}: {e}")
        return True # Indicates an error state

    db_path_str = str(db_path_obj)

    if (
        db_path_str == ":memory:"
        or ":memory_" in db_path_str
        or "error_db" in db_path_str
    ):
        msg = f"ERROR ({func_name}): Database path for {db_name_str} ('{db_path_str}') is a placeholder or indicates a configuration error. Cannot retrieve data."
        print(msg)
        return True  # Indicates an error state

    return False  # No configuration error detected by this function


# --- Dimension Table Access Functions ---


# --- KPI Groups ---
def get_kpi_groups() -> list:
    """Fetches all KPI groups, ordered by name. Returns list of sqlite3.Row."""
    if _handle_db_connection_error("db_kpis.db", "get_kpi_groups"):
        return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute("SELECT * FROM kpi_groups ORDER BY name").fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_kpi_groups): Database error querying kpi_groups: {e}")
        print(traceback.format_exc())
        return []


# --- KPI Indicator Templates & Definitions ---
def get_kpi_indicator_templates() -> list:
    """Fetches all KPI indicator templates, ordered by name. Returns list of sqlite3.Row."""
    if _handle_db_connection_error("db_kpi_templates.db", "get_kpi_indicator_templates"):
        return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM kpi_indicator_templates ORDER BY name"
            ).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_kpi_indicator_templates): Database error: {e}")
        return []


def get_kpi_indicator_template_by_id(template_id: int):  # -> sqlite3.Row or None
    """Fetches a specific KPI indicator template by its ID."""
    if _handle_db_connection_error(
        "db_kpi_templates.db", "get_kpi_indicator_template_by_id"
    ):
        return None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM kpi_indicator_templates WHERE id = ?", (template_id,)
            ).fetchone()
    except sqlite3.Error as e:
        print(
            f"ERROR (get_kpi_indicator_template_by_id): Database error for ID {template_id}: {e}"
        )
        return None


def get_template_defined_indicators(template_id: int) -> list:
    """Fetches all indicators defined within a specific template, ordered by name."""
    if _handle_db_connection_error(
        "db_kpi_templates.db", "get_template_defined_indicators"
    ):
        return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM template_defined_indicators WHERE template_id = ? ORDER BY indicator_name_in_template",
                (template_id,),
            ).fetchall()
    except sqlite3.Error as e:
        print(
            f"ERROR (get_template_defined_indicators): Database error for template ID {template_id}: {e}"
        )
        return []


def get_template_indicator_definition_by_name(
    template_id: int, indicator_name: str
):  # -> sqlite3.Row or None
    """Fetches a specific indicator definition within a template by its name."""
    if _handle_db_connection_error(
        "db_kpi_templates.db", "get_template_indicator_definition_by_name"
    ):
        return None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM template_defined_indicators WHERE template_id = ? AND indicator_name_in_template = ?",
                (template_id, indicator_name),
            ).fetchone()
    except sqlite3.Error as e:
        print(
            f"ERROR (get_template_indicator_definition_by_name): Database error for template {template_id}, name {indicator_name}: {e}"
        )
        return None


def get_template_indicator_definition_by_id(
    definition_id: int,
):  # -> sqlite3.Row or None
    """Fetches a specific indicator definition by its ID."""
    if _handle_db_connection_error(
        "db_kpi_templates.db", "get_template_indicator_definition_by_id"
    ):
        return None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM template_defined_indicators WHERE id = ?",
                (definition_id,),
            ).fetchone()
    except sqlite3.Error as e:
        print(
            f"ERROR (get_template_indicator_definition_by_id): Database error for def ID {definition_id}: {e}"
        )
        return None

# --- KPI Subgroups ---
def get_kpi_subgroups_by_group_revised(group_id: int) -> list:
    """
    Fetches all KPI subgroups for a given group ID, including the name of their linked template.
    Returns a list of dictionaries.
    """
    if _handle_db_connection_error("db_kpis.db", "get_kpi_subgroups_by_group_revised_kpis") or \
       _handle_db_connection_error("db_kpi_templates.db", "get_kpi_subgroups_by_group_revised_tpl"): return []

    subgroups = []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_kpis:
            conn_kpis.row_factory = sqlite3.Row
            subgroups_raw = conn_kpis.execute(
                "SELECT * FROM kpi_subgroups WHERE group_id = ? ORDER BY name", (group_id,)
            ).fetchall()

        templates_info = {}
        with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn_templates:
            conn_templates.row_factory = sqlite3.Row
            all_templates = conn_templates.execute(
                "SELECT id, name FROM kpi_indicator_templates"
            ).fetchall()
            for t in all_templates:
                templates_info[t["id"]] = t["name"]

        for sg_raw_row in subgroups_raw:
            sg_dict = dict(sg_raw_row) # Convert sqlite3.Row to dict
            sg_dict["template_name"] = templates_info.get(sg_dict.get("indicator_template_id"))
            subgroups.append(sg_dict)
    except sqlite3.Error as e:
        print(f"ERROR (get_kpi_subgroups_by_group_revised): Database error for group ID {group_id}: {e}")
        return []
    return subgroups

def get_kpi_subgroup_by_id_with_template_name(subgroup_id: int): # -> dict or None
    """Fetches a specific KPI subgroup by ID, including its template name if linked."""
    if _handle_db_connection_error("db_kpis.db", "get_kpi_subgroup_by_id_kpis") or \
       _handle_db_connection_error("db_kpi_templates.db", "get_kpi_subgroup_by_id_tpl"): return None

    sg_dict = None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_kpis:
            conn_kpis.row_factory = sqlite3.Row
            sg_raw = conn_kpis.execute(
                "SELECT * FROM kpi_subgroups WHERE id = ?", (subgroup_id,)
            ).fetchone()
            if sg_raw:
                sg_dict = dict(sg_raw)
                if sg_dict.get("indicator_template_id"): # Use .get() for safety
                    with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn_templates:
                        conn_templates.row_factory = sqlite3.Row
                        template_info = conn_templates.execute(
                            "SELECT name FROM kpi_indicator_templates WHERE id = ?",
                            (sg_dict["indicator_template_id"],),
                        ).fetchone()
                        sg_dict["template_name"] = template_info["name"] if template_info else None
    except sqlite3.Error as e:
        print(f"ERROR (get_kpi_subgroup_by_id_with_template_name): Database error for subgroup ID {subgroup_id}: {e}")
        return None
    return sg_dict

# --- KPI Indicators ---
def get_kpi_indicators_by_subgroup(subgroup_id: int) -> list:
    """Fetches all KPI indicators for a given subgroup ID, ordered by name."""
    if _handle_db_connection_error("db_kpis.db", "get_kpi_indicators_by_subgroup"): return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM kpi_indicators WHERE subgroup_id = ? ORDER BY name",
                (subgroup_id,),
            ).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_kpi_indicators_by_subgroup): Database error for subgroup ID {subgroup_id}: {e}")
        return []

# --- KPI Specifications (from `kpis` table) ---
def get_all_kpis_detailed(only_visible=False, stabilimento_id: int = None) -> list:
    """Fetches all KPI specifications with their full hierarchy names. Returns list of sqlite3.Row. kpis.id is aliased as 'id' in the query and available."""
    if _handle_db_connection_error("db_kpis.db", "get_all_kpis_detailed"): return []
    query = """SELECT k.id, g.name as group_name, sg.name as subgroup_name, i.name as indicator_name,
                      k.indicator_id, i.id as actual_indicator_id,
                      k.description, k.calculation_type, k.unit_of_measure, k.visible,
                      sg.id as subgroup_id, sg.indicator_template_id
               FROM kpis k
               JOIN kpi_indicators i ON k.indicator_id = i.id
               JOIN kpi_subgroups sg ON i.subgroup_id = sg.id
               JOIN kpi_groups g ON sg.group_id = g.id """
    conditions = []
    params = []

    if only_visible:
        conditions.append("k.visible = 1")
    
    if stabilimento_id is not None:
        query += " LEFT JOIN kpi_stabilimento_visibility ksv ON k.id = ksv.kpi_id AND ksv.stabilimento_id = ?"
        conditions.append("(ksv.is_enabled = 1 OR (ksv.is_enabled IS NULL AND k.visible = 1))") # If no entry, assume visible
        params.append(stabilimento_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY g.name, sg.name, i.name"
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query, params).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_all_kpis_detailed): Database error: {e}")
        return []

def get_kpi_detailed_by_id(kpi_spec_id: int, stabilimento_id: int = None): # -> dict or None
    """Fetches a specific KPI specification by its ID (kpis.id), including hierarchy and template info."""
    if _handle_db_connection_error("db_kpis.db", "get_kpi_detailed_by_id_kpis") or \
       _handle_db_connection_error("db_kpi_templates.db", "get_kpi_detailed_by_id_tpl"): return None
    kpi_dict = None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_kpis:
            conn_kpis.row_factory = sqlite3.Row
            query = """SELECT k.id, g.name as group_name, sg.name as subgroup_name, i.name as indicator_name,
                              i.id as actual_indicator_id, k.indicator_id, k.description, k.calculation_type,
                              k.unit_of_measure, k.visible, sg.id as subgroup_id, sg.indicator_template_id
                       FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id
                       JOIN kpi_subgroups sg ON i.subgroup_id = sg.id JOIN kpi_groups g ON sg.group_id = g.id
                       WHERE k.id = ?"""
            params = [kpi_spec_id]

            if stabilimento_id is not None:
                query += " AND (SELECT is_enabled FROM kpi_stabilimento_visibility WHERE kpi_id = k.id AND stabilimento_id = ?) IS NOT 0"
                params.append(stabilimento_id)

            kpi_info_row = conn_kpis.execute(query, params).fetchone()

            if kpi_info_row:
                kpi_dict = dict(kpi_info_row)
                if kpi_dict.get("indicator_template_id"):
                    with sqlite3.connect(app_config.get_database_path("db_kpi_templates.db")) as conn_templates:
                        conn_templates.row_factory = sqlite3.Row
                        template_info = conn_templates.execute(
                            "SELECT name FROM kpi_indicator_templates WHERE id = ?",
                            (kpi_dict["indicator_template_id"],),
                        ).fetchone()
                        kpi_dict["template_name"] = template_info["name"] if template_info else None
    except sqlite3.Error as e:
        print(f"ERROR (get_kpi_detailed_by_id): Database error for kpi_spec_id {kpi_spec_id}: {e}")
        return None
    return kpi_dict

# --- Stabilimenti ---
def get_all_stabilimenti(visible_only=False) -> list:
    """Fetches all stabilimenti, optionally filtering by visibility, ordered by name."""
    if _handle_db_connection_error("db_stabilimenti.db", "get_all_stabilimenti"): return []
    query = "SELECT id, name, description, visible, color FROM stabilimenti"
    if visible_only:
        query += " WHERE visible = 1"
    query += " ORDER BY name"
    try:
        with sqlite3.connect(app_config.get_database_path("db_stabilimenti.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_all_stabilimenti): Database error: {e}")
        return []

# --- Fact Table Access Functions (Targets) ---

def get_linked_sub_kpis_detailed(master_kpi_spec_id: int) -> list:
    """Fetches detailed information for all Sub-KPIs linked to a Master KPI."""
    if _handle_db_connection_error("db_kpis.db", "get_linked_sub_kpis_detailed"):
        return []

    query = """
        SELECT
            k.id, g.name as group_name, sg.name as subgroup_name, i.name as indicator_name,
            k.indicator_id, i.id as actual_indicator_id,
            k.description, k.calculation_type, k.unit_of_measure, k.visible,
            sg.id as subgroup_id, sg.indicator_template_id,
            l.distribution_weight
        FROM kpi_master_sub_links l
        JOIN kpis k ON l.sub_kpi_spec_id = k.id
        JOIN kpi_indicators i ON k.indicator_id = i.id
        JOIN kpi_subgroups sg ON i.subgroup_id = sg.id
        JOIN kpi_groups g ON sg.group_id = g.id
        WHERE l.master_kpi_spec_id = ?
        ORDER BY g.name, sg.name, i.name
    """
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query, (master_kpi_spec_id,)).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_linked_sub_kpis_detailed): Database error for master ID {master_kpi_spec_id}: {e}")
        print(traceback.format_exc())
        return []

def get_annual_target_entry(year: int, stabilimento_id: int, kpi_spec_id: int): # -> sqlite3.Row or None
    """Fetches the annual target entry for a specific year, stabilimento, and KPI spec ID (kpis.id)."""
    if _handle_db_connection_error("db_kpi_targets.db", "get_annual_target_entry"): return None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM annual_targets WHERE year=? AND stabilimento_id=? AND kpi_id=?",
                (year, stabilimento_id, kpi_spec_id),
            ).fetchone()
    except sqlite3.Error as e:
        print(f"ERROR (get_annual_target_entry): Database error for Y{year},S{stabilimento_id},K{kpi_spec_id}: {e}")
        return None

def get_annual_targets(stabilimento_id, year):
    """Retrieves annual targets for a given stabilimento and year."""
    with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM annual_targets WHERE stabilimento_id = ? AND year = ?", (stabilimento_id, year)).fetchall()

def get_periodic_targets_for_kpi(
    year: int, stabilimento_id: int, kpi_spec_id: int, period_type: str, target_number: int
) -> list:
    """
    Fetches repartited (periodic) target data for a specific KPI, year, stabilimento,
    period type ('Giorno', 'Settimana', 'Mese', 'Trimestre'), and target number (1 or 2).
    """
    db_map = {
        "Giorno": ("db_kpi_days.db", "daily_targets", "date_value"),
        "Settimana": ("db_kpi_weeks.db", "weekly_targets", "week_value"),
        "Mese": ("db_kpi_months.db", "monthly_targets", "month_value"),
        "Trimestre": ("db_kpi_quarters.db", "quarterly_targets", "quarter_value"),
    }
    if period_type not in db_map:
        print(f"ERROR (get_periodic_targets_for_kpi): Invalid period_type '{period_type}'")
        raise ValueError(f"Tipo periodo non valido: {period_type}")

    db_file_name, table_name, period_col_name = db_map[period_type]
    if _handle_db_connection_error(db_file_name, f"get_periodic_targets_for_kpi_{period_type}"): return []


    order_clause = f"ORDER BY {period_col_name}"
    if period_type == "Mese":
        month_order_cases = " ".join([f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1, 13)])
        order_clause = f"ORDER BY CASE {period_col_name} {month_order_cases} END"
    elif period_type == "Trimestre":
        quarter_order_cases = " ".join([f"WHEN 'Q{i}' THEN {i}" for i in range(1, 5)])
        order_clause = f"ORDER BY CASE {period_col_name} {quarter_order_cases} END"
    elif period_type == "Settimana": # ISO Week "YYYY-Www"
        order_clause = f"ORDER BY SUBSTR({period_col_name}, 1, 4), CAST(SUBSTR({period_col_name}, INSTR({period_col_name}, '-W') + 2) AS INTEGER)"

    query = (f"SELECT {period_col_name} AS Periodo, target_value AS Target FROM {table_name} "
             f"WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=? {order_clause}")
    try:
        with sqlite3.connect(app_config.get_database_path(db_file_name)) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query, (year, stabilimento_id, kpi_spec_id, target_number)).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_periodic_targets_for_kpi {period_type}): Database error: {e}")
        return []

def get_sub_kpis_for_master(master_kpi_spec_id: int) -> list:
    """Returns a list of sub_kpi_spec_id linked to a master_kpi_spec_id."""
    if _handle_db_connection_error("db_kpis.db", "get_sub_kpis_for_master"): return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT sub_kpi_spec_id FROM kpi_master_sub_links WHERE master_kpi_spec_id = ?",
                (master_kpi_spec_id,),
            ).fetchall()
            return [row["sub_kpi_spec_id"] for row in rows]
    except sqlite3.Error as e:
        print(f"ERROR (get_sub_kpis_for_master): Database error for master ID {master_kpi_spec_id}: {e}")
        return []

def get_master_kpi_for_sub(sub_kpi_spec_id: int): # -> int or None
    """Returns the master_kpi_spec_id for a given sub_kpi_spec_id, or None."""
    if _handle_db_connection_error("db_kpis.db", "get_master_kpi_for_sub"): return None
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT master_kpi_spec_id FROM kpi_master_sub_links WHERE sub_kpi_spec_id = ?",
                (sub_kpi_spec_id,),
            ).fetchone()
            return row["master_kpi_spec_id"] if row else None
    except sqlite3.Error as e:
        print(f"ERROR (get_master_kpi_for_for_sub): Database error for sub ID {sub_kpi_spec_id}: {e}")
        return None

def get_all_master_sub_kpi_links() -> list:
    """Returns all links (id, master_kpi_spec_id, sub_kpi_spec_id, distribution_weight)."""
    if _handle_db_connection_error("db_kpis.db", "get_all_master_sub_kpi_links"): return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT id, master_kpi_spec_id, sub_kpi_spec_id, distribution_weight FROM kpi_master_sub_links ORDER BY master_kpi_spec_id, sub_kpi_spec_id"
            ).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_all_master_sub_kpi_links): Database error: {e}")
        return []

def get_kpi_role_details(kpi_spec_id: int) -> dict:
    """Determines KPI role (Master, Sub, or None) and related info."""
    role_details = {"role": "none", "related_kpis": [], "master_id": None}
    sub_kpis = get_sub_kpis_for_master(kpi_spec_id)
    if sub_kpis:
        role_details["role"] = "master"
        role_details["related_kpis"] = sub_kpis
        return role_details
    master_id = get_master_kpi_for_sub(kpi_spec_id)
    if master_id:
        role_details["role"] = "sub"
        role_details["master_id"] = master_id
    return role_details

# --- NEW Functions for Export Manager ---

def get_all_annual_target_entries_for_export() -> list:
    """Fetches all records from annual_targets for CSV export. Selects all relevant columns."""
    if _handle_db_connection_error("db_kpi_targets.db", "get_all_annual_target_entries_for_export"): return []
    query = """
        SELECT id, year, stabilimento_id, kpi_id,
               annual_target1, annual_target2,
               distribution_profile, repartition_logic,
               repartition_values, profile_params,
               is_target1_manual, is_target2_manual,
               target1_is_formula_based, target1_formula, target1_formula_inputs,
               target2_is_formula_based, target2_formula, target2_formula_inputs
        FROM annual_targets
        ORDER BY year, stabilimento_id, kpi_id;
    """
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_all_annual_target_entries_for_export): Database error: {e}")
        print(traceback.format_exc())
        return []

def get_all_periodic_targets_for_export(period_type: str) -> list:
    """Fetches all records from a specific periodic target table for CSV export."""
    period_db_map = {
        "days": ("db_kpi_days.db", "daily_targets", "date_value"),
        "weeks": ("db_kpi_weeks.db", "weekly_targets", "week_value"),
        "months": ("db_kpi_months.db", "monthly_targets", "month_value"),
        "quarters": ("db_kpi_quarters.db", "quarterly_targets", "quarter_value"),
    }
    if period_type not in period_db_map:
        print(f"ERROR (get_all_periodic_targets_for_export): Invalid period_type '{period_type}'")
        raise ValueError(f"Tipo periodo non valido per l'export: {period_type}")

    db_file_name, table_name, period_col_name = period_db_map[period_type]
    
    if _handle_db_connection_error(db_file_name, f"get_all_periodic_targets_for_export_{period_type}"): return []

    order_clause = f"ORDER BY year, stabilimento_id, kpi_id, {period_col_name}, target_number"
    if period_col_name == "month_value":
        month_order_cases = " ".join([f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1, 13)])
        order_clause = f"ORDER BY year, stabilimento_id, kpi_id, CASE {period_col_name} {month_order_cases} END, target_number"
    elif period_col_name == "quarter_value":
        quarter_order_cases = " ".join([f"WHEN 'Q{i}' THEN {i}" for i in range(1, 5)])
        order_clause = f"ORDER BY year, stabilimento_id, kpi_id, CASE {period_col_name} {quarter_order_cases} END, target_number"
    elif period_col_name == "week_value":
         order_clause = f"ORDER BY year, stabilimento_id, kpi_id, SUBSTR({period_col_name}, 1, 4), CAST(SUBSTR({period_col_name}, INSTR({period_col_name}, '-W') + 2) AS INTEGER), target_number"

    query = (f"SELECT kpi_id, stabilimento_id, year, {period_col_name}, target_number, target_value "
             f"FROM {table_name} {order_clause}")
    try:
        with sqlite3.connect(app_config.get_database_path(db_file_name)) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_all_periodic_targets_for_export - {period_type}): Database error: {e}")
        print(traceback.format_exc())
        return []


def get_distinct_years() -> list:
    """Fetches all distinct years from the annual_targets table."""
    if _handle_db_connection_error("db_kpi_targets.db", "get_distinct_years"): return []
    try:
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute("SELECT DISTINCT year FROM annual_targets ORDER BY year DESC").fetchall()
    except sqlite3.Error as e:
        print(f"ERROR (get_distinct_years): Database error: {e}")
        return []

def get_periodic_targets_for_kpi_all_stabilimenti(kpi_spec_id: int, period_type: str, year: int = None) -> list:
    """
    Fetches periodic targets for a specific KPI across all stabilimenti.
    """
    period_map = {
        'Giorno': ("db_kpi_days.db", 'daily_targets', 'date_value'),
        'Settimana': ("db_kpi_weeks.db", 'weekly_targets', 'week_value'),
        'Mese': ("db_kpi_months.db", 'monthly_targets', 'month_value'),
        'Trimestre': ("db_kpi_quarters.db", 'quarterly_targets', 'quarter_value'),
        'Anno': ("db_kpi_targets.db", 'annual_targets', 'year') # Added for annual aggregation
    }
    if period_type not in period_map:
        raise ValueError(f"Invalid period_type: {period_type}")

    db_file_name, table_name, period_col = period_map[period_type]

    if _handle_db_connection_error(db_file_name, "get_periodic_targets_for_kpi_all_stabilimenti") or \
       _handle_db_connection_error("db_stabilimenti.db", "get_periodic_targets_for_kpi_all_stabilimenti"):
        return []

    if period_type == 'Anno':
        query = """
            SELECT
                t.year,
                t.kpi_id,
                t.stabilimento_id,
                s.name as stabilimento_name,
                1 as target_number, -- Represent Target 1
                t.annual_target1 as target_value,
                t.year as period
            FROM annual_targets t
            JOIN stab_db.stabilimenti s ON t.stabilimento_id = s.id
            WHERE t.kpi_id = ?
            UNION ALL
            SELECT
                t.year,
                t.kpi_id,
                t.stabilimento_id,
                s.name as stabilimento_name,
                2 as target_number, -- Represent Target 2
                t.annual_target2 as target_value,
                t.year as period
            FROM annual_targets t
            JOIN stab_db.stabilimenti s ON t.stabilimento_id = s.id
            WHERE t.kpi_id = ?
        """
        params = [kpi_spec_id, kpi_spec_id] # kpi_spec_id for both parts of UNION ALL
        if year:
            query += " AND t.year = ? UNION ALL "
            query += query.split("UNION ALL")[1] # Repeat the second part of UNION ALL
            query += " AND t.year = ?"
            params.extend([year, year])

    else:
        query = f"""
            SELECT
                t.year,
                t.kpi_id,
                t.stabilimento_id,
                s.name as stabilimento_name,
                t.target_number,
                t.target_value,
                t.{period_col} as period
            FROM {table_name} t
            JOIN stab_db.stabilimenti s ON t.stabilimento_id = s.id
            WHERE t.kpi_id = ?
        """
        params = [kpi_spec_id]
        if year:
            query += " AND t.year = ?"
            params.append(year)

    query += f" ORDER BY t.year, s.name, period, t.target_number"

    try:
        with sqlite3.connect(app_config.get_database_path(db_file_name)) as conn:
            conn.row_factory = sqlite3.Row
            # Attach the stabilimenti database
            conn.execute(f"ATTACH DATABASE '{str(get_database_path("db_stabilimenti.db")).replace('\\', '/')}' AS stab_db")
            result = conn.execute(query, params).fetchall()
            conn.execute("DETACH DATABASE stab_db")
            return result
    except sqlite3.Error as e:
        print(f"ERROR (get_periodic_targets_for_kpi_all_stabilimenti): Database error: {e}")
        print(traceback.format_exc())
        return []

def get_dashboard_data(stabilimento_id, year):
    """Retrieves aggregated data for the dashboard."""
    # This is a placeholder. You need to implement the actual query.
    # This query should join annual_targets with aggregated actuals.
    return []


def get_periodic_data_for_kpi(kpi_id, stabilimento_id, year):
    """Retrieves periodic data for a specific KPI."""
    # This is a placeholder. You need to implement the actual query.
    # This query should join periodic targets with actuals.
    return []


if __name__ == "__main__":
    print("Testing data_retriever.py...")
    # Ensure app_config paths are correct if running standalone for tests.
    # Test calls as before...
    test_group_id = 1
    test_template_id = 1
    test_kpi_spec_id = 1
    test_year = datetime.date.today().year
    test_stabilimento_id = 1

    print("\n--- KPI Groups ---")
    groups = get_kpi_groups()
    if groups: print(f"Found {len(groups)} groups. First: {dict(groups[0]) if groups else 'None'}")

    print("\n--- KPI Subgroups (for group 1) ---")
    subgroups = get_kpi_subgroups_by_group_revised(test_group_id)
    if subgroups: print(f"Found {len(subgroups)} subgroups for group {test_group_id}. First: {subgroups[0] if subgroups else 'None'}")

    print("\n--- All KPI Specifications (Detailed) ---")
    all_kpis_detailed = get_all_kpis_detailed(only_visible=True)
    if all_kpis_detailed: print(f"Found {len(all_kpis_detailed)} visible KPI specs. First: {dict(all_kpis_detailed[0]) if all_kpis_detailed else 'None'}")

    print(f"\n--- Annual Target for KPI Spec ID {test_kpi_spec_id}, Year {test_year}, Stab {test_stabilimento_id} ---")
    annual_target = get_annual_target_entry(test_year, test_stabilimento_id, test_kpi_spec_id)
    if annual_target: print(dict(annual_target))
    else: print("No annual target found for test IDs.")

    print(f"\n--- Monthly Targets for KPI Spec ID {test_kpi_spec_id}, Target 1 ---")
    monthly_targets = get_periodic_targets_for_kpi(test_year, test_stabilimento_id, test_kpi_spec_id, "Mese", 1)
    if monthly_targets:
        print(f"Found {len(monthly_targets)} monthly targets. First 3:")
        for mt in monthly_targets[:3]: print(f"  {mt['Periodo']}: {mt['Target']}")
    else: print("No monthly targets found for Mese.")

    print("\n--- Testing new export functions (basic calls) ---")
    all_annual = get_all_annual_target_entries_for_export()
    print(f"Fetched {len(all_annual)} total annual target entries for export.")
    if all_annual: print(f"  First annual for export: {dict(all_annual[0])}")

    for p_type in ["days", "weeks", "months", "quarters"]:
        all_periodic = get_all_periodic_targets_for_export(p_type)
        print(f"Fetched {len(all_periodic)} total {p_type} target entries for export.")
        if all_periodic: print(f"  First {p_type} for export: {dict(all_periodic[0])}")

    print("\nTest run finished for data_retriever.py.")