# data_retriever.py
import sqlite3
import json

# from pathlib import Path # No longer needed directly for DB paths
import datetime
import calendar

# Import configurations from app_config.py
from app_config import (
    DB_KPIS,
    DB_STABILIMENTI,
    DB_TARGETS,
    DB_KPI_DAYS,
    DB_KPI_WEEKS,
    DB_KPI_MONTHS,
    DB_KPI_QUARTERS,
    DB_KPI_TEMPLATES,
    # CSV_EXPORT_BASE_PATH is not typically used by data_retriever directly
)


# --- Dimension Table Access Functions ---


# --- KPI Groups ---
def get_kpi_groups():
    """Fetches all KPI groups, ordered by name."""
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM kpi_groups ORDER BY name").fetchall()


# --- KPI Indicator Templates & Definitions ---
def get_kpi_indicator_templates():
    """Fetches all KPI indicator templates, ordered by name."""
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM kpi_indicator_templates ORDER BY name"
        ).fetchall()


def get_kpi_indicator_template_by_id(template_id):
    """Fetches a specific KPI indicator template by its ID."""
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM kpi_indicator_templates WHERE id = ?", (template_id,)
        ).fetchone()


def get_template_defined_indicators(template_id):
    """Fetches all indicators defined within a specific template, ordered by name."""
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM template_defined_indicators WHERE template_id = ? ORDER BY indicator_name_in_template",
            (template_id,),
        ).fetchall()


def get_template_indicator_definition_by_name(template_id, indicator_name):
    """Fetches a specific indicator definition within a template by its name."""
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM template_defined_indicators WHERE template_id = ? AND indicator_name_in_template = ?",
            (template_id, indicator_name),
        ).fetchone()


def get_template_indicator_definition_by_id(definition_id):
    """Fetches a specific indicator definition by its ID."""
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM template_defined_indicators WHERE id = ?", (definition_id,)
        ).fetchone()


# --- KPI Subgroups ---
def get_kpi_subgroups_by_group_revised(group_id):
    """
    Fetches all KPI subgroups for a given group ID, including the name of their linked template.
    """
    subgroups = []
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        subgroups_raw = conn_kpis.execute(
            "SELECT * FROM kpi_subgroups WHERE group_id = ? ORDER BY name", (group_id,)
        ).fetchall()

    templates_info = {}  # Cache template names for efficiency if called multiple times
    with sqlite3.connect(DB_KPI_TEMPLATES) as conn_templates:
        conn_templates.row_factory = sqlite3.Row
        all_templates = conn_templates.execute(
            "SELECT id, name FROM kpi_indicator_templates"
        ).fetchall()
        for t in all_templates:
            templates_info[t["id"]] = t["name"]

    for sg_raw in subgroups_raw:
        sg_dict = dict(sg_raw)
        sg_dict["template_name"] = templates_info.get(sg_raw["indicator_template_id"])
        subgroups.append(sg_dict)
    return subgroups


def get_kpi_subgroup_by_id_with_template_name(subgroup_id):
    """Fetches a specific KPI subgroup by ID, including its template name if linked."""
    sg_dict = None
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        sg_raw = conn_kpis.execute(
            "SELECT * FROM kpi_subgroups WHERE id = ?", (subgroup_id,)
        ).fetchone()
        if sg_raw:
            sg_dict = dict(sg_raw)
            if sg_raw["indicator_template_id"]:
                with sqlite3.connect(DB_KPI_TEMPLATES) as conn_templates:
                    conn_templates.row_factory = sqlite3.Row
                    template_info = conn_templates.execute(
                        "SELECT name FROM kpi_indicator_templates WHERE id = ?",
                        (sg_raw["indicator_template_id"],),
                    ).fetchone()
                    if template_info:
                        sg_dict["template_name"] = template_info["name"]
    return sg_dict


# --- KPI Indicators ---
def get_kpi_indicators_by_subgroup(subgroup_id):
    """Fetches all KPI indicators for a given subgroup ID, ordered by name."""
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM kpi_indicators WHERE subgroup_id = ? ORDER BY name",
            (subgroup_id,),
        ).fetchall()


# --- KPI Specifications (from `kpis` table) ---
def get_all_kpis_detailed(only_visible=False):
    """
    Fetches all KPI specifications with their full hierarchy names (group, subgroup, indicator).
    Includes kpis.id, kpis.indicator_id (actual_indicator_id), subgroup_id.
    kpis.id is the kpi_spec_id.
    """
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        query = """SELECT k.id, g.name as group_name, sg.name as subgroup_name, i.name as indicator_name,
                          k.indicator_id, i.id as actual_indicator_id,
                          k.description, k.calculation_type, k.unit_of_measure, k.visible,
                          sg.id as subgroup_id
                   FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id
                   JOIN kpi_subgroups sg ON i.subgroup_id = sg.id JOIN kpi_groups g ON sg.group_id = g.id """
        if only_visible:
            query += " WHERE k.visible = 1"
        query += " ORDER BY g.name, sg.name, i.name"
        return conn.execute(query).fetchall()


def get_kpi_detailed_by_id(kpi_spec_id):
    """
    Fetches a specific KPI specification by its ID (kpis.id), including full hierarchy and template info.
    """
    with sqlite3.connect(DB_KPIS) as conn_kpis:
        conn_kpis.row_factory = sqlite3.Row
        query = """SELECT k.id, g.name as group_name, sg.name as subgroup_name, i.name as indicator_name,
                          i.id as actual_indicator_id, k.indicator_id, k.description, k.calculation_type,
                          k.unit_of_measure, k.visible, sg.id as subgroup_id, sg.indicator_template_id
                   FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id
                   JOIN kpi_subgroups sg ON i.subgroup_id = sg.id JOIN kpi_groups g ON sg.group_id = g.id
                   WHERE k.id = ?"""
        kpi_info_row = conn_kpis.execute(query, (kpi_spec_id,)).fetchone()

        if kpi_info_row:
            kpi_dict = dict(kpi_info_row)
            if kpi_dict.get(
                "indicator_template_id"
            ):  # Check if key exists before accessing
                with sqlite3.connect(DB_KPI_TEMPLATES) as conn_templates:
                    conn_templates.row_factory = sqlite3.Row
                    template_info = conn_templates.execute(
                        "SELECT name FROM kpi_indicator_templates WHERE id = ?",
                        (kpi_dict["indicator_template_id"],),
                    ).fetchone()
                    if template_info:
                        kpi_dict["template_name"] = template_info["name"]
            return kpi_dict
    return None


# --- Stabilimenti ---
def get_all_stabilimenti(only_visible=False):
    """Fetches all stabilimenti, optionally filtering by visibility, ordered by name."""
    with sqlite3.connect(DB_STABILIMENTI) as conn:
        conn.row_factory = sqlite3.Row
        query = (
            "SELECT * FROM stabilimenti"
            + (" WHERE visible = 1" if only_visible else "")
            + " ORDER BY name"
        )
        return conn.execute(query).fetchall()


# --- Fact Table Access Functions (Targets) ---


def get_annual_target_entry(year, stabilimento_id, kpi_spec_id):
    """
    Fetches the annual target entry for a specific year, stabilimento, and KPI specification ID.
    kpi_spec_id corresponds to kpis.id.
    Includes the manual override flags.
    """
    with sqlite3.connect(DB_TARGETS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM annual_targets WHERE year=? AND stabilimento_id=? AND kpi_id=?",
            (year, stabilimento_id, kpi_spec_id),
        ).fetchone()


def get_periodic_targets_for_kpi(
    year, stabilimento_id, kpi_spec_id, period_type, target_number
):
    """
    Fetches repartited (periodic) target data for a specific KPI, year, stabilimento, period type, and target number.
    kpi_spec_id corresponds to kpis.id.
    """
    db_map = {
        "Giorno": (DB_KPI_DAYS, "daily_targets", "date_value"),
        "Settimana": (DB_KPI_WEEKS, "weekly_targets", "week_value"),
        "Mese": (DB_KPI_MONTHS, "monthly_targets", "month_value"),
        "Trimestre": (DB_KPI_QUARTERS, "quarterly_targets", "quarter_value"),
    }
    if period_type not in db_map:
        raise ValueError(f"Tipo periodo non valido: {period_type}")

    db_path, table_name, period_col_name = db_map[period_type]

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build ORDER BY clause carefully for different period types
        order_clause = f"ORDER BY {period_col_name}"  # Default for date_value (Giorno)
        if period_type == "Mese":
            # Order months chronologically
            month_order_cases = " ".join(
                [f"WHEN '{calendar.month_name[i]}' THEN {i}" for i in range(1, 13)]
            )
            order_clause = f"ORDER BY CASE {period_col_name} {month_order_cases} END"
        elif period_type == "Trimestre":
            # Order quarters Q1, Q2, Q3, Q4
            quarter_order_cases = " ".join(
                [f"WHEN 'Q{i}' THEN {i}" for i in range(1, 5)]
            )
            order_clause = f"ORDER BY CASE {period_col_name} {quarter_order_cases} END"
        elif period_type == "Settimana":
            # Order weeks by year then week number (e.g., "2023-W52" before "2024-W01")
            # Assumes week_value format is "YYYY-Www"
            order_clause = f"ORDER BY SUBSTR({period_col_name}, 1, 4), CAST(SUBSTR({period_col_name}, INSTR({period_col_name}, '-W') + 2) AS INTEGER)"

        query = (
            f"SELECT {period_col_name} AS Periodo, target_value AS Target FROM {table_name} "
            f"WHERE year=? AND stabilimento_id=? AND kpi_id=? AND target_number=? {order_clause}"
        )

        cursor.execute(query, (year, stabilimento_id, kpi_spec_id, target_number))
        return cursor.fetchall()


# --- Master/Sub KPI Link Retrieval Functions ---
def get_sub_kpis_for_master(master_kpi_spec_id):
    """Returns a list of sub_kpi_spec_id linked to a master_kpi_spec_id."""
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row  # Ensure rows can be accessed by column name
        rows = conn.execute(
            "SELECT sub_kpi_spec_id FROM kpi_master_sub_links WHERE master_kpi_spec_id = ?",
            (master_kpi_spec_id,),
        ).fetchall()
        return [row["sub_kpi_spec_id"] for row in rows]


def get_master_kpi_for_sub(sub_kpi_spec_id):
    """Returns the master_kpi_spec_id for a given sub_kpi_spec_id, or None if it's not a sub-KPI."""
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT master_kpi_spec_id FROM kpi_master_sub_links WHERE sub_kpi_spec_id = ?",
            (sub_kpi_spec_id,),
        ).fetchone()
        return row["master_kpi_spec_id"] if row else None


def get_all_master_sub_kpi_links():
    """Returns all links for display or management."""
    with sqlite3.connect(DB_KPIS) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT id, master_kpi_spec_id, sub_kpi_spec_id FROM kpi_master_sub_links"
        ).fetchall()


def get_kpi_role_details(kpi_spec_id):
    """
    Determines the role of a KPI (Master, Sub, or None) and related info.
    Returns a dict: {'role': 'master'/'sub'/'none', 'related_kpis': [ids_of_subs_if_master], 'master_id': id_if_sub}
    """
    role_details = {"role": "none", "related_kpis": [], "master_id": None}

    # Check if it's a master
    sub_kpis = get_sub_kpis_for_master(kpi_spec_id)
    if sub_kpis:
        role_details["role"] = "master"
        role_details["related_kpis"] = sub_kpis
        return role_details  # A KPI is either a master or a sub, not both directly (by design)

    # Check if it's a sub
    master_id = get_master_kpi_for_sub(kpi_spec_id)
    if master_id:
        role_details["role"] = "sub"
        role_details["master_id"] = master_id
        # Optionally, one could also fetch siblings here if needed:
        # siblings = get_sub_kpis_for_master(master_id)
        # role_details['related_kpis'] = [s_id for s_id in siblings if s_id != kpi_spec_id] # Example of siblings

    return role_details


if __name__ == "__main__":
    # Small test block for data_retriever functions
    print("Testing data_retriever.py...")

    # Assumes setup_databases() from database_manager.py has been run
    # and some data exists. Replace with actual IDs from your test data.
    test_group_id = 1  # Example
    test_template_id = 1  # Example
    test_kpi_spec_id = 1  # Example kpis.id
    test_year = datetime.datetime.now().year
    test_stabilimento_id = 1  # Example

    print("\n--- KPI Groups ---")
    groups = get_kpi_groups()
    if groups:
        print(
            f"Found {len(groups)} groups. First: {dict(groups[0]) if groups else 'None'}"
        )

    print("\n--- KPI Subgroups (for group 1) ---")
    subgroups = get_kpi_subgroups_by_group_revised(test_group_id)
    if subgroups:
        print(
            f"Found {len(subgroups)} subgroups for group {test_group_id}. First: {subgroups[0] if subgroups else 'None'}"
        )

    print("\n--- KPI Indicator Templates ---")
    templates = get_kpi_indicator_templates()
    if templates:
        print(
            f"Found {len(templates)} templates. First: {dict(templates[0]) if templates else 'None'}"
        )

    print("\n--- Template Defined Indicators (for template 1) ---")
    defined_indicators = get_template_defined_indicators(test_template_id)
    if defined_indicators:
        print(
            f"Found {len(defined_indicators)} indicators in template {test_template_id}. First: {dict(defined_indicators[0]) if defined_indicators else 'None'}"
        )

    print("\n--- All KPI Specifications (Detailed) ---")
    all_kpis = get_all_kpis_detailed(only_visible=True)
    if all_kpis:
        print(
            f"Found {len(all_kpis)} visible KPI specs. First: {dict(all_kpis[0]) if all_kpis else 'None'}"
        )

    print(f"\n--- KPI Spec Detailed by ID ({test_kpi_spec_id}) ---")
    kpi_spec = get_kpi_detailed_by_id(test_kpi_spec_id)
    if kpi_spec:
        print(dict(kpi_spec))

    print("\n--- Stabilimenti ---")
    stabilimenti = get_all_stabilimenti(only_visible=True)
    if stabilimenti:
        print(
            f"Found {len(stabilimenti)} visible stabilimenti. First: {dict(stabilimenti[0]) if stabilimenti else 'None'}"
        )

    print(
        f"\n--- Annual Target for KPI Spec ID {test_kpi_spec_id}, Year {test_year}, Stab {test_stabilimento_id} ---"
    )
    annual_target = get_annual_target_entry(
        test_year, test_stabilimento_id, test_kpi_spec_id
    )
    if annual_target:
        print(dict(annual_target))
    else:
        print("No annual target found for test IDs.")

    print(f"\n--- Monthly Targets for KPI Spec ID {test_kpi_spec_id}, Target 1 ---")
    monthly_targets = get_periodic_targets_for_kpi(
        test_year, test_stabilimento_id, test_kpi_spec_id, "Mese", 1
    )
    if monthly_targets:
        print(f"Found {len(monthly_targets)} monthly targets. First 3:")
        for mt in monthly_targets[:3]:
            print(f"  {mt['Periodo']}: {mt['Target']}")
    else:
        print("No monthly targets found for test IDs.")

    print(f"\n--- Master/Sub Links for KPI Spec ID {test_kpi_spec_id} ---")
    role_info = get_kpi_role_details(test_kpi_spec_id)
    print(f"Role for KPI {test_kpi_spec_id}: {role_info['role']}")
    if role_info["role"] == "master":
        print(f"  Manages SubKPIs: {role_info['related_kpis']}")
    elif role_info["role"] == "sub":
        print(f"  Managed by Master KPI: {role_info['master_id']}")

    print("\n--- All Master/Sub Links ---")
    all_links = get_all_master_sub_kpi_links()
    if all_links:
        print(f"Found {len(all_links)} links. First few:")
        for link in all_links[:3]:
            print(
                f"  ID: {link['id']}, Master: {link['master_kpi_spec_id']}, Sub: {link['sub_kpi_spec_id']}"
            )
    else:
        print("No master/sub links found in the database.")

    print("\nTest run finished.")
