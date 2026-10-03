# src/plants_management/crud.py
import sqlite3
import traceback
from pathlib import Path

from src.config.settings import get_database_path

# --- Configuration Imports ---
DB_PLANTS = get_database_path('db_plants.db')
DB_TARGETS = get_database_path('db_kpi_targets.db')


# --- Helper to check DB path ---
def _validate_db_path(db_path_obj, db_name_str):
    """Validates if the provided DB path object is usable."""
    if not db_path_obj.exists():
        raise ConnectionError(f"Database file for {db_name_str} not found at {db_path_obj}")


# --- Plant CRUD Operations ---


def add_plant(name: str, description: str = "", visible: bool = True, color: str = "#000000") -> int:
    """Adds a new plant to the database."""
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    with sqlite3.connect(DB_PLANTS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO plants (name, description, visible, color) VALUES (?,?,?,?)",
                (name, description, 1 if visible else 0, color),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise Exception(f"A plant with name '{name}' already exists.") from e
        except Exception as e_general:
            raise Exception(
                "Database error while adding the plant."
            ) from e_general


def update_plant(
    plant_id: int, name: str, description: str, visible: bool, color: str
):
    """Updates an existing plant's details."""
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    with sqlite3.connect(DB_PLANTS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plants SET name=?, description=?, visible=?, color=? WHERE id=?",
                (name, description, 1 if visible else 0, color, plant_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No plant found with ID {plant_id}. Update had no effect."
                )
        except sqlite3.IntegrityError as e:
            raise Exception(
                f"The name '{name}' is already used by another plant."
            ) from e
        except Exception as e_general:
            raise Exception(
                "Database error while updating the plant."
            ) from e_general


def update_plant_color(plant_id: int, color: str):
    """Updates the color of an existing plant."""
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    with sqlite3.connect(DB_PLANTS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plants SET color=? WHERE id=?",
                (color, plant_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No plant found with ID {plant_id}. Color update had no effect."
                )
        except Exception as e_general:
            raise Exception(
                "Database error while updating the plant color."
            ) from e_general


def is_plant_referenced(plant_id: int) -> bool:
    """Checks if a plant is referenced in the annual_targets table."""
    _validate_db_path(DB_TARGETS, "DB_TARGETS")
    try:
        with sqlite3.connect(DB_TARGETS) as conn_targets:
            cursor = conn_targets.cursor()
            cursor.execute(
                "SELECT 1 FROM annual_targets WHERE plant_id = ? LIMIT 1",
                (plant_id,),
            )
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        print(
            f"ERROR: Database error while checking references for plant ID {plant_id}: {e}"
        )
        return True  # Assume referenced to be safe on error

def get_plant_by_id(plant_id: int) -> dict | None:
    """Retrieves a single plant by its ID."""
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    with sqlite3.connect(DB_PLANTS) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, visible, color FROM plants WHERE id = ?", (plant_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def delete_plant(plant_id: int, force_delete_if_referenced: bool = False):
    """
    Deletes a plant. By default, deletion is prevented if referenced in targets.
    """
    _validate_db_path(DB_PLANTS, "DB_PLANTS")
    if not force_delete_if_referenced:
        if is_plant_referenced(plant_id):
            raise ValueError(
                f"Plant ID {plant_id} is referenced in targets and cannot be deleted."
            )

    with sqlite3.connect(DB_PLANTS) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM plants WHERE id = ?", (plant_id,))
            conn.commit()
            if cursor.rowcount == 0:
                print(
                    f"WARNING: No plant found with ID {plant_id} to delete."
                )
        except sqlite3.Error as e:
            raise Exception(
                "Database error while deleting the plant."
            ) from e
