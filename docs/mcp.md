# MCP server

`src/mcp_server.py` lets AI agents work with the KPI data through the [Model Context Protocol](https://modelcontextprotocol.io). It's built on the official `mcp` Python SDK, so any MCP client can connect, including Claude Desktop, Claude Code and the SDK's own `Client`.

It exposes **everything the REST API does**: 60 tools that call the same core functions with the same validation and the same role rules. `tests/test_mcp_server.py::test_every_rest_route_has_an_mcp_tool` keeps the two in sync: a new REST route fails the test until it is mapped to a tool, or explicitly excluded.

## Transports and identity

| | stdio (default) | Streamable HTTP |
|---|---|---|
| Start | `python src/mcp_server.py` (a client launches it) | `python src/mcp_server.py --http`, or the `mcp_server` container |
| Endpoint | the process's stdin/stdout | `http://<MCP_HOST>:<MCP_PORT>/mcp` (default `127.0.0.1:8001`) |
| Authentication | none: whoever can start it already has the database files | `Authorization: Bearer <api key>` on every request |
| `changed_by` on writes | `$MCP_STDIO_USER` (default `mcp_agent`) | the API key's owner. Callers can't claim another name. |
| Admin tools | allowed unless `MCP_STDIO_ADMIN=false` | only if the key's owner is an admin. The role is re-read on every call. |

Both transports run the database migrations on start.

Details of the HTTP transport:
- It is stateless, and answers with JSON responses.
- When it binds to a non-loopback address, DNS-rebinding protection only accepts the `Host` headers listed in `MCP_ALLOWED_HOSTS` (default `localhost:*,127.0.0.1:*`). Add your host name there when you expose the server.
- `GET /health` is unauthenticated, for container healthchecks.

**API keys** belong to a user. Create one in the app under **Data Utilities → MCP API keys**, or with `POST /users/{id}/api-keys` or the `create_api_key` tool. The raw key (`kpi_mcp_...`) is shown once; only a hash is stored. Revoking a key, or deactivating its owner, stops it working immediately.

Login sessions and API keys are separate credentials: a session token from `/auth/login` doesn't work against the MCP server, and an API key doesn't work against the REST API.

## Connecting a client

**Claude Code over stdio:**
```bash
claude mcp add kpi --env MCP_STDIO_USER=claude-code -- /path/to/dataentryKPI/.venv/bin/python /path/to/dataentryKPI/src/mcp_server.py
```

**Claude Code over HTTP:**
```bash
claude mcp add --transport http kpi http://127.0.0.1:8001/mcp --header "Authorization: Bearer kpi_mcp_..."
```

**Claude Desktop** (`claude_desktop_config.json`, stdio):
```json
{
  "mcpServers": {
    "kpi": {
      "command": "C:\\path\\to\\dataentryKPI\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\dataentryKPI\\src\\mcp_server.py"],
      "env": { "MCP_STDIO_USER": "claude-desktop" }
    }
  }
}
```

**Python SDK:**
```python
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

http = httpx2.AsyncClient(headers={"Authorization": "Bearer kpi_mcp_..."})
async with Client(streamable_http_client("http://127.0.0.1:8001/mcp", http_client=http)) as client:
    kpis = await client.call_tool("list_kpis", {})
```

## Conventions

- **`kpi_id` is the KPI's spec id**, the `id` field returned by `list_kpis` and `get_kpi`. Formulas reference KPIs the same way: `"[3] / [4]"`.
- **Saving cascades.** Saving a target, changing a formula or aggregation type, or editing or assigning a split template all recalculate the affected formula KPIs and their day, week, month and quarter targets, in one transaction.
- **Weights** are percentages keyed by month name (`"January"`), `"Q1"`..`"Q4"`, or ISO week `"W01"`..`"W53"`. They are the same keys `analyze_seasonality` returns.
- **Errors** come back as tool errors with a readable message, for example `KPI 9999 not found` or `Formula would create a dependency cycle: [2] -> [4] -> [2]`. Unexpected crashes only report `Error executing tool <name>`; the details go to the server log.
- Every tool carries **annotations** (`readOnlyHint`, `destructiveHint`, `idempotentHint`) so clients can ask for confirmation before destructive calls.

## Tools

### KPIs and hierarchy
| Tool | What it does |
|---|---|
| `get_kpi_tree` | Folder hierarchy with each folder's KPIs (`root_id`, `depth` optional) |
| `add_kpi_node` | Create a folder (top level, or under `parent_id`) |
| `create_kpi_indicator` | Create a KPI: aggregation type, unit, direction, thresholds, target count, actuals time filter |
| `list_kpis` | Active KPIs (optionally only visible ones, or those enabled for a plant) |
| `get_kpi` | One KPI's full definition |
| `update_kpi_spec` | Change definition fields, including `formula_string` and `target_labels` |
| `soft_delete_kpi` | Hide a KPI everywhere (targets, actuals and history are kept) |
| `get_kpi_definition_history` | Who created or changed the KPI, when, and the old and new values |
| `get_kpi_target_history` | Every change to the KPI's annual target values |
| `get_kpi_visibility` / `set_kpi_visibility` | Per-plant enable/disable overrides |
| `list_units_of_measure` / `create_unit_of_measure` | The units registry |

### Facilities
| Tool | What it does |
|---|---|
| `list_plants` | Facilities |
| `create_plant` / `update_plant` | Add or edit a facility (`update_plant` keeps omitted fields) |
| `delete_plant` | Delete a facility. It refuses if the facility has data, unless `force=true`, which deletes the data too. |

### Targets
| Tool | What it does |
|---|---|
| `update_target_value` | Set one KPI's annual target for one plant and year |
| `save_annual_targets` | Save several KPIs at once, for one plant or a list of plants, optionally with repartition settings |
| `get_annual_target` | One KPI's annual record with every scenario's value |
| `list_annual_targets` | All annual records for a plant and year |
| `get_available_target_numbers` | Which scenarios have values |
| `list_years` | Years that have targets |
| `get_periodic_targets` | Day, week, month, quarter or year targets for one plant, in chronological order |
| `get_periodic_targets_all_plants` | The same, across all plants |
| `get_lean_targets` | Every periodic target as flat BI rows |

### Actuals and performance
| Tool | What it does |
|---|---|
| `record_actual` | Record (or overwrite) a measured value for a KPI, plant and day |
| `list_actuals` | Measured values, optionally between two dates |
| `get_performance_status` | Latest actual against target: `on_track`, `warning` or `out_of_range`, with the trend. The target is the stored one for that day and scenario (`target_number`, default 1) unless `target_value` is passed, and the tool fails if none is stored. |

### Split templates
| Tool | What it does |
|---|---|
| `list_global_splits` / `get_global_split` | Templates (with `year`: those covering it) |
| `create_global_split` / `update_global_split` | Create or edit a template. `kpi_ids` sets which KPIs use it, and affected KPIs are recalculated. |
| `delete_global_split` | Delete a template. Its KPIs fall back to an even split. |
| `get_global_split_kpis` / `set_global_split_kpis` | Which KPIs a template is linked to |
| `get_kpi_global_split` / `set_kpi_global_split` | A KPI's template (null clears it) |
| `get_curve_weight_suggestions` | Starting weights for a curve (progressive, sinusoidal, ...) |

### Seasonality predictor
| Tool | What it does |
|---|---|
| `analyze_seasonality` | Race OLS, Ridge and Random Forest on historical data. Pass `csv_text`, or `file_base64` plus `filename` for Excel. Returns weights ready for `create_global_split`, along with coefficients, R² and the 5–95% band. Capped at `MAX_UPLOAD_MB`; runs in a worker thread. |

### KPI templates
| Tool | What it does |
|---|---|
| `list_templates` / `create_template` / `delete_template` | Reusable sets of KPI definitions |
| `list_template_indicators` / `add_template_indicator` / `update_template_indicator` / `remove_template_indicator` | The definitions in a template. Changes propagate to folders that use it. |
| `apply_template` | Link a folder to a template and create its KPIs there |

### Data
| Tool | What it does |
|---|---|
| `export_csv` | One human-readable table as CSV text: Plants, KPI Hierarchy, KPI Definitions, Plant Visibility, Annual Targets, Periodic Targets, Lean Targets |
| `export_backup` | Full backup as a base64 ZIP (user accounts excluded) |
| `restore_backup` | **Admin only.** Replace all KPI data with a backup, after snapshotting the current databases |

### Users and API keys
| Tool | What it does |
|---|---|
| `whoami` | The account this connection acts as, and the transport |
| `list_users` | Admins get full profiles; others get id, name, colour and active flag |
| `create_user` | **Admin only.** Create an account |
| `update_user` | Edit a profile. Users can edit their own name, email and colour. Admins can edit anyone, including `is_active` (deactivating revokes sessions and keys) and `is_admin`. |
| `reset_user_password` | **Admin only.** Set a new password and sign the user out everywhere |
| `change_my_password` | Change the key owner's password (HTTP only) |
| `list_api_keys` / `create_api_key` / `revoke_api_key` | Your own keys, or anyone's as an admin. `raw_key` is returned once. |

### Deliberately not exposed
- `POST /auth/register`, `/auth/login`, `/auth/logout` and `GET /auth/status`: these manage browser sessions, and MCP authenticates with API keys instead.
- `GET/POST /targets`: the deprecated flat target table, which repartition doesn't use.

## Example session

Typical agent workflow:
1. `whoami`, then `list_plants` and `list_kpis` to learn the ids.
2. `save_annual_targets` with `{"year": 2026, "plant_id": [1, 2], "targets_by_kpi": {"1": {"targets": [{"target_number": 1, "target_value": 120000}]}}}`.
3. `get_periodic_targets` with `{"kpi_id": 1, "plant_id": 1, "year": 2026, "period_type": "Month"}` to read the monthly split back.
4. `analyze_seasonality` on last year's sales, `create_global_split` with the returned `weights` and `kpi_ids: [1]`. The KPI's targets are recalculated straight away.
