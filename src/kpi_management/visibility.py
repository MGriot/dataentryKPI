"""Per-plant KPI visibility overrides (a KPI is visible for a plant unless explicitly disabled)."""
from src.data_access import db


def get_plant_visibility_for_kpi(kpi_id: int) -> list:
    """Explicit overrides for a KPI: [{'plant_id', 'is_enabled'}]."""
    with db.connect(db.KPIS) as conn:
        out = db.rows(conn.execute("SELECT plant_id, is_enabled FROM kpi_plant_visibility WHERE kpi_id = ?", (kpi_id,)))
    for row in out:
        row["is_enabled"] = bool(row["is_enabled"])
    return out


def update_plant_visibility(kpi_id: int, visibility_data: list) -> bool:
    """Upserts overrides [{'plant_id', 'is_enabled'}]. Returns False if the KPI doesn't exist."""
    with db.connect(db.KPIS) as conn:
        if not conn.execute("SELECT 1 FROM kpis WHERE id = ?", (kpi_id,)).fetchone():
            return False
        conn.executemany(
            "INSERT OR REPLACE INTO kpi_plant_visibility (kpi_id, plant_id, is_enabled) VALUES (?, ?, ?)",
            [(kpi_id, int(e["plant_id"]), 1 if e["is_enabled"] else 0) for e in visibility_data],
        )
    return True
