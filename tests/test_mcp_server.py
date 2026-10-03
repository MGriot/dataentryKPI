import asyncio
import json

import pytest

from src import mcp_server
from src.plants_management import crud as plants_crud
from src.services import history_service

pytestmark = pytest.mark.usefixtures("db_dir")


def _call(coro):
    return asyncio.run(coro)


def _data(result):
    assert not result.is_error, result.content
    if result.structured_content is not None:
        return result.structured_content.get("result", result.structured_content)
    return json.loads(result.content[0].text)


async def _session(fn):
    from mcp import Client

    async with Client(mcp_server.build_server()) as client:
        return await fn(client)


def test_tools_are_listed_with_schemas():
    async def run(client):
        return await client.list_tools()

    tools = {t.name: t for t in _call(_session(run)).tools}
    assert len(tools) == 22
    schema = tools["update_target_value"].input_schema
    assert set(schema["required"]) == {"kpi_id", "plant_id", "year", "value"}
    assert "changed_by" not in schema["properties"]  # identity can't be claimed by the caller


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
        return kpi, quarters, renamed, after, bad

    kpi, quarters, renamed, after, bad = _call(_session(run))
    assert sum(q["target_value"] for q in quarters) == pytest.approx(12)
    assert renamed["status"] == "success"
    assert {q["period"]: round(q["target_value"], 6) for q in after}["Q2"] == pytest.approx(8.4)
    assert bad.is_error
    assert history_service.get_target_history(kpi)[0]["changed_by"] == "agent-007"


def test_http_requires_api_key(db_dir):
    from starlette.testclient import TestClient

    from src.user_management import crud as user_crud

    user_id = user_crud.add_user("robot-owner", "password-123")
    key = user_crud.create_api_key(user_id, "ci")["raw_key"]
    app = mcp_server.build_http_app(port=8001)
    with TestClient(app, base_url="http://localhost:8001") as http:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        assert http.post("/mcp", json=payload, headers=headers).status_code == 401
        assert http.post("/mcp", json=payload, headers=headers | {"Authorization": "Bearer kpi_mcp_wrong"}).status_code == 401
        ok = http.post("/mcp", json=payload, headers=headers | {"Authorization": f"Bearer {key}"})
        assert ok.status_code == 200, ok.text
        assert ok.json()["result"]["serverInfo"]["name"] == "Data Entry KPI Target Manager"
        assert http.get("/health").json() == {"status": "healthy"}
