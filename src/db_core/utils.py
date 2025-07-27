from pathlib import Path
import os

def get_database_path(db_name: str) -> Path:
    """Constructs the absolute path to the database file."""
    # Assumes the database is in the 'databases' directory, relative to the project root.
    project_root = Path(__file__).resolve().parents[2]
    db_path = project_root / "databases" / db_name
    return db_path