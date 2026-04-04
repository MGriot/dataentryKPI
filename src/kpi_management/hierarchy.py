# src/kpi_management/hierarchy.py
import sqlite3
import traceback
from src.config import settings as app_config
from pathlib import Path

def add_node(name: str, parent_id: int = None, node_type: str = 'folder') -> int:
    """Adds a new node to the recursive hierarchy."""
    db_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_path) as conn:
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO kpi_nodes (name, parent_id, node_type) VALUES (?, ?, ?)", (name, parent_id, node_type))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"ERROR (add_node): {e}")
            raise

def update_node(node_id: int, name: str = None, parent_id = -999):
    """Updates node properties. Use parent_id=None for root."""
    db_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_path) as conn:
        try:
            if name:
                conn.execute("UPDATE kpi_nodes SET name = ? WHERE id = ?", (name, node_id))
            if parent_id != -999:
                conn.execute("UPDATE kpi_nodes SET parent_id = ? WHERE id = ?", (parent_id, node_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR (update_node): {e}")
            raise

def delete_node(node_id: int):
    """Deletes a node and all its children (recursive due to FK ON DELETE CASCADE)."""
    db_path = app_config.get_database_path("db_kpis.db")
    with sqlite3.connect(db_path) as conn:
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("DELETE FROM kpi_nodes WHERE id = ?", (node_id,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"ERROR (delete_node): {e}")
            raise
