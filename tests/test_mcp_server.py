import asyncio
import base64
import json

import pytest

from src import mcp_server
from src.plants_management import crud as plants_crud
from src.services import history_service

pytestmark = pytest.mark.usefixtures("db_dir")

# Every REST route maps to the MCP tool that covers it, or to the reason it has none.
# A new REST route fails test_every_rest_route_has_an_mcp_tool until it's added here.
NOT_ON_MCP = "excluded"
REST_TO_MCP = {
    "GET /health": NOT_ON_MCP,  # the MCP server has its own /health
    "GET /auth/status": NOT_ON_MCP,  # browser sign-up/sign-in: MCP authenticates with API keys
    "POST /auth/register": NOT_ON_MCP,
    "POST /auth/login": NOT_ON_MCP,
    "POST /auth/logout": NOT_ON_MCP,
    "GET /auth/me": "whoami",
    "POST /auth/change-password": "change_my_password",
    "GET /kpis": "list_kpis",
    "GET /kpis/tree": "get_kpi_tree",
    "POST /kpis": "create_kpi_indicator",
    "POST /kpis/nodes": "add_kpi_node",
    "DELETE /kpis/{kpi_id}": "soft_delete_kpi",
    "GET /kpis/{kpi_id}/status": "get_performance_status",
    "GET /kpis/{kpi_id}/history": "get_kpi_definition_history",
    "GET /kpis/{kpi_id}/target-history": "get_kpi_target_history",
    "GET /kpis/{kpi_id}": "get_kpi",
    "PUT /kpis/{kpi_id}": "update_kpi_spec",
    "GET /units-of-measure": "list_units_of_measure",
    "POST /units-of-measure": "create_unit_of_measure",
    "PUT /kpis/{kpi_id}/global-split": "set_kpi_global_split",
    "GET /kpis/{kpi_id}/visibility": "get_kpi_visibility",
    "PUT /kpis/{kpi_id}/visibility": "set_kpi_visibility",
    "GET /kpis/{kpi_id}/global-splits": "get_kpi_global_split",
    "GET /plants": "list_plants",
    "POST /plants": "create_plant",
    "PUT /plants/{plant_id}": "update_plant",
    "DELETE /plants/{plant_id}": "delete_plant",
    "GET /global-splits": "list_global_splits",
    "GET /global-splits/curve-preview": "get_curve_weight_suggestions",
    "GET /global-splits/{split_id}": "get_global_split",
    "POST /global-splits": "create_global_split",
    "PUT /global-splits/{split_id}": "update_global_split",
    "DELETE /global-splits/{split_id}": "delete_global_split",
    "GET /global-splits/{split_id}/indicators": "get_global_split_kpis",
    "PUT /global-splits/{split_id}/indicators": "set_global_split_kpis",
    "GET /targets/lean": "get_lean_targets",
    "POST /targets": NOT_ON_MCP,  # deprecated flat target table, not used by repartition
    "GET /targets": NOT_ON_MCP,
    "GET /targets/annual-entry": "get_annual_target",
    "GET /targets/annual": "list_annual_targets",
    "GET /targets/available-numbers": "get_available_target_numbers",
    "POST /targets/annual": "save_annual_targets",
    "GET /kpis/{kpi_id}/periodic-targets": "get_periodic_targets",
    "GET /kpis/{kpi_id}/periodic-targets/all-plants": "get_periodic_targets_all_plants",
    "POST /actuals": "record_actual",
    "GET /actuals": "list_actuals",
    "POST /analysis/multivariate": "analyze_seasonality",
    "GET /templates": "list_templates",
    "POST /templates": "create_template",
    "DELETE /templates/{template_id}": "delete_template",
    "GET /templates/{template_id}/indicators": "list_template_indicators",
    "POST /templates/{template_id}/indicators": "add_template_indicator",
    "PUT /templates/indicators/{definition_id}": "update_template_indicator",
    "DELETE /templates/indicators/{definition_id}": "remove_template_indicator",
    "POST /templates/{template_id}/apply": "apply_template",
    "GET /years": "list_years",
    "GET /export/lean": "export_csv",
    "GET /export/csv/{table_key}": "export_csv",
    "GET /export/all": "export_backup",
    "POST /import/restore": "restore_backup",
    "GET /users": "list_users",
    "POST /users": "create_user",
    "PUT /users/{user_id}": "update_user",
    "POST /users/{user_id}/reset-password": "reset_user_password",
    "GET /users/{user_id}/api-keys": "list_api_keys",
    "POST /users/{user_id}/api-keys": "create_api_key",
    "DELETE /api-keys/{key_id}": "revoke_api_key",
}


def _call(coro):
    return asyncio.run(coro)


def _data(result):
    assert not result.is_error, result.content
    if result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    return json.loads(result.content[0].text)


def _error_text(result) -> str:
    assert result.is_error
    return result.content[0].text


async def _session(fn):
    from mcp import Client

    async with Client(mcp_server.build_server()) as client:
        return await fn(client)


def _run(fn):
    return _call(_session(fn))


def _list_tools():
    async def run(client):
        return await client.list_tools()

    return {t.name: t for t in _run(run).tools}


def test_tools_are_listed_with_schemas_and_hints():
    tools = _list_tools()
    assert len(tools) == 60
    schema = tools["update_target_value"].input_schema
    assert set(schema["required"]) == {"kpi_id", "plant_id", "year", "value"}
    assert "changed_by" not in schema["properties"]  # identity can't be claimed by the caller
    assert all(t.annotations is not None for t in tools.values())
    assert tools["list_kpis"].annotations.read_only_hint is True
    assert tools["restore_backup"].annotations.destructive_hint is True
    assert tools["create_plant"].annotations.read_only_hint is False


def test_every_rest_route_has_an_mcp_tool():
    from fastapi.routing import APIRoute

    from src import api

    routes = {f"{m} {r.path}" for r in api.app.routes if isinstance(r, APIRoute) for m in r.methods if m != "HEAD"}
    assert routes == set(REST_TO_MCP), "Map new/removed REST routes in REST_TO_MCP"
    tools = set(_list_tools())
    missing = {route: tool for route, tool in REST_TO_MCP.items() if tool != NOT_ON_MCP and tool not in tools}
    assert not missing


def test_tool_flow_and_attribution(monkeypatch):
    monkeypatch.setenv("MCP_STDIO_USER", "agent-007")
    plant = plants_crud.add_plant("Main")

    async def run(client):
        node = _data(await client.call_tool("add_kpi_node", {"name": "Safety"}))["node_id"]
        kpi = _data(await client.call_tool("create_kpi_indicator", {"node_id": node, "name": "Incidents", "calculation_type": "Count"}))["kpi_id"]
        _data(await client.call_tool("update_target_value", {"kpi_id": kpi, "plant_id": plant, "year": 2026, "value": 12}))
        quarters = _data(await client.call_tool("get_periodic_targets", {"kpi_id": kpi, "plant_id": plant, "year": 2026, "period_type": "Quarter"}))
        split = _data(await client.call_tool("create_global_split", {
            "name": "Spring", "repartition_logic": "Quarter", "distribution_profile": "even_distribution",
            "repartition_values": {"Q1": 10, "Q2": 70, "Q3": 10, "Q4": 10}}))["split_id"]
        _data(await client.call_tool("set_kpi_global_split", {"kpi_id": kpi, "global_split_id": split}))
        renamed = _data(await client.call_tool("update_global_split", {"split_id": split, "name": "Spring v2"}))
        after = _data(await client.call_tool("get_periodic_targets", {"kpi_id": kpi, "plant_id": plant, "year": 2026, "period_type": "Quarter"}))
        bad = await client.call_tool("update_global_split", {"split_id": split, "repartition_logic": "Fortnight"})
        linked = _data(await client.call_tool("get_global_split_kpis", {"split_id": split}))
        return kpi, quarters, renamed, after, bad, linked

    kpi, quarters, renamed, after, bad, linked = _run(run)
    assert sum(q["target_value"] for q in quarters) == pytest.approx(12)
    assert renamed["status"] == "success"
    assert {q["period"]: round(q["target_value"], 6) for q in after}["Q2"] == pytest.approx(8.4)
    assert bad.is_error
    assert [link["kpi_id"] for link in linked] == [kpi]
    assert history_service.get_target_history(kpi)[0]["changed_by"] == "agent-007"


def test_anticipated_errors_reach_the_model():
    async def run(client):
        node = _data(await client.call_tool("add_kpi_node", {"name": "Ops"}))["node_id"]
        kpi = _data(await client.call_tool("create_kpi_indicator", {"node_id": node, "name": "Units"}))["kpi_id"]
        return (
            await client.call_tool("soft_delete_kpi", {"kpi_id": 999}),
            await client.call_tool("update_kpi_spec", {"kpi_id": kpi, "data_updates": {"formula_string": "[999] * 2"}}),
            await client.call_tool("update_kpi_spec", {"kpi_id": kpi, "data_updates": {"is_active": 0}}),
            await client.call_tool("create_kpi_indicator", {"node_id": node, "name": "Units"}),
        )

    missing, bad_formula, bad_field, duplicate = _run(run)
    assert "KPI 999 not found" in _error_text(missing)
    assert "999" in _error_text(bad_formula)
    assert "can't be updated" in _error_text(bad_field)
    assert "already exists" in _error_text(duplicate)


def test_plants_visibility_actuals_and_history():
    async def run(client):
        north = _data(await client.call_tool("create_plant", {"name": "North", "color": "#22c55e"}))["plant_id"]
        south = _data(await client.call_tool("create_plant", {"name": "South"}))["plant_id"]
        _data(await client.call_tool("update_plant", {"plant_id": south, "description": "Second site"}))
        bad_color = await client.call_tool("create_plant", {"name": "X", "color": "red"})
        node = _data(await client.call_tool("add_kpi_node", {"name": "Ops"}))["node_id"]
        kpi = _data(await client.call_tool("create_kpi_indicator", {
            "node_id": node, "name": "OEE", "calculation_type": "Average", "unit_of_measure": "%",
            "threshold_json": {"warning_margin": 0.05, "error_margin": 0.15}}))["kpi_id"]
        _data(await client.call_tool("update_kpi_spec", {"kpi_id": kpi, "data_updates": {"description": "Overall equipment eff."}}))
        _data(await client.call_tool("set_kpi_visibility", {"kpi_id": kpi, "visibility": [{"plant_id": south, "is_enabled": False}]}))
        visibility = _data(await client.call_tool("get_kpi_visibility", {"kpi_id": kpi}))
        for_south = _data(await client.call_tool("list_kpis", {"plant_id": south}))
        _data(await client.call_tool("update_target_value", {"kpi_id": kpi, "plant_id": north, "year": 2026, "value": 85}))
        for day, value in (("2026-01-05", 80.0), ("2026-01-06", 84.0), ("2026-01-06", 86.0)):
            _data(await client.call_tool("record_actual", {"kpi_id": kpi, "plant_id": north, "measurement_date": day, "actual_value": value}))
        bad_date = await client.call_tool("record_actual", {"kpi_id": kpi, "plant_id": north, "measurement_date": "5/1/2026", "actual_value": 1})
        actuals = _data(await client.call_tool("list_actuals", {"kpi_id": kpi, "plant_id": north}))
        status = _data(await client.call_tool("get_performance_status", {"kpi_id": kpi, "plant_id": north, "target_value": 85}))
        definition_history = _data(await client.call_tool("get_kpi_definition_history", {"kpi_id": kpi}))
        target_history = _data(await client.call_tool("get_kpi_target_history", {"kpi_id": kpi, "plant_id": north}))
        plants = _data(await client.call_tool("list_plants", {}))
        refused = await client.call_tool("delete_plant", {"plant_id": north})
        _data(await client.call_tool("delete_plant", {"plant_id": north, "force": True}))
        return (south, kpi, bad_color, visibility, for_south, bad_date, actuals, status, definition_history,
                target_history, plants, refused)

    (south, kpi, bad_color, visibility, for_south, bad_date, actuals, status, definition_history,
     target_history, plants, refused) = _run(run)
    assert bad_color.is_error
    assert visibility == [{"plant_id": south, "is_enabled": False}]
    assert kpi not in [k["id"] for k in for_south]
    assert bad_date.is_error
    assert [a["actual_value"] for a in actuals] == [80.0, 86.0]  # same day overwrites
    assert status["status"] in ("on_track", "warning", "out_of_range")
    assert [h["change_type"] for h in definition_history] == ["UPDATE", "CREATE"]  # newest first
    assert target_history[0]["new_value"] == 85
    assert next(p for p in plants if p["id"] == south)["description"] == "Second site"
    assert "force" in _error_text(refused).lower() or "referenced" in _error_text(refused).lower()


def test_performance_status_uses_the_stored_target():
    plant = plants_crud.add_plant("Main")

    async def run(client):
        node = _data(await client.call_tool("add_kpi_node", {"name": "Ops"}))["node_id"]
        kpi = _data(await client.call_tool("create_kpi_indicator", {"node_id": node, "name": "OEE", "calculation_type": "Average"}))["kpi_id"]
        _data(await client.call_tool("record_actual", {"kpi_id": kpi, "plant_id": plant, "measurement_date": "2026-03-10", "actual_value": 83.2}))
        no_target = await client.call_tool("get_performance_status", {"kpi_id": kpi, "plant_id": plant})
        _data(await client.call_tool("update_target_value", {"kpi_id": kpi, "plant_id": plant, "year": 2026, "value": 85}))
        stored = _data(await client.call_tool("get_performance_status", {"kpi_id": kpi, "plant_id": plant}))
        explicit = _data(await client.call_tool("get_performance_status", {"kpi_id": kpi, "plant_id": plant, "target_value": 80}))
        other_scenario = await client.call_tool("get_performance_status", {"kpi_id": kpi, "plant_id": plant, "target_number": 2})
        return no_target, stored, explicit, other_scenario

    no_target, stored, explicit, other_scenario = _run(run)
    assert "No target 1" in _error_text(no_target) and "target_value" in _error_text(no_target)
    assert stored["target"] == pytest.approx(85) and stored["target_source"] == "daily"
    assert stored["status"] == "warning" and stored["diff_pct"] == pytest.approx(-2.12)
    assert explicit["target"] == 80 and explicit["target_source"] == "explicit" and explicit["status"] == "on_track"
    assert "No target 2" in _error_text(other_scenario)


def test_performance_status_parameters_match_rest():
    from src import api

    rest = {p["name"] for p in api.app.openapi()["paths"]["/kpis/{kpi_id}/status"]["get"]["parameters"]}
    assert rest == set(_list_tools()["get_performance_status"].input_schema["properties"])
    assert rest == {"kpi_id", "plant_id", "target_value", "target_number"}


def test_bulk_save_with_split_settings_and_target_queries():
    p1, p2 = plants_crud.add_plant("A"), plants_crud.add_plant("B")
    weights = {m: (20 if m == "January" else 80 / 11) for m in (
        "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
        "November", "December")}

    async def run(client):
        node = _data(await client.call_tool("add_kpi_node", {"name": "Ops"}))["node_id"]
        units = _data(await client.call_tool("create_kpi_indicator", {"node_id": node, "name": "Units", "target_count": 2}))["kpi_id"]
        hours = _data(await client.call_tool("create_kpi_indicator", {"node_id": node, "name": "Hours"}))["kpi_id"]
        _data(await client.call_tool("save_annual_targets", {"year": 2026, "plant_id": [p1, p2], "targets_by_kpi": {
            str(units): {"targets": [{"target_number": 1, "target_value": 1200}, {"target_number": 2, "target_value": 1500}],
                         "repartition_logic": "Month", "repartition_values": weights},
            str(hours): {"targets": [{"target_number": 1, "target_value": 100}]},
        }}))
        months = _data(await client.call_tool("get_periodic_targets", {"kpi_id": units, "plant_id": p2, "year": 2026, "period_type": "Month"}))
        annual = _data(await client.call_tool("list_annual_targets", {"plant_id": p1, "year": 2026}))
        numbers = _data(await client.call_tool("get_available_target_numbers", {"year": 2026, "plant_id": p1, "kpi_id": units}))
        years = _data(await client.call_tool("list_years", {}))
        lean = _data(await client.call_tool("get_lean_targets", {}))
        all_plants = _data(await client.call_tool("get_periodic_targets_all_plants", {"kpi_id": units, "period_type": "Quarter", "year": 2026}))
        return months, annual, numbers, years, lean, all_plants

    months, annual, numbers, years, lean, all_plants = _run(run)
    assert months[0]["period"] == "January" and months[0]["target_value"] == pytest.approx(240)
    assert sum(m["target_value"] for m in months) == pytest.approx(1200)
    assert len(annual) == 2
    assert numbers == [1, 2]
    assert years == [{"year": 2026}]
    assert lean and all_plants


def test_templates_flow():
    async def run(client):
        template = _data(await client.call_tool("create_template", {"name": "Line KPIs"}))["template_id"]
        definition = _data(await client.call_tool("add_template_indicator", {
            "template_id": template, "name": "Scrap", "calculation_type": "Sum", "unit_of_measure": "kg"}))["definition_id"]
        node = _data(await client.call_tool("add_kpi_node", {"name": "Line 1"}))["node_id"]
        applied = _data(await client.call_tool("apply_template", {"template_id": template, "node_id": node}))
        _data(await client.call_tool("update_template_indicator", {
            "definition_id": definition, "template_id": template, "name": "Scrap", "calculation_type": "Sum",
            "unit_of_measure": "t"}))
        kpis = _data(await client.call_tool("list_kpis", {}))
        listed = _data(await client.call_tool("list_template_indicators", {"template_id": template}))
        templates = _data(await client.call_tool("list_templates", {}))
        _data(await client.call_tool("remove_template_indicator", {"definition_id": definition}))
        after_remove = _data(await client.call_tool("list_kpis", {}))
        _data(await client.call_tool("delete_template", {"template_id": template}))
        missing = await client.call_tool("delete_template", {"template_id": template})
        return applied, kpis, listed, templates, after_remove, missing

    applied, kpis, listed, templates, after_remove, missing = _run(run)
    assert applied["applied"] == 1
    scrap = [k for k in kpis if k["indicator_name"] == "Scrap"]
    assert len(scrap) == 1 and scrap[0]["unit_of_measure"] == "t"
    assert [d["indicator_name_in_template"] for d in listed] == ["Scrap"]
    assert [t["name"] for t in templates] == ["Line KPIs"]
    assert not [k for k in after_remove if k["indicator_name"] == "Scrap"]
    assert "not found" in _error_text(missing)


def test_analyze_seasonality_from_csv_text():
    import datetime

    rows = ["date,sales,temp"]
    for year in (2024, 2025):
        for month in range(1, 13):
            sales = 100 + (50 if month in (11, 12) else 0) + month
            rows.append(f"{datetime.date(year, month, 1).isoformat()},{sales},{10 + month}")
    csv_text = "\n".join(rows)

    async def run(client):
        ok = _data(await client.call_tool("analyze_seasonality", {
            "csv_text": csv_text, "target_cols": ["sales"], "feature_cols": ["temp"], "date_col": "date"}))
        neither = await client.call_tool("analyze_seasonality", {"target_cols": ["sales"], "date_col": "date"})
        bad_col = await client.call_tool("analyze_seasonality", {"csv_text": csv_text, "target_cols": ["nope"], "date_col": "date"})
        return ok, neither, bad_col

    ok, neither, bad_col = _run(run)
    assert sum(ok["weights"].values()) == pytest.approx(100, abs=0.01)
    assert set(ok["weights"]) == {datetime.date(2000, m, 1).strftime("%B") for m in range(1, 13)}
    assert ok["weights"]["December"] > ok["weights"]["January"]
    assert "exactly one" in _error_text(neither)
    assert "nope" in _error_text(bad_col)


def test_exports_and_backup_round_trip():
    plants_crud.add_plant("Keep")

    async def run(client):
        csv_plants = _data(await client.call_tool("export_csv", {"table": "Plants"}))
        csv_lean = _data(await client.call_tool("export_csv", {"table": "Lean Targets"}))
        backup = _data(await client.call_tool("export_backup", {}))
        _data(await client.call_tool("create_plant", {"name": "After backup"}))
        restored = _data(await client.call_tool("restore_backup", {"zip_base64": backup["zip_base64"]}))
        plants = _data(await client.call_tool("list_plants", {}))
        garbage = await client.call_tool("restore_backup", {"zip_base64": base64.b64encode(b"not a zip").decode()})
        return csv_plants, csv_lean, backup, restored, plants, garbage

    csv_plants, csv_lean, backup, restored, plants, garbage = _run(run)
    assert csv_plants["csv"].splitlines()[0] == "id,name,description,visible,color" and "Keep" in csv_plants["csv"]
    assert csv_lean["filename"] == "lean_target_data.csv"
    assert backup["size_bytes"] > 0
    assert restored["status"] == "success" and restored["snapshot"]
    assert [p["name"] for p in plants] == ["Keep"]
    assert garbage.is_error


def test_stdio_admin_can_be_disabled(monkeypatch):
    async def run(client):
        return (
            _data(await client.call_tool("whoami", {})),
            await client.call_tool("create_user", {"name": "bob", "password": "password-123"}),
            await client.call_tool("change_my_password", {"current_password": "x", "new_password": "password-123"}),
        )

    me, created, change = _run(run)
    assert me["transport"] == "stdio" and me["is_admin"] is True and me["id"] is None
    assert not created.is_error
    assert "stdio" in _error_text(change)

    monkeypatch.setenv("MCP_STDIO_ADMIN", "false")
    _, refused, _ = _run(run)
    assert "Admin rights required" in _error_text(refused)


# --- Streamable HTTP (API-key auth) ---

_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _http_app():
    from starlette.testclient import TestClient

    return TestClient(mcp_server.build_http_app(port=8001), base_url="http://localhost:8001")


def _rpc(http, key, method, params=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    res = http.post("/mcp", json=payload, headers=_HEADERS | {"Authorization": f"Bearer {key}"})
    assert res.status_code == 200, res.text
    return res.json()["result"]


def _tool(http, key, name, args=None):
    result = _rpc(http, key, "tools/call", {"name": name, "arguments": args or {}})
    if result.get("isError"):
        return None, result["content"][0]["text"]
    data = result.get("structuredContent")
    return (data.get("result", data) if data is not None else json.loads(result["content"][0]["text"])), None


def test_http_requires_api_key():
    from src.user_management import crud as user_crud

    user_id = user_crud.add_user("robot-owner", "password-123")
    key = user_crud.create_api_key(user_id, "ci")["raw_key"]
    with _http_app() as http:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        assert http.post("/mcp", json=payload, headers=_HEADERS).status_code == 401
        assert http.post("/mcp", json=payload, headers=_HEADERS | {"Authorization": "Bearer kpi_mcp_wrong"}).status_code == 401
        ok = http.post("/mcp", json=payload, headers=_HEADERS | {"Authorization": f"Bearer {key}"})
        assert ok.status_code == 200, ok.text
        assert ok.json()["result"]["serverInfo"]["name"] == "Data Entry KPI Target Manager"
        assert http.get("/health").json() == {"status": "healthy"}


def test_http_roles_follow_the_key_owner():
    from src.user_management import crud as user_crud

    boss = user_crud.add_user("boss", "password-123")  # first account -> admin
    alice = user_crud.add_user("alice", "password-123")
    boss_key = user_crud.create_api_key(boss, "boss")["raw_key"]
    alice_key = user_crud.create_api_key(alice, "alice")["raw_key"]
    plant = plants_crud.add_plant("Main")

    with _http_app() as http:
        me, _ = _tool(http, alice_key, "whoami")
        assert me["name"] == "alice" and me["is_admin"] is False and me["transport"] == "http"

        # admin-only and other-account tools are refused for a regular user...
        assert "Admin rights required" in _tool(http, alice_key, "create_user", {"name": "eve", "password": "password-123"})[1]
        assert "Admin rights required" in _tool(http, alice_key, "restore_backup", {"zip_base64": "UEs="})[1]
        assert "Admin rights required" in _tool(http, alice_key, "reset_user_password", {"user_id": boss, "new_password": "hijacked-1"})[1]
        assert "own account" in _tool(http, alice_key, "create_api_key", {"user_id": boss, "label": "steal"})[1]
        assert "own account" in _tool(http, alice_key, "update_user", {"user_id": boss, "is_active": False})[1]
        assert "Only admins" in _tool(http, alice_key, "update_user", {"user_id": alice, "is_admin": True})[1]
        assert all("email" not in u for u in _tool(http, alice_key, "list_users")[0])

        # ...but self-service works
        own, _ = _tool(http, alice_key, "create_api_key", {"user_id": alice, "label": "laptop"})
        assert own["raw_key"].startswith("kpi_mcp_")
        assert _tool(http, alice_key, "revoke_api_key", {"key_id": own["id"]})[1] is None
        assert _tool(http, alice_key, "update_user", {"user_id": alice, "color": "#22c55e"})[1] is None
        assert _tool(http, alice_key, "change_my_password", {"current_password": "password-123", "new_password": "password-456"})[1] is None

        # the admin key can do all of it
        created, err = _tool(http, boss_key, "create_user", {"name": "eve", "password": "password-123"})
        assert err is None and created["name"] == "eve"
        assert _tool(http, boss_key, "list_api_keys", {"user_id": alice})[1] is None
        assert "email" in _tool(http, boss_key, "list_users")[0][0]

        # writes are attributed to the key's owner
        node, _ = _tool(http, alice_key, "add_kpi_node", {"name": "Ops"})
        kpi, _ = _tool(http, alice_key, "create_kpi_indicator", {"node_id": node["node_id"], "name": "Units"})
        assert _tool(http, alice_key, "update_target_value", {"kpi_id": kpi["kpi_id"], "plant_id": plant, "year": 2026, "value": 10})[1] is None
        assert history_service.get_target_history(kpi["kpi_id"])[0]["changed_by"] == "alice"

        # deactivating the owner kills the key at once
        assert _tool(http, boss_key, "update_user", {"user_id": alice, "is_active": False})[1] is None
        res = http.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
                        headers=_HEADERS | {"Authorization": f"Bearer {alice_key}"})
        assert res.status_code == 401
