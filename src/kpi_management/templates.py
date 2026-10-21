# src/kpi_management/templates.py
"""
KPI indicator templates: a named list of indicator definitions that can be applied to a
folder. Applying creates the template's indicators in the folder and links the folder, so
later definition changes propagate (new definitions are created, edits update the linked
indicators' specs, removed definitions soft-delete them). Deleting a template only unlinks
folders -- KPIs created from it are kept.
"""
from typing import Optional

from src.config.constants import normalize_calc_type
from src.data_access import db
from src.kpi_management import crud as kpi_crud


def add_kpi_indicator_template(name: str, description: str = "") -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("Template name cannot be empty.")
    with db.connect(db.TEMPLATES) as conn:
        try:
            return conn.execute(
                "INSERT INTO kpi_indicator_templates (name, description) VALUES (?, ?)", (name, description or "")
            ).lastrowid
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError(f"A template named '{name}' already exists.") from e
            raise


def get_template(template_id: int) -> Optional[dict]:
    with db.connect(db.TEMPLATES) as conn:
        row = conn.execute("SELECT * FROM kpi_indicator_templates WHERE id = ?", (template_id,)).fetchone()
        return dict(row) if row else None


def delete_kpi_indicator_template(template_id: int) -> bool:
    if not get_template(template_id):
        return False
    with db.connect(db.KPIS) as conn:
        conn.execute("UPDATE kpi_nodes SET indicator_template_id = NULL WHERE indicator_template_id = ?", (template_id,))
    with db.connect(db.TEMPLATES) as conn:
        conn.execute("DELETE FROM kpi_indicator_templates WHERE id = ?", (template_id,))  # definitions cascade
    return True


def _linked_node_ids(template_id: int) -> list:
    with db.connect(db.KPIS) as conn:
        return [r[0] for r in conn.execute(
            "SELECT id FROM kpi_nodes WHERE indicator_template_id = ? AND is_active = 1", (template_id,)
        )]


def _find_kpi(node_id: int, name: str) -> Optional[dict]:
    with db.connect(db.KPIS) as conn:
        row = conn.execute(
            "SELECT k.id AS kpi_id, i.id AS indicator_id FROM kpi_indicators i JOIN kpis k ON k.indicator_id = i.id "
            "WHERE i.node_id = ? AND i.name = ? AND i.is_active = 1",
            (node_id, name),
        ).fetchone()
        return dict(row) if row else None


def _apply_definition(node_id: int, definition: dict, changed_by: str, old_name: Optional[str] = None):
    name = definition["indicator_name_in_template"]
    existing = _find_kpi(node_id, old_name or name)
    spec = {
        "description": definition.get("default_description") or "",
        "calculation_type": definition.get("default_calculation_type"),
        "unit_of_measure": definition.get("default_unit_of_measure"),
        "visible": bool(definition.get("default_visible", True)),
    }
    if existing:
        if old_name and old_name != name:
            with db.connect(db.KPIS) as conn:
                conn.execute("UPDATE kpi_indicators SET name = ? WHERE id = ?", (name, existing["indicator_id"]))
        kpi_crud.update_kpi_spec_extended(existing["kpi_id"], spec, changed_by=changed_by)
    else:
        kpi_crud.create_kpi_indicator(node_id=node_id, name=name, changed_by=changed_by, **spec)


def add_indicator_definition_to_template(template_id, indicator_name_in_template, default_calculation_type,
                                         default_unit_of_measure=None, default_visible=True, default_description="",
                                         changed_by: str = "system") -> int:
    name = (indicator_name_in_template or "").strip()
    if not name:
        raise ValueError("Indicator name cannot be empty.")
    if not get_template(template_id):
        raise LookupError(f"Template {template_id} not found.")
    calc = normalize_calc_type(default_calculation_type)
    with db.connect(db.TEMPLATES) as conn:
        try:
            def_id = conn.execute(
                """INSERT INTO template_defined_indicators
                   (template_id, indicator_name_in_template, default_description, default_calculation_type,
                    default_unit_of_measure, default_visible) VALUES (?, ?, ?, ?, ?, ?)""",
                (template_id, name, default_description or "", calc, default_unit_of_measure, 1 if default_visible else 0),
            ).lastrowid
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError(f"'{name}' is already defined in this template.") from e
            raise
        definition = dict(conn.execute("SELECT * FROM template_defined_indicators WHERE id = ?", (def_id,)).fetchone())
    for node_id in _linked_node_ids(template_id):
        _apply_definition(node_id, definition, changed_by)
    return def_id


def update_indicator_definition_in_template(definition_id, template_id, name, calc_type, unit, visible, description,
                                            changed_by: str = "system") -> bool:
    name = (name or "").strip()
    if not name:
        raise ValueError("Indicator name cannot be empty.")
    calc = normalize_calc_type(calc_type)
    with db.connect(db.TEMPLATES) as conn:
        old = conn.execute(
            "SELECT * FROM template_defined_indicators WHERE id = ? AND template_id = ?", (definition_id, template_id)
        ).fetchone()
        if not old:
            return False
        conn.execute(
            """UPDATE template_defined_indicators SET indicator_name_in_template=?, default_description=?,
               default_calculation_type=?, default_unit_of_measure=?, default_visible=? WHERE id=?""",
            (name, description or "", calc, unit, 1 if visible else 0, definition_id),
        )
        definition = dict(conn.execute("SELECT * FROM template_defined_indicators WHERE id = ?", (definition_id,)).fetchone())
    for node_id in _linked_node_ids(template_id):
        _apply_definition(node_id, definition, changed_by, old_name=old["indicator_name_in_template"])
    return True


def remove_indicator_definition_from_template(definition_id, changed_by: str = "system") -> bool:
    with db.connect(db.TEMPLATES) as conn:
        row = conn.execute("SELECT * FROM template_defined_indicators WHERE id = ?", (definition_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM template_defined_indicators WHERE id = ?", (definition_id,))
    for node_id in _linked_node_ids(row["template_id"]):
        existing = _find_kpi(node_id, row["indicator_name_in_template"])
        if existing:
            kpi_crud.soft_delete_kpi(existing["kpi_id"], changed_by=changed_by)
    return True


def apply_template_to_node(template_id: int, node_id: int, changed_by: str = "system") -> int:
    """Links a folder to a template and creates/updates its indicators. Returns how many were applied."""
    if not get_template(template_id):
        raise LookupError(f"Template {template_id} not found.")
    with db.connect(db.KPIS) as conn:
        if not conn.execute("SELECT 1 FROM kpi_nodes WHERE id = ? AND is_active = 1", (node_id,)).fetchone():
            raise LookupError(f"Folder {node_id} not found.")
        conn.execute("UPDATE kpi_nodes SET indicator_template_id = ? WHERE id = ?", (template_id, node_id))
    with db.connect(db.TEMPLATES) as conn:
        definitions = db.rows(conn.execute("SELECT * FROM template_defined_indicators WHERE template_id = ?", (template_id,)))
    for definition in definitions:
        _apply_definition(node_id, definition, changed_by)
    return len(definitions)
