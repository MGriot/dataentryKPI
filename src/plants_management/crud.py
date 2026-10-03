# src/plants_management/crud.py
"""Plant (facility) CRUD."""
import re
from typing import Optional

from src.data_access import db

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class PlantNotFoundError(LookupError):
    pass


def _validate(name: str, color: str):
    if not (name or "").strip():
        raise ValueError("Plant name cannot be empty.")
    if not _HEX_COLOR.match(color or ""):
        raise ValueError("Color must be a hex value like #3b82f6.")


def add_plant(name: str, description: str = "", visible: bool = True, color: str = "#3b82f6") -> int:
    _validate(name, color)
    with db.connect(db.PLANTS) as conn:
        try:
            return conn.execute(
                "INSERT INTO plants (name, description, visible, color) VALUES (?, ?, ?, ?)",
                (name.strip(), description or "", 1 if visible else 0, color),
            ).lastrowid
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError(f"A plant named '{name}' already exists.") from e
            raise


def update_plant(plant_id: int, name: str, description: str, visible: bool, color: str):
    _validate(name, color)
    with db.connect(db.PLANTS) as conn:
        try:
            cur = conn.execute(
                "UPDATE plants SET name=?, description=?, visible=?, color=? WHERE id=?",
                (name.strip(), description or "", 1 if visible else 0, color, plant_id),
            )
        except Exception as e:
            if "UNIQUE" in str(e):
                raise ValueError(f"The name '{name}' is already used by another plant.") from e
            raise
        if cur.rowcount == 0:
            raise PlantNotFoundError(f"Plant {plant_id} not found.")


def get_plant_by_id(plant_id: int) -> Optional[dict]:
    with db.connect(db.PLANTS) as conn:
        row = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,)).fetchone()
        return dict(row) if row else None


def is_plant_referenced(plant_id: int) -> bool:
    """True if any target, periodic target or actual references the plant."""
    checks = [(db.TARGETS, "annual_targets"), (db.TARGETS, "kpi_targets"), (db.ACTUALS, "actual_measurements")]
    checks += [(db_name, table) for db_name, table, _ in db.PERIOD_TABLES.values()]
    for db_name, table in checks:
        with db.connect(db_name) as conn:
            if conn.execute(f"SELECT 1 FROM {table} WHERE plant_id = ? LIMIT 1", (plant_id,)).fetchone():
                return True
    return False


def delete_plant(plant_id: int, force_delete_if_referenced: bool = False):
    """Deletes a plant. Refuses (ValueError) if it has data unless forced; forcing deletes that data too."""
    if not get_plant_by_id(plant_id):
        raise PlantNotFoundError(f"Plant {plant_id} not found.")
    if not force_delete_if_referenced and is_plant_referenced(plant_id):
        raise ValueError(f"Plant {plant_id} has targets or actuals; delete with force=true to remove them too.")
    attach = {
        "tgt": db.TARGETS, "act": db.ACTUALS, "kp": db.KPIS,
        **{db.PERIOD_ALIASES[pt]: db.PERIOD_TABLES[pt][0] for pt in db.PERIOD_TABLES},
    }
    with db.connect(db.PLANTS, attach=attach) as conn:
        conn.execute("DELETE FROM tgt.annual_targets WHERE plant_id = ?", (plant_id,))  # values cascade
        conn.execute("DELETE FROM tgt.kpi_targets WHERE plant_id = ?", (plant_id,))
        conn.execute("DELETE FROM act.actual_measurements WHERE plant_id = ?", (plant_id,))
        conn.execute("DELETE FROM kp.kpi_plant_visibility WHERE plant_id = ?", (plant_id,))
        for pt, (_, table, _) in db.PERIOD_TABLES.items():
            conn.execute(f"DELETE FROM {db.PERIOD_ALIASES[pt]}.{table} WHERE plant_id = ?", (plant_id,))
        conn.execute("DELETE FROM plants WHERE id = ?", (plant_id,))
