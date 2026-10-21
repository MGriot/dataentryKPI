"""Small helpers shared by the API tests."""


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def save_targets(client, headers, year, plant_id, values: dict, status=200):
    """values: {kpi_id: value or {target_number: value}}"""
    data = {}
    for kpi_id, v in values.items():
        per_target = v if isinstance(v, dict) else {1: v}
        data[str(kpi_id)] = {"targets": [{"target_number": tn, "target_value": val} for tn, val in per_target.items()]}
    res = client.post("/targets/annual", json={"year": year, "plant_id": plant_id, "targets_data_map": data}, headers=headers)
    assert res.status_code == status, res.text
    return res


def periodic(client, headers, kpi_id, plant_id, year, period_type, target_number=1):
    res = client.get(
        f"/kpis/{kpi_id}/periodic-targets",
        params={"plant_id": plant_id, "year": year, "period_type": period_type, "target_number": target_number},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()
