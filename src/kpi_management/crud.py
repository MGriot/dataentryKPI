# src/kpi_management/crud.py
"""KPI hierarchy (folders), indicators/specs, units of measure."""
import json
from typing import Any, Dict, List, Optional

from src.config.constants import DISTRIBUTION_PROFILES, normalize_calc_type
from src.data_access import db
from src.services import history_service

DIRECTIONS = ("Higher is Better", "Lower is Better", "Range")
TIME_FILTER_TYPES = ("None", "Rolling")

# Spec fields that change what the engine computes -> trigger a recalculation when edited.
_CALC_FIELDS = {"formula_string", "formula_json", "calculation_type", "target_count", "default_distribution_profile"}


# --- Units of measure ---

def get_all_units_of_measure() -> List[Dict[str, Any]]:
    with db.connect(db.KPIS) as conn:
        return db.rows(conn.execute("SELECT id, name FROM units_of_measure ORDER BY name"))


def add_unit_of_measure(name: str) -> Dict[str, Any]:
    """Adds a unit to the registry, or returns the existing one."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Unit of measure name cannot be empty.")
    with db.connect(db.KPIS) as conn:
        conn.execute("INSERT OR IGNORE INTO units_of_measure (name) VALUES (?)", (name,))
        row = conn.execute("SELECT id, name FROM units_of_measure WHERE name = ?", (name,)).fetchone()
        return dict(row)


# --- Hierarchy ---

def get_kpi_tree(root_id: Optional[int] = None, depth: Optional[int] = None) -> List[Dict[str, Any]]:
    """Folder tree (active nodes) with their active indicators; optionally rooted at root_id / cut at depth."""
    with db.connect(db.KPIS) as conn:
        nodes = db.rows(conn.execute("SELECT * FROM kpi_nodes WHERE is_active = 1 ORDER BY name"))
        indicators = db.rows(conn.execute("""
            SELECT i.id AS indicator_id, i.name AS indicator_name, i.node_id,
                   k.id AS kpi_id, k.description, k.calculation_type, k.unit_of_measure, k.visible,
                   k.formula_json, k.formula_string, k.is_calculated, k.default_distribution_profile,
                   k.owner, k.direction, k.threshold_json, k.target_granularity, k.target_count,
                   k.time_filter_type, k.time_filter_value, k.target_labels
            FROM kpi_indicators i LEFT JOIN kpis k ON k.indicator_id = i.id
            WHERE i.is_active = 1 ORDER BY i.name
        """))

    by_node: Dict[int, list] = {}
    for ind in indicators:
        by_node.setdefault(ind["node_id"], []).append(ind)
    nodes_by_id = {n["id"]: dict(n, children=[], indicators=by_node.get(n["id"], [])) for n in nodes}

    def creates_cycle(node_id: int, parent_id: int) -> bool:
        seen, current = {node_id}, parent_id
        while current is not None:
            if current in seen:
                return True
            seen.add(current)
            current = nodes_by_id.get(current, {}).get("parent_id")
        return False

    roots = []
    for nid, node in nodes_by_id.items():
        parent_id = node.get("parent_id")
        if parent_id and parent_id in nodes_by_id and not creates_cycle(nid, parent_id):
            nodes_by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)

    if root_id is not None:
        roots = [nodes_by_id[root_id]] if root_id in nodes_by_id else []

    def prune(node, level):
        if depth is not None and level >= depth:
            node["children"] = []
        for child in node["children"]:
            prune(child, level + 1)
        return node

    return [prune(r, 1) for r in roots]


def add_kpi_node(parent_id: Optional[int], name: str, custom_level_label: Optional[str] = None) -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("Folder name cannot be empty.")
    with db.connect(db.KPIS) as conn:
        if parent_id is not None and not conn.execute(
            "SELECT 1 FROM kpi_nodes WHERE id = ? AND is_active = 1", (parent_id,)
        ).fetchone():
            raise ValueError(f"Parent folder {parent_id} not found.")
        # UNIQUE(name, parent_id) doesn't catch duplicates at the root (NULL != NULL in SQL).
        if conn.execute(
            "SELECT 1 FROM kpi_nodes WHERE name = ? AND parent_id IS ? AND is_active = 1", (name, parent_id)
        ).fetchone():
            raise ValueError(f"A folder named '{name}' already exists here.")
        return conn.execute(
            "INSERT INTO kpi_nodes (name, parent_id, node_type, custom_level_label, is_active) VALUES (?, ?, 'folder', ?, 1)",
            (name, parent_id, custom_level_label),
        ).lastrowid


# --- Indicators / specs ---

def _validate_spec_values(values: Dict[str, Any]) -> Dict[str, Any]:
    """Normalizes/validates spec fields; raises ValueError on bad input."""
    out = dict(values)
    if "calculation_type" in out:
        out["calculation_type"] = normalize_calc_type(out["calculation_type"])
    if "target_count" in out:
        try:
            count = int(out["target_count"])
        except (TypeError, ValueError):
            raise ValueError("target_count must be an integer.") from None
        if not 1 <= count <= 10:
            raise ValueError("target_count must be between 1 and 10.")
        out["target_count"] = count
    if out.get("direction") is not None and out["direction"] not in DIRECTIONS:
        raise ValueError(f"direction must be one of: {', '.join(DIRECTIONS)}.")
    if out.get("time_filter_type") is not None:
        canonical = {t.lower(): t for t in TIME_FILTER_TYPES}.get(str(out["time_filter_type"]).strip().lower())
        if canonical is None:
            raise ValueError(f"time_filter_type must be one of: {', '.join(TIME_FILTER_TYPES)}.")
        out["time_filter_type"] = canonical
    if out.get("default_distribution_profile") and out["default_distribution_profile"] not in DISTRIBUTION_PROFILES:
        raise ValueError("Unknown default_distribution_profile.")
    for json_field in ("threshold_json", "target_labels", "formula_json"):
        value = out.get(json_field)
        if isinstance(value, (dict, list)):
            out[json_field] = json.dumps(value)
        elif value not in (None, ""):
            try:
                json.loads(value)
            except (TypeError, ValueError):
                raise ValueError(f"{json_field} must be valid JSON.") from None
    if "visible" in out:
        out["visible"] = 1 if out["visible"] else 0
    return out


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
    changed_by: Optional[str] = "system",
) -> Dict[str, Any]:
    """Creates an indicator + its spec in one transaction (with an audit entry)."""
    name = (name or "").strip()
    if not name:
        raise ValueError("KPI name cannot be empty.")
    spec = _validate_spec_values({
        "calculation_type": calculation_type, "target_count": target_count, "direction": direction,
        "time_filter_type": time_filter_type, "threshold_json": threshold_json, "visible": visible,
    })
    with db.connect(db.KPIS, attach={"hist": db.HISTORY}) as conn:
        if not conn.execute("SELECT 1 FROM kpi_nodes WHERE id = ? AND is_active = 1", (node_id,)).fetchone():
            raise ValueError(f"Folder {node_id} not found.")
        if conn.execute(
            "SELECT 1 FROM kpi_indicators WHERE name = ? AND node_id = ? AND is_active = 1", (name, node_id)
        ).fetchone():
            raise ValueError(f"A KPI named '{name}' already exists in this folder.")
        # A soft-deleted KPI with the same name would collide on UNIQUE(name, node_id): free the name.
        conn.execute(
            "UPDATE kpi_indicators SET name = name || ' (deleted #' || id || ')' WHERE name = ? AND node_id = ? AND is_active = 0",
            (name, node_id),
        )
        indicator_id = conn.execute(
            "INSERT INTO kpi_indicators (name, node_id, is_active) VALUES (?, ?, 1)", (name, node_id)
        ).lastrowid
        kpi_id = conn.execute(
            """INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible,
                                 owner, direction, threshold_json, target_granularity, target_count,
                                 time_filter_type, time_filter_value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (indicator_id, description, spec["calculation_type"], unit_of_measure, spec["visible"], owner,
             spec["direction"], spec["threshold_json"], target_granularity, spec["target_count"],
             spec["time_filter_type"], time_filter_value),
        ).lastrowid
        history_service.record_definition_change(
            kpi_id, "CREATE", None,
            {"name": name, "node_id": node_id, "description": description, "calculation_type": spec["calculation_type"],
             "unit_of_measure": unit_of_measure, "owner": owner, "direction": spec["direction"],
             "target_granularity": target_granularity, "target_count": spec["target_count"]},
            changed_by, conn=conn, schema="hist",
        )
    return {"indicator_id": indicator_id, "kpi_id": kpi_id, "name": name}


UPDATABLE_SPEC_FIELDS = (
    "description", "calculation_type", "unit_of_measure", "visible", "formula_json", "formula_string",
    "default_distribution_profile", "owner", "direction", "threshold_json", "target_granularity",
    "target_count", "time_filter_type", "time_filter_value", "target_labels",
)


def update_kpi_spec_extended(kpi_id: int, data_updates: Dict[str, Any], changed_by: Optional[str] = "system") -> bool:
    """Updates a KPI's spec fields (audited). Returns False if the KPI doesn't exist or nothing valid was sent.

    Raises ValueError (incl. FormulaError) on invalid values. `is_calculated` is derived from
    the formula (set iff formula_string/formula_json is non-empty) and can't be set directly.
    Formula/calc-type/target-count changes recalculate the KPI's stored targets.
    """
    from src.target_management import annual

    updates = {k: v for k, v in (data_updates or {}).items() if k in UPDATABLE_SPEC_FIELDS}
    if not updates:
        return False
    updates = _validate_spec_values(updates)
    if "formula_string" in updates:
        updates["formula_string"] = (updates["formula_string"] or "").strip() or None
        annual.validate_formula(kpi_id, updates["formula_string"])

    with db.connect(db.KPIS, attach={"hist": db.HISTORY}) as conn:
        row = conn.execute(
            "SELECT k.* FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id WHERE k.id = ? AND i.is_active = 1",
            (kpi_id,),
        ).fetchone()
        if not row:
            return False
        old_state = dict(row)
        formula_string = updates.get("formula_string", old_state.get("formula_string"))
        formula_json = updates.get("formula_json", old_state.get("formula_json"))
        updates["is_calculated"] = 1 if (formula_string or (formula_json or "").strip()) else 0

        sets = ", ".join(f"{db.ident(k)} = ?" for k in updates)
        conn.execute(f"UPDATE kpis SET {sets} WHERE id = ?", (*updates.values(), kpi_id))
        new_state = dict(conn.execute("SELECT * FROM kpis WHERE id = ?", (kpi_id,)).fetchone())
        history_service.record_definition_change(kpi_id, "UPDATE", old_state, new_state, changed_by, conn=conn, schema="hist")

    if any(old_state.get(f) != new_state.get(f) for f in _CALC_FIELDS | {"is_calculated"}):
        annual.recalculate_kpis([kpi_id], changed_by=changed_by)
    return True


def soft_delete_kpi(kpi_id: int, changed_by: Optional[str] = "system") -> bool:
    """Hides a KPI everywhere (is_active = 0) while keeping its targets, actuals and history."""
    with db.connect(db.KPIS, attach={"hist": db.HISTORY}) as conn:
        row = conn.execute(
            "SELECT i.id FROM kpis k JOIN kpi_indicators i ON k.indicator_id = i.id WHERE k.id = ? AND i.is_active = 1",
            (kpi_id,),
        ).fetchone()
        if not row:
            return False
        conn.execute("UPDATE kpi_indicators SET is_active = 0 WHERE id = ?", (row["id"],))
        history_service.record_definition_change(
            kpi_id, "SOFT_DELETE", {"is_active": 1}, {"is_active": 0}, changed_by, conn=conn, schema="hist"
        )
    return True


def hard_delete_indicator(indicator_id: int, changed_by: Optional[str] = "system") -> bool:
    """Permanently deletes an indicator, its spec, and all its targets/actuals/split links (one transaction)."""
    attach = {
        "tgt": db.TARGETS, "act": db.ACTUALS, "tpl": db.TEMPLATES, "hist": db.HISTORY,
        **{db.PERIOD_ALIASES[pt]: db.PERIOD_TABLES[pt][0] for pt in db.PERIOD_TABLES},
    }
    with db.connect(db.KPIS, attach=attach) as conn:
        ind = conn.execute("SELECT id FROM kpi_indicators WHERE id = ?", (indicator_id,)).fetchone()
        if not ind:
            return False
        spec = conn.execute("SELECT id FROM kpis WHERE indicator_id = ?", (indicator_id,)).fetchone()
        if spec:
            kpi_id = spec["id"]
            conn.execute("DELETE FROM tgt.annual_targets WHERE kpi_id = ?", (kpi_id,))  # values cascade
            conn.execute("DELETE FROM tgt.kpi_targets WHERE kpi_id = ?", (kpi_id,))
            for pt, (_, table, _) in db.PERIOD_TABLES.items():
                conn.execute(f"DELETE FROM {db.PERIOD_ALIASES[pt]}.{table} WHERE kpi_id = ?", (kpi_id,))
            conn.execute("DELETE FROM act.actual_measurements WHERE kpi_id = ?", (kpi_id,))
            history_service.record_definition_change(kpi_id, "HARD_DELETE", None, None, changed_by, conn=conn, schema="hist")
        conn.execute("DELETE FROM tpl.global_split_indicators WHERE indicator_id = ?", (indicator_id,))
        conn.execute("DELETE FROM kpi_indicators WHERE id = ?", (indicator_id,))  # spec + visibility cascade
    return True


def update_target_value(
    plant_id: int,
    kpi_id: int,
    target_number: int,
    period_start: str,
    period_end: str,
    target_value: float,
    changed_by: Optional[str] = "system",
) -> bool:
    """Legacy flat kpi_targets table (explicit start/end). Not used by repartition or the UI."""
    with db.connect(db.TARGETS, attach={"hist": db.HISTORY}) as conn:
        existing = conn.execute(
            "SELECT target_value FROM kpi_targets WHERE kpi_id = ? AND plant_id = ? AND target_number = ? AND period_start = ?",
            (kpi_id, plant_id, target_number, period_start),
        ).fetchone()
        conn.execute(
            """INSERT INTO kpi_targets (kpi_id, plant_id, target_number, period_start, period_end, target_value)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(kpi_id, plant_id, target_number, period_start) DO UPDATE SET
               period_end = excluded.period_end, target_value = excluded.target_value""",
            (kpi_id, plant_id, target_number, period_start, period_end, target_value),
        )
        history_service.record_target_change(
            kpi_id, plant_id, target_number, period_start, period_end,
            existing["target_value"] if existing else None, target_value, changed_by, conn=conn, schema="hist",
        )
    return True
