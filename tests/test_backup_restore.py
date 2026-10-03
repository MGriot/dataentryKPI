import io
import zipfile

from tests.helpers import periodic, save_targets


def test_backup_round_trip_preserves_nulls_ids_and_values(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["units"]: 1200})
    child = client.post("/kpis/nodes", json={"name": "Child", "parent_id": seeded["node"]}, headers=admin).json()["node_id"]

    backup = client.get("/export/all", headers=admin)
    assert backup.status_code == 200
    with zipfile.ZipFile(io.BytesIO(backup.content)) as zf:
        names = set(zf.namelist())
        assert {"manifest.json", "raw_units_of_measure.csv", "raw_target_value_history.csv"} <= names
        assert not any("users" in n or "sessions" in n or "api_keys" in n for n in names)
        assert "\\N" in zf.read("raw_kpi_nodes.csv").decode()  # root folder's NULL parent

    # change things after the backup, then restore
    client.post("/kpis/nodes", json={"name": "After backup"}, headers=admin)
    save_targets(client, admin, 2026, p1, {seeded["units"]: 9999})

    res = client.post("/import/restore", files={"file": ("kpi_backup.zip", backup.content, "application/zip")}, headers=admin)
    assert res.status_code == 200, res.text
    assert res.json()["snapshot"]

    tree = client.get("/kpis/tree", headers=admin).json()
    assert [n["name"] for n in tree] == ["Ops"]  # root visible again, post-backup folder gone
    assert tree[0]["children"][0]["id"] == child
    months = periodic(client, admin, seeded["units"], p1, 2026, "Month")
    assert round(sum(m["target_value"] for m in months)) == 1200
    # restored KPI ids still line up with their targets
    entry = client.get("/targets/annual-entry", params={"year": 2026, "plant_id": p1, "kpi_id": seeded["units"]}, headers=admin).json()
    assert entry["target_values"][0]["target_value"] == 1200


def test_restore_validation(client, admin):
    def upload(content: bytes):
        return client.post("/import/restore", files={"file": ("b.zip", content, "application/zip")}, headers=admin)

    assert upload(b"not a zip").status_code == 400

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.csv", "x")
    assert upload(buf.getvalue()).status_code == 400

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("raw_plants.csv", "id,name,unknown_column\n1,A,x\n")
    res = upload(buf.getvalue())
    assert res.status_code == 400 and "unknown_column" in res.json()["detail"]


def test_restore_accepts_legacy_backup_with_empty_strings(client, admin):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("raw_plants.csv", "id,name,description,visible,color\n7,Legacy,,1,#000000\n")
        zf.writestr("raw_kpi_nodes.csv", "id,name,parent_id,node_type\n3,Root,,folder\n")
    res = client.post("/import/restore", files={"file": ("old.zip", buf.getvalue(), "application/zip")}, headers=admin)
    assert res.status_code == 200, res.text
    assert [n["name"] for n in client.get("/kpis/tree", headers=admin).json()] == ["Root"]
    assert client.get("/plants", headers=admin).json()[0]["id"] == 7
