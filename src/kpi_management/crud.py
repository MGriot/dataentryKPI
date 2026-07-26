# src/kpi_management/crud.py
import sqlite3
import json
from typing import Dict, Any, List, Optional
from src.config import settings as app_config
from src.services import history_service

def _get_kpis_db() -> sqlite3.Connection:
    return sqlite3.connect(app_config.get_database_path("db_kpis.db"))

def _get_targets_db() -> sqlite3.Connection:
    return sqlite3.connect(app_config.get_database_path("db_kpi_targets.db"))

def get_all_units_of_measure() -> List[Dict[str, Any]]:
    """Retrieves the registry of defined units of measure, for KPI Explorer's UoM picker."""
    with _get_kpis_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, name FROM units_of_measure ORDER BY name").fetchall()
        return [dict(r) for r in rows]

def add_unit_of_measure(name: str) -> Dict[str, Any]:
    """Adds a new unit of measure to the registry, or returns the existing one if it already exists."""
    name = name.strip()
    if not name:
        raise ValueError("Unit of measure name cannot be empty.")
    with _get_kpis_db() as conn:
        conn.execute("INSERT OR IGNORE INTO units_of_measure (name) VALUES (?)", (name,))
        conn.commit()
        row = conn.execute("SELECT id, name FROM units_of_measure WHERE name = ?", (name,)).fetchone()
        return {"id": row[0], "name": row[1]}

def get_kpi_tree(root_id: Optional[int] = None, depth: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Constructs the KPI hierarchy tree starting from optional root_id up to max depth.
    Filters out soft-deleted (is_active = 0) nodes and indicators.
    """
    with _get_kpis_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Fetch active nodes
        if root_id is not None:
            cursor.execute(
                "SELECT * FROM kpi_nodes WHERE (id = ? OR parent_id = ?) AND is_active = 1 ORDER BY name",
                (root_id, root_id)
            )
        else:
            cursor.execute("SELECT * FROM kpi_nodes WHERE is_active = 1 ORDER BY name")
        nodes = [dict(r) for r in cursor.fetchall()]

        # Fetch active indicators and their KPI specs
        cursor.execute("""
            SELECT i.id as indicator_id, i.name as indicator_name, i.node_id, i.is_active as ind_active,
                   k.id as kpi_id, k.description, k.calculation_type, k.unit_of_measure, k.visible,
                   k.formula_json, k.formula_string, k.is_calculated, k.default_distribution_profile,
                   k.owner, k.direction, k.threshold_json, k.target_granularity, k.target_count,
                   k.time_filter_type, k.time_filter_value, k.target_labels
            FROM kpi_indicators i
            LEFT JOIN kpis k ON k.indicator_id = i.id
            WHERE i.is_active = 1
            ORDER BY i.name
        """)
        indicators = [dict(r) for r in cursor.fetchall()]

    # Group indicators by node_id
    node_indicators: Dict[int, List[Dict[str, Any]]] = {}
    for ind in indicators:
        nid = ind["node_id"]
        if nid not in node_indicators:
            node_indicators[nid] = []
        node_indicators[nid].append(ind)

    # Build recursive hierarchy
    nodes_by_id = {n["id"]: dict(n, children=[], indicators=node_indicators.get(n["id"], [])) for n in nodes}

    def creates_cycle(node_id: int, parent_id: int) -> bool:
        # Walks the ancestor chain to guard against a corrupted parent_id (self- or
        # mutually-referential) silently swallowing the node and its subtree.
        seen = {node_id}
        current: Optional[int] = parent_id
        while current is not None:
            if current in seen:
                return True
            seen.add(current)
            current = nodes_by_id.get(current, {}).get("parent_id")
        return False

    tree = []
    for nid, node in nodes_by_id.items():
        parent_id = node.get("parent_id")
        if parent_id and parent_id in nodes_by_id and not creates_cycle(nid, parent_id):
            nodes_by_id[parent_id]["children"].append(node)
        else:
            if root_id is None or nid == root_id:
                tree.append(node)

    return tree

def add_kpi_node(parent_id: Optional[int], name: str, custom_level_label: Optional[str] = None) -> int:
    """
    Creates a new hierarchy node.
    """
    with _get_kpis_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO kpi_nodes (name, parent_id, node_type, custom_level_label, is_active)
               VALUES (?, ?, 'folder', ?, 1)""",
            (name, parent_id, custom_level_label)
        )
        conn.commit()
        return cursor.lastrowid

def create_kpi_indicator(
    node_id: int,
    name: str,
    description: Optional[str] = None,
    calculation_type: str = "Sum",
    unit_of_measure: Optional[str] = None,
    visible: bool = True,
    owner: Optional[str] = None,
    direction: str = "Higher is Better",
    threshold_json: Optional[str] = None,
    target_granularity: str = "Monthly",
    target_count: int = 1,
    time_filter_type: str = "None",
    time_filter_value: Optional[str] = None,
    changed_by: Optional[str] = "system"
) -> Dict[str, Any]:
    """
    Creates an indicator and its spec record in a single transaction with audit logging.
    """
    with _get_kpis_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO kpi_indicators (name, node_id, is_active) VALUES (?, ?, 1)",
            (name, node_id)
        )
        indicator_id = cursor.lastrowid

        cursor.execute(
            """INSERT INTO kpis (
                indicator_id, description, calculation_type, unit_of_measure, visible,
                owner, direction, threshold_json, target_granularity, target_count,
                time_filter_type, time_filter_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                indicator_id, description, calculation_type, unit_of_measure, 1 if visible else 0,
                owner, direction, threshold_json, target_granularity, target_count,
                time_filter_type, time_filter_value
            )
        )
        kpi_id = cursor.lastrowid
        conn.commit()

    # Record history
    new_data = {
        "name": name, "node_id": node_id, "description": description,
        "calculation_type": calculation_type, "unit_of_measure": unit_of_measure,
        "owner": owner, "direction": direction, "target_granularity": target_granularity
    }
    history_service.record_definition_change(kpi_id, "CREATE", old_value=None, new_value=new_data, changed_by=changed_by)

    return {"indicator_id": indicator_id, "kpi_id": kpi_id, "name": name}

def update_kpi_spec_extended(
    kpi_id: int,
    data_updates: Dict[str, Any],
    changed_by: Optional[str] = "system"
) -> bool:
    """
    Updates KPI spec fields and logs old vs new state into audit history.
    """
    with _get_kpis_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM kpis WHERE id = ?", (kpi_id,))
        row = cursor.fetchone()
        if not row:
            return False

        old_state = dict(row)
        fields = []
        params = []

        allowed_fields = [
            "description", "calculation_type", "unit_of_measure", "visible",
            "formula_json", "formula_string", "is_calculated", "default_distribution_profile",
            "owner", "direction", "threshold_json", "target_granularity", "target_count",
            "time_filter_type", "time_filter_value", "target_labels"
        ]

        for k, v in data_updates.items():
            if k in allowed_fields:
                fields.append(f"{k} = ?")
                params.append(v)

        if not fields:
            return False

        params.append(kpi_id)
        sql = f"UPDATE kpis SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(sql, params)
        conn.commit()

        # Fetch new state
        cursor.execute("SELECT * FROM kpis WHERE id = ?", (kpi_id,))
        new_state = dict(cursor.fetchone())

    history_service.record_definition_change(
        kpi_id=kpi_id,
        change_type="UPDATE",
        old_value=old_state,
        new_value=new_state,
        changed_by=changed_by
    )

    return True

def soft_delete_kpi(kpi_id: int, changed_by: Optional[str] = "system") -> bool:
    """
    Soft deletes a KPI indicator (is_active = 0) and preserves all historical records.
    """
    with _get_kpis_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT indicator_id FROM kpis WHERE id = ?", (kpi_id,))
        row = cursor.fetchone()
        if not row:
            return False

        indicator_id = row[0]
        cursor.execute("UPDATE kpi_indicators SET is_active = 0 WHERE id = ?", (indicator_id,))
        conn.commit()

    history_service.record_definition_change(
        kpi_id=kpi_id,
        change_type="SOFT_DELETE",
        old_value={"is_active": 1},
        new_value={"is_active": 0},
        changed_by=changed_by
    )
    return True

def update_target_value(
    plant_id: int,
    kpi_id: int,
    target_number: int,
    period_start: str,
    period_end: str,
    target_value: float,
    changed_by: Optional[str] = "system"
) -> bool:
    """
    Creates or updates a target value in kpi_targets and records target value audit history.
    """
    with _get_targets_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT target_value FROM kpi_targets 
               WHERE kpi_id = ? AND plant_id = ? AND target_number = ? AND period_start = ?""",
            (kpi_id, plant_id, target_number, period_start)
        )
        existing_row = cursor.fetchone()
        old_val = existing_row[0] if existing_row else None

        cursor.execute(
            """INSERT INTO kpi_targets (kpi_id, plant_id, target_number, period_start, period_end, target_value)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(kpi_id, plant_id, target_number, period_start) DO UPDATE SET
               period_end = excluded.period_end, target_value = excluded.target_value""",
            (kpi_id, plant_id, target_number, period_start, period_end, target_value)
        )
        conn.commit()

    # Record target audit history
    history_service.record_target_change(
        kpi_id=kpi_id,
        plant_id=plant_id,
        target_number=target_number,
        period_start=period_start,
        period_end=period_end,
        old_value=old_val,
        new_value=target_value,
        changed_by=changed_by
    )

    return True
