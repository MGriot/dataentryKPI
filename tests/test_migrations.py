"""setup_databases() must upgrade databases created by older versions without losing data."""
import sqlite3

import pytest

from src.config import settings as app_config


@pytest.fixture
def legacy_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KPI_DB_DIR", str(tmp_path))
    monkeypatch.setitem(app_config.SETTINGS, "database_base_dir", str(tmp_path))

    kpis = sqlite3.connect(tmp_path / "db_kpis.db")
    kpis.executescript("""
        CREATE TABLE kpi_nodes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, parent_id INTEGER,
            node_type TEXT, FOREIGN KEY (parent_id) REFERENCES kpi_nodes(id) ON DELETE CASCADE, UNIQUE (name, parent_id));
        CREATE TABLE kpi_indicators (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, node_id INTEGER NOT NULL,
            subgroup_id INTEGER, is_active BOOLEAN NOT NULL DEFAULT 1, UNIQUE (name, node_id));
        -- v1 shape: restrictive CHECK + FK left pointing at a table that a botched migration dropped
        CREATE TABLE kpis (id INTEGER PRIMARY KEY AUTOINCREMENT, indicator_id INTEGER NOT NULL, description TEXT,
            calculation_type TEXT NOT NULL CHECK(calculation_type IN ('Incremental', 'Average')),
            unit_of_measure TEXT, visible BOOLEAN NOT NULL DEFAULT 1,
            FOREIGN KEY (indicator_id) REFERENCES "kpi_indicators_old"(id) ON DELETE CASCADE, UNIQUE (indicator_id));
        CREATE TABLE kpi_plant_visibility (kpi_id INTEGER NOT NULL, plant_id INTEGER NOT NULL, is_enabled BOOLEAN NOT NULL DEFAULT 1,
            PRIMARY KEY (kpi_id, plant_id), FOREIGN KEY (kpi_id) REFERENCES kpis(id) ON DELETE CASCADE,
            FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE);
        INSERT INTO kpi_nodes (id, name) VALUES (1, 'Legacy');
        INSERT INTO kpi_indicators (id, name, node_id) VALUES (1, 'Old KPI', 1);
        INSERT INTO kpis (id, indicator_id, calculation_type) VALUES (1, 1, 'Incremental');
        INSERT INTO kpi_plant_visibility VALUES (1, 1, 0);
    """)
    kpis.close()

    targets = sqlite3.connect(tmp_path / "db_kpi_targets.db")
    targets.executescript("""
        CREATE TABLE annual_targets (id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, plant_id INTEGER NOT NULL,
            kpi_id INTEGER NOT NULL, annual_target1 REAL, annual_target2 REAL, is_target1_manual BOOLEAN DEFAULT 1,
            is_target2_manual BOOLEAN DEFAULT 1, target1_is_formula_based BOOLEAN DEFAULT 0, target2_is_formula_based BOOLEAN DEFAULT 0,
            target1_formula TEXT, target2_formula TEXT, target1_formula_inputs TEXT, target2_formula_inputs TEXT,
            repartition_logic TEXT NOT NULL DEFAULT 'Year', repartition_values TEXT NOT NULL DEFAULT '{}',
            distribution_profile TEXT NOT NULL DEFAULT 'annual_progressive', profile_params TEXT, global_split_id INTEGER,
            FOREIGN KEY (global_split_id) REFERENCES global_kpi_splits(id), UNIQUE(year, plant_id, kpi_id));
        INSERT INTO annual_targets (id, year, plant_id, kpi_id, annual_target1) VALUES (1, 2025, 1, 1, 500);
    """)
    targets.close()

    days = sqlite3.connect(tmp_path / "db_kpi_days.db")
    days.executescript("""
        CREATE TABLE daily_targets (id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, plant_id INTEGER NOT NULL,
            kpi_id INTEGER NOT NULL, target_number INTEGER NOT NULL, date_value, target_value REAL NOT NULL,
            UNIQUE(year, plant_id, kpi_id, target_number, date_value));
        INSERT INTO daily_targets (year, plant_id, kpi_id, target_number, date_value, target_value) VALUES (2025, 1, 1, 1, '2025-01-01', 1.5);
    """)
    days.close()

    users = sqlite3.connect(tmp_path / "db_users.db")
    users.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, email TEXT,
            color TEXT NOT NULL DEFAULT '#3b82f6', password_hash TEXT, password_salt TEXT,
            is_active BOOLEAN NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        INSERT INTO users (name, created_at) VALUES ('first', '2025-01-01'), ('second', '2025-01-02');
    """)
    users.close()
    return tmp_path


def _sql(path, table):
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[0]


def test_legacy_schema_is_upgraded_in_place(legacy_dir):
    from src import data_retriever
    from src.data_access.setup import setup_databases
    from src.kpi_management import crud as kpi_crud

    setup_databases()
    setup_databases()  # idempotent

    assert "CHECK" not in _sql(legacy_dir / "db_kpis.db", "kpis")
    assert "kpi_indicators_old" not in _sql(legacy_dir / "db_kpis.db", "kpis")
    assert "plants" not in _sql(legacy_dir / "db_kpis.db", "kpi_plant_visibility").split("REFERENCES kpis")[0]
    assert "global_kpi_splits" not in _sql(legacy_dir / "db_kpi_targets.db", "annual_targets")
    assert "date_value TEXT NOT NULL" in _sql(legacy_dir / "db_kpi_days.db", "daily_targets")

    kpi = data_retriever.get_kpi_detailed_by_id(1)
    assert kpi["calculation_type"] == "Sum" and kpi["indicator_name"] == "Old KPI"
    entry = data_retriever.get_annual_target_entry(2025, 1, 1)
    assert entry["target_values"][0]["target_value"] == 500
    assert data_retriever.get_daily_targets_for_kpi(2025, 1, 1, 1)[0]["target_value"] == 1.5
    assert data_retriever.get_all_kpis_detailed(plant_id=1) == []  # visibility override survived

    # creating KPIs works again (failed on the CHECK / dangling FK before)
    node = kpi_crud.add_kpi_node(None, "New")
    assert kpi_crud.create_kpi_indicator(node, "Fresh", calculation_type="Count")["kpi_id"] > 1

    from src.user_management import crud as user_crud
    flags = {u["name"]: u["is_admin"] for u in user_crud.get_all_users()}
    assert flags == {"first": True, "second": False}


def test_presets_are_seeded_once(db_dir):
    from src.data_access.setup import setup_databases
    from src.kpi_management import splits

    presets = [s for s in splits.get_all_global_splits() if s["name"].startswith("Preset:")]
    assert len(presets) == 5
    splits.delete_global_split(presets[0]["id"])
    setup_databases()
    assert len([s for s in splits.get_all_global_splits() if s["name"].startswith("Preset:")]) == 4
