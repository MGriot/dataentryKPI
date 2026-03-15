# src/kpi_management/templates.py
import sqlite3
import traceback
from src.config import settings as app_config
from pathlib import Path

from src.config.settings import CALC_TYPE_INCREMENTAL, CALC_TYPE_AVERAGE

# --- Module Availability Flags & Mock Definitions ---
_data_retriever_available = False
_indicators_module_available = False
_specs_module_available = False

try:
    from src import data_retriever
    _data_retriever_available = True
except ImportError:
    pass

try:
    from src.kpi_management.indicators import add_kpi_indicator, delete_kpi_indicator
    _indicators_module_available = True
except ImportError:
    pass

try:
    from src.kpi_management.specs import add_kpi_spec
    _specs_module_available = True
except ImportError:
    pass


def _propagate_template_indicator_change(
    template_id: int,
    indicator_definition: dict,
    action: str, # "add_or_update" or "remove"
    specific_node_ids: list = None
):
    """
    Propagates changes from a template's indicator definition to all linked nodes.
    """
    if not _indicators_module_available or not _specs_module_available:
        print(f"ERROR (_propagate): Missing 'indicators' or 'specs' module.")
        return

    db_kpis_path = app_config.get_database_path("db_kpis.db")
    
    nodes_to_update = []
    try:
        with sqlite3.connect(db_kpis_path) as conn:
            conn.row_factory = sqlite3.Row
            if specific_node_ids:
                placeholders = ",".join("?" for _ in specific_node_ids)
                query = f"SELECT id FROM kpi_nodes WHERE indicator_template_id = ? AND id IN ({placeholders})"
                nodes_to_update = conn.execute(query, [template_id] + specific_node_ids).fetchall()
            else:
                nodes_to_update = conn.execute("SELECT id FROM kpi_nodes WHERE indicator_template_id = ?", (template_id,)).fetchall()
    except sqlite3.Error as e:
        print(f"ERROR: {e}")
        return

    with sqlite3.connect(db_kpis_path) as conn:
        conn.row_factory = sqlite3.Row
        for node_row in nodes_to_update:
            node_id = node_row["id"]
            name = indicator_definition.get("indicator_name_in_template")
            
            # Check existing
            existing_row = conn.execute("SELECT id FROM kpi_indicators WHERE name = ? AND node_id = ?", (name, node_id)).fetchone()
            existing_id = existing_row["id"] if existing_row else None
            
            if action == "add_or_update":
                ind_id = existing_id if existing_id else add_kpi_indicator(name, node_id)
                if ind_id:
                    add_kpi_spec(
                        indicator_id=ind_id,
                        description=indicator_definition.get("default_description", ""),
                        calculation_type=indicator_definition.get("default_calculation_type"),
                        unit_of_measure=indicator_definition.get("default_unit_of_measure"),
                        visible=bool(indicator_definition.get("default_visible", True))
                    )
            elif action == "remove" and existing_id:
                delete_kpi_indicator(existing_id)


def add_kpi_indicator_template(name: str, description: str = "") -> int:
    """Adds a new KPI indicator template to DB_KPI_TEMPLATES."""
    db_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO kpi_indicator_templates (name, description) VALUES (?, ?)",
                (name, description),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"ERROR: {e}")
            raise

def delete_kpi_indicator_template(template_id: int):
    """Deletes a template and unlinks from nodes."""
    db_tpl_path = app_config.get_database_path("db_kpi_templates.db")
    db_kpis_path = app_config.get_database_path("db_kpis.db")

    linked_nodes = []
    with sqlite3.connect(db_kpis_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id FROM kpi_nodes WHERE indicator_template_id = ?", (template_id,)).fetchall()
        linked_nodes = [r["id"] for r in rows]

    if linked_nodes and _data_retriever_available:
        defs = data_retriever.get_template_defined_indicators(template_id)
        for d_row in defs:
            _propagate_template_indicator_change(template_id, dict(d_row), "remove", linked_nodes)

    # Unlink
    with sqlite3.connect(db_kpis_path) as conn:
        conn.execute("UPDATE kpi_nodes SET indicator_template_id = NULL WHERE indicator_template_id = ?", (template_id,))
        conn.commit()

    # Delete Template
    with sqlite3.connect(db_tpl_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM kpi_indicator_templates WHERE id = ?", (template_id,))
        conn.commit()

def add_indicator_definition_to_template(template_id, name, calc_type, unit, visible=True, description=""):
    db_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("""INSERT INTO template_defined_indicators 
                     (template_id, indicator_name_in_template, default_description, default_calculation_type, default_unit_of_measure, default_visible)
                     VALUES (?,?,?,?,?,?)""", (template_id, name, description, calc_type, unit, 1 if visible else 0))
        conn.commit()
        def_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    _propagate_template_indicator_change(template_id, {
        "indicator_name_in_template": name,
        "default_description": description,
        "default_calculation_type": calc_type,
        "default_unit_of_measure": unit,
        "default_visible": visible
    }, "add_or_update")

def update_indicator_definition_in_template(definition_id, template_id, name, calc_type, unit, visible, description):
    db_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("""UPDATE template_defined_indicators SET
                     indicator_name_in_template=?, default_description=?, default_calculation_type=?, default_unit_of_measure=?, default_visible=?
                     WHERE id=?""", (name, description, calc_type, unit, 1 if visible else 0, definition_id))
        conn.commit()
    
    _propagate_template_indicator_change(template_id, {
        "indicator_name_in_template": name,
        "default_description": description,
        "default_calculation_type": calc_type,
        "default_unit_of_measure": unit,
        "default_visible": visible
    }, "add_or_update")

def remove_indicator_definition_from_template(definition_id):
    db_path = app_config.get_database_path("db_kpi_templates.db")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM template_defined_indicators WHERE id=?", (definition_id,)).fetchone()
        if not row: return
        data = dict(row)
        conn.execute("DELETE FROM template_defined_indicators WHERE id=?", (definition_id,))
        conn.commit()
    
    _propagate_template_indicator_change(data['template_id'], data, "remove")
