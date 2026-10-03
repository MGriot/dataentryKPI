# src/kpi_management/specs.py
import sqlite3
import traceback
from src.config import settings as app_config
from pathlib import Path # Ensure Path is imported

from src.config.settings import CALC_TYPE_INCREMENTAL, CALC_TYPE_AVERAGE

# --- KPI Specification (kpis table) CRUD Operations ---


def add_kpi_spec(
    indicator_id: int,
    description: str,
    calculation_type: str,
    unit_of_measure: str,
    visible: bool,
    formula_json: str = None,
    formula_string: str = None,
    is_calculated: bool = False,
    default_distribution_profile: str = None,
) -> int:
    """
    Adds a new KPI specification (a record in the 'kpis' table).
    If a spec for the given indicator_id already exists, it attempts to update it.
    """
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    if not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError(
            f"DB_KPIS is not properly configured ({db_kpis_path}). Cannot add KPI spec."
        )

    allowed_calc_types = [CALC_TYPE_INCREMENTAL, CALC_TYPE_AVERAGE]
    if calculation_type not in allowed_calc_types:
        msg = f"Invalid calculation_type: '{calculation_type}'. Must be one of {allowed_calc_types}."
        print(f"ERROR: {msg}")
        raise ValueError(msg)

    with sqlite3.connect(db_kpis_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO kpis (indicator_id, description, calculation_type, unit_of_measure, visible, formula_json, formula_string, is_calculated, default_distribution_profile)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    indicator_id,
                    description,
                    calculation_type,
                    unit_of_measure,
                    1 if visible else 0,
                    formula_json,
                    formula_string,
                    1 if is_calculated else 0,
                    default_distribution_profile,
                ),
            )
            conn.commit()
            kpi_spec_id = cursor.lastrowid
            return kpi_spec_id
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: kpis.indicator_id" in str(e):
                # Spec for this indicator_id already exists, attempt to update it.
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM kpis WHERE indicator_id=?", (indicator_id,))
                existing_kpi_row = cursor.fetchone()
                if existing_kpi_row:
                    existing_kpi_spec_id = existing_kpi_row[0]
                    cursor.execute(
                        """UPDATE kpis SET description=?, calculation_type=?,
                           unit_of_measure=?, visible=?, formula_json=?, formula_string=?, is_calculated=?, default_distribution_profile=? WHERE id=?""",
                        (
                            description,
                            calculation_type,
                            unit_of_measure,
                            1 if visible else 0,
                            formula_json,
                            formula_string,
                            1 if is_calculated else 0,
                            default_distribution_profile,
                            existing_kpi_spec_id,
                        ),
                    )
                    conn.commit()
                    return existing_kpi_spec_id
                raise
            raise

def update_kpi_spec(
    kpi_spec_id: int,
    indicator_id: int = None,
    description: str = None,
    calculation_type: str = None,
    unit_of_measure: str = None,
    visible: bool = None,
    formula_json: str = None,
    formula_string: str = None,
    is_calculated: bool = None,
    default_distribution_profile: str = None,
):
    """Updates an existing KPI specification. Only provided fields (not None) will be updated."""
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    
    # 1. Fetch existing record to merge
    with sqlite3.connect(db_kpis_path) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute("SELECT * FROM kpis WHERE id = ?", (kpi_spec_id,)).fetchone()
        if not existing:
            raise ValueError(f"KPI Spec with ID {kpi_spec_id} not found.")
        
        data = dict(existing)
        
        # 2. Update with provided values
        if indicator_id is not None: data['indicator_id'] = indicator_id
        if description is not None: data['description'] = description
        if calculation_type is not None: data['calculation_type'] = calculation_type
        if unit_of_measure is not None: data['unit_of_measure'] = unit_of_measure
        if visible is not None: data['visible'] = 1 if visible else 0
        if formula_json is not None: data['formula_json'] = formula_json
        if formula_string is not None: data['formula_string'] = formula_string
        if is_calculated is not None: data['is_calculated'] = 1 if is_calculated else 0
        if default_distribution_profile is not None: data['default_distribution_profile'] = default_distribution_profile

        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE kpis SET indicator_id=?, description=?, calculation_type=?,
                   unit_of_measure=?, visible=?, formula_json=?, formula_string=?, 
                   is_calculated=?, default_distribution_profile=? WHERE id=?""",
                (
                    data['indicator_id'],
                    data['description'],
                    data['calculation_type'],
                    data['unit_of_measure'],
                    data['visible'],
                    data['formula_json'],
                    data['formula_string'],
                    data['is_calculated'],
                    data['default_distribution_profile'],
                    kpi_spec_id,
                ),
            )
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR: Database error while updating KPI Spec {kpi_spec_id}: {e}")
            raise

def get_kpi_spec_by_indicator_id(indicator_id: int) -> dict | None:
    """Retrieves a KPI specification by its associated indicator ID."""
    db_kpis_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_kpis_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, indicator_id, description, calculation_type, unit_of_measure, visible, formula_json, formula_string, is_calculated, default_distribution_profile
                   FROM kpis WHERE indicator_id = ?""",
                (indicator_id,),
            )
            row = cursor.fetchone()
            if row:
                spec_data = dict(row)
                spec_data["visible"] = bool(spec_data["visible"])
                spec_data["is_calculated"] = bool(spec_data["is_calculated"])
                return spec_data
            return None
        except sqlite3.Error as e:
            print(f"ERROR: Database error while retrieving KPI Spec: {e}")
            raise


# Note: Deletion of a KPI Specification (kpis record) is typically handled
# by the deletion of its parent KPI Indicator (kpi_indicators record)
# through ON DELETE CASCADE, as defined in the kpis table schema:
# FOREIGN KEY (indicator_id) REFERENCES kpi_indicators(id) ON DELETE CASCADE
# Therefore, an explicit `delete_kpi_spec` function is often not needed here
# if that's the intended data lifecycle. If you need to delete a spec
# without deleting the indicator (which would break the FK if not handled carefully),
# that would be a different use case.
