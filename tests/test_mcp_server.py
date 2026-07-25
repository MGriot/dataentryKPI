# tests/test_mcp_server.py
import json
import pytest
from src.config import settings as app_config
from src.data_access import setup
from src import mcp_server

@pytest.fixture(autouse=True)
def setup_tmp_dbs(tmp_path, monkeypatch):
    monkeypatch.setitem(app_config.SETTINGS, "database_base_dir", str(tmp_path))
    setup.setup_databases()

def test_mcp_tools_list():
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    res_str = mcp_server.handle_json_rpc_request(req)
    res = json.loads(res_str)
    assert res["id"] == 1
    assert "tools" in res["result"]
    tool_names = [t["name"] for t in res["result"]["tools"]]
    assert "get_kpi_tree" in tool_names
    assert "create_kpi_indicator" in tool_names
    assert "update_target_value" in tool_names

def test_mcp_tool_execution_flow():
    # 1. Add Node via MCP
    req_node = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "add_kpi_node",
            "arguments": {"parent_id": None, "name": "Safety Group"}
        }
    })
    res_node = json.loads(mcp_server.handle_json_rpc_request(req_node))
    content_node = json.loads(res_node["result"]["content"][0]["text"])
    node_id = content_node["node_id"]
    assert node_id > 0

    # 2. Add Indicator via MCP
    req_ind = json.dumps({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "create_kpi_indicator",
            "arguments": {
                "node_id": node_id,
                "name": "Lost Time Injuries",
                "direction": "Lower is Better"
            }
        }
    })
    res_ind = json.loads(mcp_server.handle_json_rpc_request(req_ind))
    content_ind = json.loads(res_ind["result"]["content"][0]["text"])
    kpi_id = content_ind["kpi_id"]
    assert kpi_id > 0

    # 3. Update Target via MCP
    req_target = json.dumps({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "update_target_value",
            "arguments": {
                "plant_id": 1,
                "kpi_id": kpi_id,
                "target_number": 1,
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "value": 0.0
            }
        }
    })
    res_target = json.loads(mcp_server.handle_json_rpc_request(req_target))
    content_target = json.loads(res_target["result"]["content"][0]["text"])
    assert content_target["updated"] is True
