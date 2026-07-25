# tests/test_data_access_upgrade.py
import sqlite3
import pytest
from pathlib import Path
from src.config import settings as app_config
from src.data_access import setup

def test_database_setup(tmp_path, monkeypatch):
    monkeypatch.setitem(app_config.SETTINGS, "database_base_dir", str(tmp_path))
    setup.setup_databases()

    # Check db_kpis.db tables and columns
    db_kpis = app_config.get_database_path("db_kpis.db")
    assert db_kpis.exists()
    with sqlite3.connect(db_kpis) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(kpis)")
        cols = {row[1] for row in cursor.fetchall()}
        assert "owner" in cols
        assert "direction" in cols
        assert "threshold_json" in cols
        assert "target_granularity" in cols
        assert "target_count" in cols
        assert "time_filter_type" in cols
        assert "time_filter_value" in cols

    # Check db_kpi_actuals.db
    db_actuals = app_config.get_database_path("db_kpi_actuals.db")
    assert db_actuals.exists()
    with sqlite3.connect(db_actuals) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='actual_measurements'")
        assert cursor.fetchone() is not None

    # Check db_kpi_history.db
    db_history = app_config.get_database_path("db_kpi_history.db")
    assert db_history.exists()
    with sqlite3.connect(db_history) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kpi_definition_history'")
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='target_value_history'")
        assert cursor.fetchone() is not None

    # Check db_kpi_targets.db for kpi_targets
    db_targets = app_config.get_database_path("db_kpi_targets.db")
    assert db_targets.exists()
    with sqlite3.connect(db_targets) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='kpi_targets'")
        assert cursor.fetchone() is not None
