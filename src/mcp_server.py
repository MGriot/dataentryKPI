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
from src.kpi_management import splits as splits_crud
from src import data_retriever
from src.target_management import annual as annual_management
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
        "description": (
            "Sets a KPI's annual target for a year/plant/target-scenario -- the same modern path "
            "Target Entry itself uses. This automatically triggers the repartition engine, which "
            "recalculates and stores Day/Week/Month/Quarter/Year breakdowns for the KPI, honoring "
            "whatever Global Split Template is assigned to it in KPI Explorer (see "
            "get_kpi_global_split / set_kpi_global_split)."
        ),
        "parameters": {
            "plant_id": {"type": "integer", "description": "Plant ID"},
            "kpi_id": {"type": "integer", "description": "KPI spec ID"},
            "year": {"type": "integer", "description": "Target year"},
            "target_number": {"type": "integer", "description": "Target scenario number (1 for Base, 2 for Stretch)", "default": 1},
            "value": {"type": "number", "description": "Annual target value"},
            "changed_by": {"type": "string", "description": "User or AI identity", "default": "mcp_agent"}
        }
    },
    "get_annual_target": {
        "name": "get_annual_target",
        "description": "Fetches a KPI's annual target entry for a year/plant, including its per-scenario target values.",
        "parameters": {
            "year": {"type": "integer", "description": "Target year"},
            "plant_id": {"type": "integer", "description": "Plant ID"},
            "kpi_id": {"type": "integer", "description": "KPI spec ID"}
        }
    },
    "get_periodic_targets": {
        "name": "get_periodic_targets",
        "description": "Retrieves a KPI's repartitioned target breakdown for one plant at a chosen aggregation level.",
        "parameters": {
            "kpi_id": {"type": "integer", "description": "KPI spec ID"},
            "plant_id": {"type": "integer", "description": "Plant ID"},
            "year": {"type": "integer", "description": "Target year"},
            "period_type": {"type": "string", "description": "Aggregation level: Day, Week, Month, Quarter, or Year"},
            "target_number": {"type": "integer", "description": "Target scenario number", "default": 1}
        }
    },
    "get_periodic_targets_all_plants": {
        "name": "get_periodic_targets_all_plants",
        "description": "Retrieves a KPI's repartitioned target breakdown across all plants at a chosen aggregation level.",
        "parameters": {
            "kpi_id": {"type": "integer", "description": "KPI spec ID"},
            "period_type": {"type": "string", "description": "Aggregation level: Day, Week, Month, Quarter, or Year"},
            "year": {"type": "integer", "description": "Optional target year", "default": None}
        }
    },
    "update_kpi_spec": {
        "name": "update_kpi_spec",
        "description": "Updates a KPI's specification fields (description, unit_of_measure, calculation_type, target_count, etc.).",
        "parameters": {
            "kpi_id": {"type": "integer", "description": "KPI spec ID"},
            "data_updates": {"type": "object", "description": "Dict of fields to update, e.g. {\"unit_of_measure\": \"Metric Tons\"}"},
            "changed_by": {"type": "string", "description": "User or AI identity", "default": "mcp_agent"}
        }
    },
    "list_kpis": {
        "name": "list_kpis",
        "description": "Lists detailed KPI specifications, optionally filtered to visible-only or a specific plant.",
        "parameters": {
            "only_visible": {"type": "boolean", "description": "Restrict to visible KPIs", "default": False},
            "plant_id": {"type": "integer", "description": "Optional plant ID filter", "default": None}
        }
    },
    "list_plants": {
        "name": "list_plants",
        "description": "Lists facilities/plants.",
        "parameters": {
            "visible_only": {"type": "boolean", "description": "Restrict to visible plants", "default": False}
        }
    },
    "list_units_of_measure": {
        "name": "list_units_of_measure",
        "description": "Lists the registry of defined Units of Measure (KPI Explorer's UoM picker).",
        "parameters": {}
    },
    "create_unit_of_measure": {
        "name": "create_unit_of_measure",
        "description": "Adds a new unit of measure to the registry, or returns the existing one if it already exists.",
        "parameters": {
            "name": {"type": "string", "description": "Unit of measure name, e.g. 'Metric Tons'"}
        }
    },
    "list_global_splits": {
        "name": "list_global_splits",
        "description": "Lists Global Split Templates, optionally filtered by year (year-agnostic presets always included).",
        "parameters": {
            "year": {"type": "integer", "description": "Optional year filter", "default": None}
        }
    },
    "get_global_split": {
        "name": "get_global_split",
        "description": "Fetches a single Global Split Template by ID.",
        "parameters": {
            "split_id": {"type": "integer", "description": "Global split template ID"}
        }
    },
    "create_global_split": {
        "name": "create_global_split",
        "description": (
            "Creates a Global Split Template: a reusable named repartition/seasonality definition "
            "(period weights + a distribution curve) that can be assigned to KPIs in KPI Explorer."
        ),
        "parameters": {
            "name": {"type": "string", "description": "Template name"},
            "repartition_logic": {"type": "string", "description": "Month, Quarter, or Week"},
            "repartition_values": {"type": "object", "description": "Per-period weight percentages, e.g. {\"January\": 10, \"February\": 10, ...}", "default": {}},
            "distribution_profile": {
                "type": "string",
                "description": "even_distribution, annual_progressive, annual_progressive_weekday_bias, true_annual_sinusoidal, or event_based_spikes_or_dips"
            },
            "profile_params": {"type": "object", "description": "Extra curve parameters (e.g. sine_amplitude)", "default": {}},
            "years": {"type": "array", "description": "Years this template applies to; omit or pass [] for a year-agnostic preset", "default": None}
        }
    },
    "update_global_split": {
        "name": "update_global_split",
        "description": "Updates an existing Global Split Template. Only provided fields are changed.",
        "parameters": {
            "split_id": {"type": "integer", "description": "Global split template ID"},
            "name": {"type": "string", "description": "New name", "default": None},
            "repartition_logic": {"type": "string", "description": "Month, Quarter, or Week", "default": None},
            "repartition_values": {"type": "object", "description": "Per-period weight percentages", "default": None},
            "distribution_profile": {"type": "string", "description": "New distribution curve", "default": None},
            "profile_params": {"type": "object", "description": "New curve parameters", "default": None},
            "years": {"type": "array", "description": "New set of years ([] to make it a year-agnostic preset)", "default": None}
        }
    },
    "delete_global_split": {
        "name": "delete_global_split",
        "description": "Deletes a Global Split Template.",
        "parameters": {
            "split_id": {"type": "integer", "description": "Global split template ID"}
        }
    },
    "get_curve_weight_suggestions": {
        "name": "get_curve_weight_suggestions",
        "description": "Computes suggested per-period weight percentages for a distribution curve, matching what the repartition engine would actually produce -- useful as a starting point before creating/editing a Global Split Template.",
        "parameters": {
            "profile": {"type": "string", "description": "Distribution curve, e.g. annual_progressive"},
            "logic": {"type": "string", "description": "Month, Quarter, or Week"},
            "year": {"type": "integer", "description": "Optional year (affects week-count for Week logic)", "default": None}
        }
    },
    "get_kpi_global_split": {
        "name": "get_kpi_global_split",
        "description": "Returns the Global Split Template(s) currently assigned to a KPI from KPI Explorer.",
        "parameters": {
            "kpi_id": {"type": "integer", "description": "KPI spec ID"}
        }
    },
    "set_kpi_global_split": {
        "name": "set_kpi_global_split",
        "description": (
            "Assigns (or clears, if global_split_id is null) the Global Split Template used to "
            "repartition a KPI's targets. This is the KPI Explorer assignment -- the authoritative "
            "source the repartition engine uses, overriding any legacy per-target override."
        ),
        "parameters": {
            "kpi_id": {"type": "integer", "description": "KPI spec ID"},
            "global_split_id": {"type": "integer", "description": "Global split template ID, or null to clear", "default": None}
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
        kpi_id = arguments["kpi_id"]
        target_number = arguments.get("target_number", 1)
        annual_management.save_annual_targets(
            year=arguments["year"],
            plant_id=arguments["plant_id"],
            targets_data_map={
                str(kpi_id): {
                    "targets": [{
                        "target_number": target_number,
                        "target_value": float(arguments["value"]),
                        "is_manual": True,
                    }]
                }
            },
            initiator_kpi_spec_id=kpi_id,
            changed_by=arguments.get("changed_by", "mcp_agent"),
        )
        return {"status": "success"}
    elif name == "get_annual_target":
        return data_retriever.get_annual_target_entry(
            year=arguments["year"], plant_id=arguments["plant_id"], kpi_id=arguments["kpi_id"]
        )
    elif name == "get_periodic_targets":
        return data_retriever.get_periodic_targets_for_kpi(
            year=arguments["year"],
            plant_id=arguments["plant_id"],
            kpi_id=arguments["kpi_id"],
            period_type=arguments["period_type"],
            target_number=arguments.get("target_number", 1),
        )
    elif name == "get_periodic_targets_all_plants":
        return data_retriever.get_periodic_targets_for_kpi_all_plants(
            kpi_spec_id=arguments["kpi_id"], period_type=arguments["period_type"], year=arguments.get("year")
        )
    elif name == "update_kpi_spec":
        success = kpi_crud.update_kpi_spec_extended(
            kpi_id=arguments["kpi_id"],
            data_updates=arguments.get("data_updates", {}),
            changed_by=arguments.get("changed_by", "mcp_agent"),
        )
        return {"status": "success", "kpi_id": arguments["kpi_id"], "updated": success}
    elif name == "list_kpis":
        return data_retriever.get_all_kpis_detailed(
            only_visible=arguments.get("only_visible", False), plant_id=arguments.get("plant_id")
        )
    elif name == "list_plants":
        return data_retriever.get_all_plants(visible_only=arguments.get("visible_only", False))
    elif name == "list_units_of_measure":
        return kpi_crud.get_all_units_of_measure()
    elif name == "create_unit_of_measure":
        return kpi_crud.add_unit_of_measure(arguments["name"])
    elif name == "list_global_splits":
        return splits_crud.get_all_global_splits(year=arguments.get("year"))
    elif name == "get_global_split":
        return splits_crud.get_global_split(arguments["split_id"])
    elif name == "create_global_split":
        split_id = splits_crud.add_global_split(
            name=arguments["name"],
            repartition_logic=arguments["repartition_logic"],
            repartition_values=arguments.get("repartition_values", {}),
            distribution_profile=arguments["distribution_profile"],
            profile_params=arguments.get("profile_params", {}),
            years=arguments.get("years"),
        )
        return {"split_id": split_id, "name": arguments["name"]}
    elif name == "update_global_split":
        split_id = arguments["split_id"]
        kwargs = {k: v for k, v in arguments.items() if k != "split_id" and v is not None}
        splits_crud.update_global_split(split_id, **kwargs)
        return {"status": "success", "split_id": split_id}
    elif name == "delete_global_split":
        splits_crud.delete_global_split(arguments["split_id"])
        return {"status": "success", "split_id": arguments["split_id"]}
    elif name == "get_curve_weight_suggestions":
        return splits_crud.get_curve_weight_suggestions(
            profile=arguments["profile"], logic=arguments["logic"], year=arguments.get("year")
        )
    elif name == "get_kpi_global_split":
        kpi = data_retriever.get_kpi_detailed_by_id(arguments["kpi_id"])
        indicator_id = kpi["indicator_id"] if kpi else arguments["kpi_id"]
        return splits_crud.get_global_splits_for_indicator(indicator_id)
    elif name == "set_kpi_global_split":
        kpi = data_retriever.get_kpi_detailed_by_id(arguments["kpi_id"])
        if not kpi:
            raise ValueError(f"KPI {arguments['kpi_id']} not found")
        splits_crud.set_kpi_global_split(kpi["indicator_id"], arguments.get("global_split_id"))
        return {"status": "success", "kpi_id": arguments["kpi_id"], "global_split_id": arguments.get("global_split_id")}
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
