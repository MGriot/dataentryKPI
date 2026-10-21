import pytest

from src.data_access import db
from tests.helpers import save_targets

DAY = "2026-03-10"


def _actual(client, headers, kpi_id, plant_id, value, day=DAY):
    res = client.post("/actuals", json={"kpi_id": kpi_id, "plant_id": plant_id, "measurement_date": day,
                                        "actual_value": value}, headers=headers)
    assert res.status_code == 200, res.text


def _status(client, headers, kpi_id, plant_id, expect=200, **params):
    res = client.get(f"/kpis/{kpi_id}/status", params={"plant_id": plant_id, **params}, headers=headers)
    assert res.status_code == expect, res.text
    return res.json()


def test_status_compares_against_the_stored_daily_target(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["oee"]: 85, seeded["units"]: 36_500})
    _actual(client, admin, seeded["oee"], p1, 83.2)
    _actual(client, admin, seeded["units"], p1, 98)

    oee = _status(client, admin, seeded["oee"], p1)
    assert oee["target"] == pytest.approx(85) and oee["target_source"] == "daily"
    assert oee["status"] == "warning" and oee["diff_pct"] == pytest.approx(-2.12)
    units = _status(client, admin, seeded["units"], p1)  # additive: the day's share, not the annual total
    assert units["target"] == pytest.approx(100) and units["target_source"] == "daily"
    assert units["status"] == "warning"


def test_status_picks_the_target_scenario(client, admin, seeded):
    p1, _ = seeded["plants"]
    kpi = seeded["kpi"]("Yield", "Average", target_count=2)
    save_targets(client, admin, 2026, p1, {kpi: {1: 85, 2: 90}})
    _actual(client, admin, kpi, p1, 83.2)

    assert _status(client, admin, kpi, p1)["target"] == pytest.approx(85)
    stretch = _status(client, admin, kpi, p1, target_number=2)
    assert stretch["target"] == pytest.approx(90) and stretch["status"] == "out_of_range"
    _status(client, admin, kpi, p1, expect=422, target_number=0)


def test_explicit_target_value_overrides_the_stored_one(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["oee"]: 85})
    _actual(client, admin, seeded["oee"], p1, 83.2)

    res = _status(client, admin, seeded["oee"], p1, target_value=80)
    assert res["target"] == 80 and res["target_source"] == "explicit" and res["status"] == "on_track"


def test_missing_target_is_an_error_not_a_baseline(client, admin, seeded):
    p1, p2 = seeded["plants"]
    oee = seeded["oee"]
    assert _status(client, admin, oee, p1)["status"] == "no_data"  # nothing to compare yet: not an error

    _actual(client, admin, oee, p1, 83.2)
    detail = _status(client, admin, oee, p1, expect=404)["detail"]
    assert "No target 1" in detail and "target_value" in detail

    save_targets(client, admin, 2026, p1, {oee: 85})
    _status(client, admin, oee, p1, expect=404, target_number=2)
    _actual(client, admin, oee, p1, 84.0, day="2027-01-04")  # latest actual is in a year without targets
    assert "2027" in _status(client, admin, oee, p1, expect=404)["detail"]
    _actual(client, admin, oee, p2, 83.2)
    _status(client, admin, oee, p2, expect=404)  # targets are per plant


def test_level_kpis_fall_back_to_the_annual_target_additive_ones_do_not(client, admin, seeded):
    p1, _ = seeded["plants"]
    save_targets(client, admin, 2026, p1, {seeded["oee"]: 85, seeded["units"]: 36_500})
    _actual(client, admin, seeded["oee"], p1, 83.2)
    _actual(client, admin, seeded["units"], p1, 98)
    with db.connect(db.DAYS) as conn:  # e.g. data from before repartition stored daily rows
        conn.execute("DELETE FROM daily_targets")

    oee = _status(client, admin, seeded["oee"], p1)
    assert oee["target"] == 85 and oee["target_source"] == "annual"
    _status(client, admin, seeded["units"], p1, expect=404)


@pytest.mark.parametrize("direction, target, actual, expected", [
    ("Higher is Better", 85, 86, "on_track"),
    ("Higher is Better", 85, 83.2, "warning"),
    ("Higher is Better", 85, 70, "out_of_range"),
    ("Lower is Better", 2.0, 1.8, "on_track"),
    ("Lower is Better", 2.0, 2.05, "warning"),
    ("Lower is Better", 2.0, 3.0, "out_of_range"),
    ("Range", 20, 20.5, "on_track"),  # default range: target +/- 5% = [19, 21]
    ("Range", 20, 21.2, "warning"),
    ("Range", 20, 25, "out_of_range"),
])
def test_status_direction_against_the_stored_target(client, admin, seeded, direction, target, actual, expected):
    p1, _ = seeded["plants"]
    kpi = seeded["kpi"]("Metric", "Average", direction=direction)
    save_targets(client, admin, 2026, p1, {kpi: target})
    _actual(client, admin, kpi, p1, actual)

    res = _status(client, admin, kpi, p1)
    assert res["target"] == pytest.approx(target) and res["status"] == expected
