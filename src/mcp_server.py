# src/mcp_server.py
"""
Model Context Protocol (MCP) Server for Data Entry KPI Target Manager.
Exposes tools for AI agents to query hierarchy trees, create nodes/indicators,
update targets, retrieve performance status, and soft-delete KPIs.

Two transports are supported:
  - stdio (default): one JSON-RPC request per line on stdin, response on stdout.
    This is how local MCP clients (e.g. Claude Desktop) spawn the server as a
    subprocess -- there is no per-caller identity, so `changed_by` is whatever
    the client sends (defaulting to "mcp_agent").
  - HTTP (`python src/mcp_server.py --http`, or $MCP_TRANSPORT=http): a shared,
    long-running service (this is what the `mcp_server` container in
    podman-compose.yml runs -- stdio cannot be a shared container service since
    nothing is attached to its stdin there). Every request must carry an
    `Authorization: Bearer <api_key>` header; the key is resolved to a user via
    src.user_management.crud, and that user's name is force-set as `changed_by`
    on any write the tool call makes, overriding whatever the caller claims.
"""
import sys
import os
import json
from typing import Dict, Any, List, Optional
from src.kpi_management import crud as kpi_crud
from src import data_retriever
from src.user_management import crud as user_crud

TOOLS_REGISTRY = {
    "get_kpi_tree": {
        "name": "get_kpi_tree",
        "description": "Retrieves the KPI tree hierarchy starting from optional root_id up to max depth.",
        "parameters": {
            "root_id": {"type": "integer", "description": "Optional root node ID", "default": None},
            "depth": {"type": "integer", "description": "Optional depth limit", "default": None}
        }
    },
    "add_kpi_node": {
        "name": "add_kpi_node",
        "description": "Creates a new hierarchy node (folder/group/subgroup).",
        "parameters": {
            "parent_id": {"type": "integer", "description": "Parent node ID or null for root"},
            "name": {"type": "string", "description": "Node name"},
            "custom_level_label": {"type": "string", "description": "Optional level label", "default": None}
        }
    },
    "create_kpi_indicator": {
        "name": "create_kpi_indicator",
        "description": "Creates a new KPI indicator and specification.",
        "parameters": {
            "node_id": {"type": "integer", "description": "Parent node ID"},
            "name": {"type": "string", "description": "KPI indicator name"},
            "description": {"type": "string", "description": "Optional description", "default": None},
            "calculation_type": {"type": "string", "description": "Aggregation type (Sum, Average, Last, Min, Max, Count)", "default": "Sum"},
            "unit_of_measure": {"type": "string", "description": "Unit of measure", "default": None},
            "owner": {"type": "string", "description": "KPI owner", "default": None},
            "direction": {"type": "string", "description": "Direction (Higher is Better, Lower is Better, Range)", "default": "Higher is Better"},
            "target_granularity": {"type": "string", "description": "Target granularity (Daily, Weekly, Monthly, Quarterly, Yearly)", "default": "Monthly"}
        }
    },
    "update_target_value": {
        "name": "update_target_value",
        "description": "Creates or updates a KPI target value with audit logging.",
        "parameters": {
            "plant_id": {"type": "integer", "description": "Plant ID"},
            "kpi_id": {"type": "integer", "description": "KPI spec ID"},
            "target_number": {"type": "integer", "description": "Target scenario number (1 for Base, 2 for Stretch)"},
            "period_start": {"type": "string", "description": "Period start date (YYYY-MM-DD)"},
            "period_end": {"type": "string", "description": "Period end date (YYYY-MM-DD)"},
            "value": {"type": "number", "description": "Target numerical value"},
            "changed_by": {"type": "string", "description": "User or AI identity", "default": "mcp_agent"}
        }
    },
    "get_performance_status": {
        "name": "get_performance_status",
        "description": "Evaluates actual measurements vs targets, directional status, time filters, and trend slope.",
        "parameters": {
            "kpi_id": {"type": "integer", "description": "KPI spec ID"},
            "plant_id": {"type": "integer", "description": "Plant ID"},
            "target_value": {"type": "number", "description": "Target value to compare against", "default": None}
        }
    },
    "soft_delete_kpi": {
        "name": "soft_delete_kpi",
        "description": "Soft deletes a KPI indicator (is_active = 0) while preserving historical data.",
        "parameters": {
            "kpi_id": {"type": "integer", "description": "KPI spec ID to delete"},
            "changed_by": {"type": "string", "description": "User or AI identity", "default": "mcp_agent"}
        }
    }
}

def dispatch_tool_call(name: str, arguments: Dict[str, Any], changed_by_override: Optional[str] = None) -> Any:
    if changed_by_override:
        # HTTP transport: identity comes from the authenticated API key, not the caller's claim.
        arguments = {**arguments, "changed_by": changed_by_override}

    if name == "get_kpi_tree":
        return kpi_crud.get_kpi_tree(
            root_id=arguments.get("root_id"),
            depth=arguments.get("depth")
        )
    elif name == "add_kpi_node":
        node_id = kpi_crud.add_kpi_node(
            parent_id=arguments.get("parent_id"),
            name=arguments.get("name"),
            custom_level_label=arguments.get("custom_level_label")
        )
        return {"node_id": node_id, "name": arguments.get("name")}
    elif name == "create_kpi_indicator":
        return kpi_crud.create_kpi_indicator(
            node_id=arguments["node_id"],
            name=arguments["name"],
            description=arguments.get("description"),
            calculation_type=arguments.get("calculation_type", "Sum"),
            unit_of_measure=arguments.get("unit_of_measure"),
            owner=arguments.get("owner"),
            direction=arguments.get("direction", "Higher is Better"),
            target_granularity=arguments.get("target_granularity", "Monthly"),
            changed_by="mcp_agent"
        )
    elif name == "update_target_value":
        success = kpi_crud.update_target_value(
            plant_id=arguments["plant_id"],
            kpi_id=arguments["kpi_id"],
            target_number=arguments.get("target_number", 1),
            period_start=arguments["period_start"],
            period_end=arguments["period_end"],
            target_value=float(arguments["value"]),
            changed_by=arguments.get("changed_by", "mcp_agent")
        )
        return {"status": "success", "updated": success}
    elif name == "get_performance_status":
        return data_retriever.get_kpi_performance_status(
            kpi_id=arguments["kpi_id"],
            plant_id=arguments["plant_id"],
            target_value=arguments.get("target_value")
        )
    elif name == "soft_delete_kpi":
        success = kpi_crud.soft_delete_kpi(
            kpi_id=arguments["kpi_id"],
            changed_by=arguments.get("changed_by", "mcp_agent")
        )
        return {"status": "success", "kpi_id": arguments["kpi_id"], "is_active": False, "deleted": success}
    else:
        raise ValueError(f"Unknown MCP tool: '{name}'")

def handle_json_rpc_request(request_str: str, changed_by_override: Optional[str] = None) -> str:
    try:
        req = json.loads(request_str)
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "tools/list":
            result = {"tools": list(TOOLS_REGISTRY.values())}
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            result = {"content": [{"type": "text", "text": json.dumps(dispatch_tool_call(name, arguments, changed_by_override))}]}
        else:
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})

        return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result})
    except Exception as e:
        return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}})


def _run_stdio():
    print("Data Entry KPI Target Manager MCP Server started (stdio transport).", file=sys.stderr)
    for line in sys.stdin:
        if line.strip():
            response = handle_json_rpc_request(line)
            sys.stdout.write(response + "\n")
            sys.stdout.flush()


def _build_http_app():
    """Lazily builds the HTTP transport app (only imports FastAPI when actually needed)."""
    from fastapi import FastAPI, HTTPException, Request

    app = FastAPI(title="Data Entry KPI Target Manager MCP Server (HTTP transport)")

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.post("/mcp")
    async def mcp_endpoint(request: Request):
        auth_header = request.headers.get("authorization", "")
        raw_key = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
        user = user_crud.validate_api_key(raw_key) if raw_key else None
        if not user:
            raise HTTPException(status_code=401, detail="Missing or invalid API key. Send 'Authorization: Bearer <key>'.")

        body = await request.body()
        response_str = handle_json_rpc_request(body.decode("utf-8"), changed_by_override=user["name"])
        return json.loads(response_str)

    return app


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if "--http" in sys.argv:
        transport = "http"

    if transport == "http":
        import uvicorn
        port = int(os.environ.get("MCP_PORT", "8001"))
        print(f"Data Entry KPI Target Manager MCP Server starting (HTTP transport) on 0.0.0.0:{port}", file=sys.stderr)
        uvicorn.run(_build_http_app(), host="0.0.0.0", port=port)
    else:
        _run_stdio()
