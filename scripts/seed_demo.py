"""
Seeds a running Data Entry KPI backend with demo data through the REST API.

DEV/DEMO ONLY -- the credentials below are throwaway values for local testing and are
also listed in .env.example. Never point this at a real deployment.

    python scripts/seed_demo.py                       # backend on http://localhost:8000
    SEED_API_URL=http://localhost:3000/api python scripts/seed_demo.py

Creates (if missing): an admin account, a second regular account, two plants, a folder
with Sum / Average / formula KPIs, a monthly Global Split, and targets for the current year.
Only uses the standard library so it runs from any Python without installing anything.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("SEED_API_URL", "http://localhost:8000").rstrip("/")
ADMIN_NAME = os.environ.get("DEMO_ADMIN_NAME", "demo-admin")
ADMIN_PASSWORD = os.environ.get("DEMO_ADMIN_PASSWORD", "demo-admin-pass-2026")
USER_NAME = os.environ.get("DEMO_USER_NAME", "demo-user")
USER_PASSWORD = os.environ.get("DEMO_USER_PASSWORD", "demo-user-pass-2026")
YEAR = datetime.date.today().year


def call(method, path, body=None, token=None, ok_statuses=(200,)):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as e:
        payload = e.read().decode(errors="replace")
        if e.code in ok_statuses:
            return e.code, payload
        raise SystemExit(f"{method} {path} -> {e.code}: {payload}")


def login_or_register(name, password):
    status, body = call("POST", "/auth/login", {"name": name, "password": password}, ok_statuses=(200, 401))
    if status == 200:
        return body["token"], body["user"]
    status, body = call("POST", "/auth/register", {"name": name, "password": password}, ok_statuses=(200, 403, 409))
    if status != 200:
        return None, None
    return body["token"], body["user"]


def main():
    token, admin = login_or_register(ADMIN_NAME, ADMIN_PASSWORD)
    if not token:
        raise SystemExit("Could not log in or register the demo admin account.")
    print(f"Logged in as {admin['name']} (id={admin['id']})")

    # Second, regular account: created by the admin (registration may be closed).
    users = call("GET", "/users", token=token)[1]
    if not any(u["name"] == USER_NAME for u in users):
        call("POST", "/users", {"name": USER_NAME, "password": USER_PASSWORD}, token=token)
        print(f"Created user {USER_NAME}")

    plants = call("GET", "/plants", token=token)[1]
    wanted_plants = [("North Plant", "#22c55e"), ("South Plant", "#f97316")]
    for name, color in wanted_plants:
        if not any(p["name"] == name for p in plants):
            call("POST", "/plants", {"name": name, "description": "Demo plant", "visible": True, "color": color}, token=token)
    plants = call("GET", "/plants", token=token)[1]
    plant_ids = [p["id"] for p in plants if p["name"] in dict(wanted_plants)]
    print(f"Plants: {plant_ids}")

    kpis = call("GET", "/kpis", token=token)[1]
    by_name = {k["indicator_name"]: k for k in kpis}
    if "Units Produced" not in by_name:
        node_id = call("POST", "/kpis/nodes", {"parent_id": None, "name": "Demo Operations"}, token=token)[1]["node_id"]
        call("POST", "/kpis", {"node_id": node_id, "name": "Units Produced", "calculation_type": "Sum", "unit_of_measure": "pcs"}, token=token)
        call("POST", "/kpis", {"node_id": node_id, "name": "Hours Worked", "calculation_type": "Sum", "unit_of_measure": "h"}, token=token)
        call("POST", "/kpis", {"node_id": node_id, "name": "OEE", "calculation_type": "Average", "unit_of_measure": "%"}, token=token)
        call("POST", "/kpis", {"node_id": node_id, "name": "Units per Hour", "calculation_type": "Average", "unit_of_measure": "pcs/h"}, token=token)
        kpis = call("GET", "/kpis", token=token)[1]
        by_name = {k["indicator_name"]: k for k in kpis}
    units, hours, oee, uph = (by_name[n]["id"] for n in ("Units Produced", "Hours Worked", "OEE", "Units per Hour"))
    print(f"KPIs: units={units} hours={hours} oee={oee} uph={uph}")

    # Formula KPI: Units per Hour = Units Produced / Hours Worked
    call("PUT", f"/kpis/{uph}", {"data_updates": {"formula_string": f"[{units}] / [{hours}]", "is_calculated": 1}}, token=token)

    splits = call("GET", "/global-splits", token=token)[1]
    if not any(s["name"] == "Demo Seasonal (Month)" for s in splits):
        weights = {datetime.date(2000, m, 1).strftime("%B"): w for m, w in zip(range(1, 13), [6, 6, 8, 8, 9, 9, 7, 5, 9, 10, 11, 12])}
        call("POST", "/global-splits", {
            "name": "Demo Seasonal (Month)", "repartition_logic": "Month", "repartition_values": weights,
            "distribution_profile": "even_distribution", "profile_params": {}, "years": [YEAR],
        }, token=token)
        splits = call("GET", "/global-splits", token=token)[1]
    split_id = next(s["id"] for s in splits if s["name"] == "Demo Seasonal (Month)")
    call("PUT", f"/kpis/{units}/global-split", {"global_split_id": split_id}, token=token)

    for i, plant_id in enumerate(plant_ids):
        call("POST", "/targets/annual", {
            "year": YEAR, "plant_id": plant_id,
            "targets_data_map": {
                str(units): {"targets": [{"target_number": 1, "target_value": 120000 + i * 10000}]},
                str(hours): {"targets": [{"target_number": 1, "target_value": 8000 + i * 500}]},
                str(oee): {"targets": [{"target_number": 1, "target_value": 85 - i * 3}]},
            },
        }, token=token)
    print(f"Saved {YEAR} targets for {len(plant_ids)} plants. Done.")


if __name__ == "__main__":
    sys.exit(main())
