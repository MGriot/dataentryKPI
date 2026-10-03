import calendar

import pytest

from tests.helpers import periodic, save_targets


def test_save_repartitions_sum_and_average(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["units"]: 120_000, seeded["oee"]: 85})

    months = periodic(client, admin, seeded["units"], p1, 2026, "Month")
    assert [m["period"] for m in months] == [calendar.month_name[i] for i in range(1, 13)]  # chronological
    assert sum(m["target_value"] for m in months) == pytest.approx(120_000)
    # default split is even (by day), not a progressive ramp
    assert months[0]["target_value"] == pytest.approx(120_000 * 31 / 365)

    days = periodic(client, admin, seeded["oee"], p1, 2026, "Day")
    assert len(days) == 365 and all(d["target_value"] == pytest.approx(85) for d in days)


def test_blank_values_keep_stored_values(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["units"]: 1000})
    save_targets(client, admin, 2026, p1, {seeded["units"]: {1: None}})
    entry = client.get("/targets/annual-entry", params={"year": 2026, "plant_id": p1, "kpi_id": seeded["units"]}, headers=admin).json()
    assert entry["target_values"][0]["target_value"] == 1000


def test_broadcast_to_several_plants(client, admin, seeded):
    p1, p2 = seeded["plants"]
    res = client.post("/targets/annual", json={"year": 2026, "plant_id": [p1, p2], "targets_data_map": {
        str(seeded["units"]): {"targets": [{"target_number": 1, "target_value": 500}]}}}, headers=admin)
    assert res.status_code == 200
    rows = client.get(f"/kpis/{seeded['units']}/periodic-targets/all-plants", params={"period_type": "Year", "year": 2026}, headers=admin).json()
    assert {r["plant_name"] for r in rows} == {"North", "South"}


def test_formula_kpi_is_computed_per_target_number(client, admin, seeded):
    p1, _ = seeded["plants"]
    units, hours = seeded["units"], seeded["hours"]
    for kid in (units, hours):
        assert client.put(f"/kpis/{kid}", json={"data_updates": {"target_count": 2}}, headers=admin).status_code == 200
    uph = seeded["kpi"]("UPH", "Average", target_count=2)
    assert client.put(f"/kpis/{uph}", json={"data_updates": {"formula_string": f"[{units}] / [{hours}]"}}, headers=admin).status_code == 200
    assert client.get(f"/kpis/{uph}", headers=admin).json()["is_calculated"] is True

    save_targets(client, admin, 2026, p1, {units: {1: 120_000, 2: 150_000}, hours: {1: 8000, 2: 7500}})
    entry = client.get("/targets/annual-entry", params={"year": 2026, "plant_id": p1, "kpi_id": uph}, headers=admin).json()
    values = {tv["target_number"]: tv["target_value"] for tv in entry["target_values"]}
    assert values == {1: pytest.approx(15.0), 2: pytest.approx(20.0)}
    assert all(tv["is_formula_based"] for tv in entry["target_values"])

    t2_months = periodic(client, admin, uph, p1, 2026, "Month", target_number=2)
    assert sum(m["target_value"] for m in t2_months) / 12 == pytest.approx(20.0, rel=0.01)

    # manual entry for a calculated KPI is refused; so are per-target formulas
    save_targets(client, admin, 2026, p1, {uph: 5}, status=400)
    res = client.post("/targets/annual", json={"year": 2026, "plant_id": p1, "targets_data_map": {
        str(units): {"targets": [{"target_number": 1, "is_formula_based": True, "formula": "1"}]}}}, headers=admin)
    assert res.status_code == 400


def test_formula_validation(client, admin, seeded):
    units = seeded["units"]
    bad = [
        ("().__class__", "not allowed"),
        ("[999] * 2", "unknown KPI"),
        (f"[{units}] + 1", "itself"),
    ]
    for formula, fragment in bad:
        res = client.put(f"/kpis/{units}", json={"data_updates": {"formula_string": formula}}, headers=admin)
        assert res.status_code == 400 and fragment in res.json()["detail"], res.text
    other = seeded["kpi"]("Other")
    assert client.put(f"/kpis/{other}", json={"data_updates": {"formula_string": f"[{units}]"}}, headers=admin).status_code == 200
    res = client.put(f"/kpis/{units}", json={"data_updates": {"formula_string": f"[{other}] * 2"}}, headers=admin)
    assert res.status_code == 400 and "cycle" in res.json()["detail"]


def test_split_assignment_recalculates_existing_targets(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["units"]: 1200})
    split = client.post("/global-splits", json={
        "name": "Q4 heavy", "repartition_logic": "Quarter", "repartition_values": {"Q1": 10, "Q2": 10, "Q3": 10, "Q4": 70},
        "distribution_profile": "even_distribution", "years": [2026]}, headers=admin).json()["split_id"]
    assert client.put(f"/kpis/{seeded['units']}/global-split", json={"global_split_id": split}, headers=admin).status_code == 200
    quarters = {q["period"]: q["target_value"] for q in periodic(client, admin, seeded["units"], p1, 2026, "Quarter")}
    assert quarters["Q4"] == pytest.approx(840)

    # editing the template's weights recalculates too
    client.put(f"/global-splits/{split}", json={"repartition_values": {"Q1": 25, "Q2": 25, "Q3": 25, "Q4": 25}}, headers=admin)
    quarters = {q["period"]: q["target_value"] for q in periodic(client, admin, seeded["units"], p1, 2026, "Quarter")}
    assert quarters["Q4"] == pytest.approx(300)

    # a split restricted to 2026 doesn't apply to 2027 (-> even)
    save_targets(client, admin, 2027, p1, {seeded["units"]: 365})
    assert periodic(client, admin, seeded["units"], p1, 2027, "Day")[0]["target_value"] == pytest.approx(1.0)

    # deleting the split reverts to even
    client.delete(f"/global-splits/{split}", headers=admin)
    quarters = {q["period"]: q["target_value"] for q in periodic(client, admin, seeded["units"], p1, 2026, "Quarter")}
    assert quarters["Q1"] == pytest.approx(1200 * 90 / 365)


def test_split_validation(client, admin):
    base = {"name": "x", "repartition_logic": "Month", "distribution_profile": "even_distribution"}
    assert client.post("/global-splits", json=base | {"repartition_logic": "Day"}, headers=admin).status_code == 400
    assert client.post("/global-splits", json=base | {"distribution_profile": "nope"}, headers=admin).status_code == 400
    assert client.post("/global-splits", json=base | {"repartition_values": {"January": -5}}, headers=admin).status_code == 400
    assert client.put("/global-splits/9999", json={"name": "y"}, headers=admin).status_code == 404


def test_soft_delete_hides_kpi_everywhere(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["units"]: 100})
    assert client.delete(f"/kpis/{seeded['units']}", headers=admin).status_code == 200
    assert seeded["units"] not in [k["id"] for k in client.get("/kpis", headers=admin).json()]
    assert client.get(f"/kpis/{seeded['units']}", headers=admin).status_code == 404
    assert all(r["Indicator"] != "Units" for r in client.get("/targets/lean", headers=admin).json())
    # the name can be reused
    assert client.post("/kpis", json={"node_id": seeded["node"], "name": "Units"}, headers=admin).status_code == 200


def test_input_validation(client, admin, seeded):
    p1, _ = seeded["plants"]
    assert client.get(f"/kpis/{seeded['units']}/periodic-targets", params={"plant_id": p1, "year": 2026, "period_type": "Bogus"}, headers=admin).status_code == 400
    save_targets(client, admin, 2026, 9999, {seeded["units"]: 1}, status=400)
    save_targets(client, admin, 2026, p1, {12345: 1}, status=400)
    save_targets(client, admin, 2026, p1, {seeded["units"]: {2: 1}}, status=400)  # target_count is 1
    assert client.post("/plants", json={"name": "Bad", "color": "red"}, headers=admin).status_code == 422
    assert client.post("/kpis", json={"node_id": seeded["node"], "name": "X", "calculation_type": "Median"}, headers=admin).status_code == 400
    assert client.put(f"/kpis/{seeded['units']}", json={"data_updates": {"is_calculated": 1}}, headers=admin).status_code == 400


def test_plant_delete_requires_force_when_referenced(client, admin, seeded):
    p1, p2 = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["units"]: 100})
    assert client.delete(f"/plants/{p1}", headers=admin).status_code == 409
    assert client.delete(f"/plants/{p1}?force=true", headers=admin).status_code == 200
    assert client.get(f"/kpis/{seeded['units']}/periodic-targets", params={"plant_id": p1, "year": 2026, "period_type": "Day"}, headers=admin).json() == []
    assert client.delete(f"/plants/{p2}", headers=admin).status_code == 200
    assert client.delete("/plants/9999", headers=admin).status_code == 404


def test_exports(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["units"]: 100})
    for key in ["Plants", "KPI Hierarchy", "KPI Definitions", "Plant Visibility", "Annual Targets", "Periodic Targets"]:
        res = client.get(f"/export/csv/{key}", headers=admin)
        assert res.status_code == 200 and res.text.splitlines()[0], key
    assert "Units" in client.get("/export/csv/Annual Targets", headers=admin).text
    assert client.get("/export/csv/Nope", headers=admin).status_code == 400
    assert client.get("/export/lean", headers=admin).text.startswith("Indicator,Plant")
