"""Shared fixtures: every test that touches data gets its own throwaway database directory."""
import pytest

from src.config import settings as app_config
from tests.helpers import auth as _auth


@pytest.fixture
def db_dir(tmp_path, monkeypatch):
    """Points all databases at tmp_path and creates the schema."""
    from src.data_access import setup

    monkeypatch.setenv("KPI_DB_DIR", str(tmp_path))
    monkeypatch.setenv("KPI_EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setitem(app_config.SETTINGS, "database_base_dir", str(tmp_path))
    monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)
    setup.setup_databases()
    return tmp_path


@pytest.fixture
def client(db_dir):
    from fastapi.testclient import TestClient

    from src import api

    api.login_limiter._failures.clear()
    with TestClient(api.app) as c:
        yield c


@pytest.fixture
def admin(client):
    """Headers for the first (admin) account."""
    res = client.post("/auth/register", json={"name": "admin", "password": "admin-password"})
    assert res.status_code == 200, res.text
    return _auth(res.json()["token"])


@pytest.fixture
def user(client, admin):
    """Headers for a regular account created by the admin."""
    assert client.post("/users", json={"name": "alice", "password": "alice-password"}, headers=admin).status_code == 200
    res = client.post("/auth/login", json={"name": "alice", "password": "alice-password"})
    assert res.status_code == 200, res.text
    return _auth(res.json()["token"])


@pytest.fixture
def seeded(client, admin):
    """Two plants, a folder and Sum / Average KPIs. Returns ids."""
    p1 = client.post("/plants", json={"name": "North"}, headers=admin).json()["plant_id"]
    p2 = client.post("/plants", json={"name": "South"}, headers=admin).json()["plant_id"]
    node = client.post("/kpis/nodes", json={"name": "Ops"}, headers=admin).json()["node_id"]

    def kpi(name, calc="Sum", **extra):
        res = client.post("/kpis", json={"node_id": node, "name": name, "calculation_type": calc, **extra}, headers=admin)
        assert res.status_code == 200, res.text
        return res.json()["kpi_id"]

    return {
        "plants": (p1, p2),
        "node": node,
        "units": kpi("Units"),
        "hours": kpi("Hours"),
        "oee": kpi("OEE", "Average"),
        "kpi": kpi,
    }

