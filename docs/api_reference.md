# REST & MCP API Reference

The FastAPI backend (`src/api.py`) is the single source of truth for request/response shapes — every endpoint below is documented interactively at **`http://localhost:8000/docs`** (Swagger UI) once the backend is running. This page is a map of what exists and which underlying function it calls, so you know where to look in the code.

CORS is wide open (`allow_origins=["*"]`). **Every route requires a valid session** (`Authorization: Bearer <token>`, minted by `/auth/login` or `/auth/register`) except the auth endpoints themselves, `/health`, and the docs routes — enforced by an `@app.middleware("http")` gate, not by decorating each route individually, so nothing can accidentally ship unauthenticated. Swagger UI's "Try it out" doesn't have a security-scheme "Authorize" button wired up (the gate is header-based middleware, not a FastAPI `Security()` dependency), so to call a protected endpoint from `/docs` you'd need to add the `Authorization` header manually per request.

Handlers that log `changed_by` (KPI spec/target edits) derive it from the authenticated session via `Depends(get_current_user)` — they do **not** trust a `changed_by` value in the request body. This is the same "identity comes from the token, not the caller's claim" rule the MCP HTTP transport uses (see below).

## Auth

| Endpoint | Calls | Notes |
|---|---|---|
| `POST /auth/register` | `user_management.crud.add_user` + `create_session` | `{name, password, email?, color?}` — 8+ char password, creates the account and logs it in (returns a token) in one call. Public. |
| `POST /auth/login` | `verify_password` + `create_session` | `{name, password}` → `{token, expires_at, user}`. Public. |
| `POST /auth/logout` | `revoke_session` | Public (reads the token itself; a bogus/expired token is a harmless no-op). |
| `GET /auth/me` | `get_current_user` | Returns the authenticated user — what the frontend calls on load to verify a stored session is still valid. |
| `POST /auth/change-password` | `change_password` | `{current_password, new_password}` — verifies the current password first. |

Sessions: `secrets.token_urlsafe(32)`, only the SHA-256 hash is stored (`sessions` table), 30-day expiry (`user_management.crud.SESSION_TTL_DAYS`). Passwords: PBKDF2-HMAC-SHA256, 260,000 iterations, random 16-byte salt per user (`hashlib`, no extra dependency).

## KPIs & Hierarchy

| Endpoint | Calls | Notes |
|---|---|---|
| `GET /kpis` | `data_retriever.get_all_kpis_detailed` | `?only_visible=&plant_id=` |
| `GET /kpis/tree` | `kpi_crud.get_kpi_tree` | Recursive hierarchy, `?root_id=&depth=` |
| `GET /kpis/{id}` | `data_retriever.get_kpi_detailed_by_id` | |
| `POST /kpis` | `kpi_crud.create_kpi_indicator` | Creates the indicator + its spec in one call; `changed_by` is the authenticated user |
| `PUT /kpis/{id}` | `kpi_crud.update_kpi_spec_extended` | `{data_updates: {...}}` — any subset of the `kpis` columns (including `target_labels`, a JSON string like `{"1": "Budget", "2": "Committed"}`), logs to history as the authenticated user |
| `DELETE /kpis/{id}` | `kpi_crud.soft_delete_kpi` | Sets `is_active=0`, preserves history |
| `POST /kpis/nodes` | `kpi_crud.add_kpi_node` | New Group/Subgroup/Folder |
| `GET /kpis/{id}/status` | `data_retriever.get_kpi_performance_status` | Actual vs. target, threshold status, trend |
| `GET /kpis/{id}/history` | `history_service.get_definition_history` | Spec edit audit trail |
| `GET /kpis/{id}/target-history` | `history_service.get_target_history` | Target value edit audit trail, `?plant_id=` |
| `GET`/`PUT /kpis/{id}/visibility` | `kpi_management.visibility.*` | Per-plant visibility overrides |

## Plants

| Endpoint | Calls |
|---|---|
| `GET /plants` | `data_retriever.get_all_plants` (`?visible_only=`) |
| `POST /plants` | `plants_management.crud.add_plant` |
| `PUT /plants/{id}` | `plants_management.crud.update_plant` |
| `DELETE /plants/{id}` | `plants_management.crud.delete_plant` (`?force=` to delete even if referenced by targets) |

## Targets & Repartition

> There are two target systems (see [database_schema.md](database_schema.md)). **`/targets/annual`** is the one that actually drives repartition — use it unless you specifically need the flat `/targets` table.

| Endpoint | Calls | Notes |
|---|---|---|
| `GET /targets/annual-entry` | `data_retriever.get_annual_target_entry` | `?year=&plant_id=&kpi_id=` — the annual record + all its `target_number` values |
| `GET /targets/annual` | `data_retriever.get_annual_targets` | All KPIs' annual records for a `plant_id`+`year` |
| `POST /targets/annual` | `target_management.annual.save_annual_targets` | **Primary save path.** `plant_id` may be a single ID or a list (broadcast). Logs history, cascades formula recalculation, triggers repartition in dependency order. |
| `GET /targets/available-numbers` | `data_retriever.get_available_target_numbers_for_kpi` | Which `target_number`s exist for a KPI/plant/year |
| `GET /kpis/{id}/periodic-targets` | `data_retriever.get_periodic_targets_for_kpi` | One KPI/plant, `?period_type=Day|Week|Month|Quarter|Year&target_number=` |
| `GET /kpis/{id}/periodic-targets/all-plants` | `data_retriever.get_periodic_targets_for_kpi_all_plants` | Same, across every plant — used for the Analysis chart |
| `GET`/`POST /targets` | `data_retriever.get_modern_kpi_targets` / `kpi_crud.update_target_value` | The flat, non-repartitioned system |
| `GET /targets/lean` | `data_retriever.get_lean_targets` | Minimal flat export for BI tools |

## Global Splits

Standard CRUD at `/global-splits`, `/global-splits/{id}`, `/global-splits/{id}/indicators` (affiliated indicators + per-indicator profile override), `/kpis/{id}/global-splits` (splits affiliated with one KPI) — all thin wrappers over `kpi_management.splits`.

## Multivariate Seasonality Predictor

`POST /analysis/multivariate` — multipart upload (`file`, `target_cols`, `feature_cols`, `date_col`, `period_type`). Calls `services.split_analyzer.analyze_seasonality_from_file`, which races OLS/Ridge/RandomForest with cross-validation and a Monte Carlo confidence band, and returns `{weights, coefficients, r_squared, plot_data, winning_model}`. The frontend lets you publish the result straight into a new Global Split.

## Templates

Standard CRUD at `/templates`, `/templates/{id}/indicators`, `/templates/indicators/{def_id}` — KPI *definition* templates (`kpi_management.templates`), not to be confused with Global Split templates above.

## Data Utilities

| Endpoint | Calls | Notes |
|---|---|---|
| `GET /years` | `data_retriever.get_distinct_years` | |
| `GET /export/lean` | `export_manager.export_lean_data_to_csv` | |
| `GET /export/csv/{table_key}` | `export_manager.export_single_table` | `table_key` ∈ Plants / KPI Hierarchy / KPI Definitions / Plant Visibility / Annual Targets / Periodic Targets — human-readable, **not** restorable |
| `GET /export/all` | `export_manager.export_raw_backup_csvs` + `package_all_csvs_as_zip` | Raw per-table dump, ZIP — this is the restorable format |
| `POST /import/restore` | `import_manager.import_from_zip` | Multipart ZIP upload; `INSERT OR IGNORE` per table in FK-safe order, idempotent |

## Users & MCP API Keys

| Endpoint | Calls | Notes |
|---|---|---|
| `GET /users` | `user_management.crud.get_all_users` | `?active_only=` |
| `POST /users` | `add_user` | `{name, password, email?, color?}` — admin-style creation (same requirements as `/auth/register`, but doesn't log the caller in); requires a valid session like everything else, so only a logged-in user can create another account |
| `PUT /users/{id}` | `update_user` | Name/email/color/active — does not touch the password; use `/auth/change-password` for that |
| `GET /users/{id}/api-keys` | `list_api_keys` | Never returns the raw key, only `key_prefix` |
| `POST /users/{id}/api-keys` | `create_api_key` | `{label}` → `{raw_key, ...}` — **shown once**, store it now |
| `DELETE /api-keys/{id}` | `revoke_api_key` | Soft-revoke (`is_active=0`), key stays listed |

Note the naming: `api_keys` (long-lived, MCP-only, tied to a user) and `sessions` (30-day, login-only) are separate tables and mechanisms — see [database_schema.md](database_schema.md).

## MCP Server (`src/mcp_server.py`)

Two transports, same tool registry and dispatcher underneath:

- **stdio** (default: `python src/mcp_server.py`) — one JSON-RPC 2.0 request per line on stdin, response on stdout. No authentication; intended for a local client (e.g. Claude Desktop) that spawns the process directly. `changed_by` in tool arguments is whatever the caller sends (default `"mcp_agent"`).
- **HTTP** (`python src/mcp_server.py --http`, or `MCP_TRANSPORT=http`) — `POST /mcp` on port 8001 (`MCP_PORT`), body is a JSON-RPC 2.0 request, requires `Authorization: Bearer <api_key>`. The key is resolved via `user_management.crud.validate_api_key`; the resolved user's `name` **overwrites** any `changed_by` the caller sent, so a compromised/misused key can't misattribute its own writes. `GET /health` for container healthchecks. This is what the `mcp_server` container in `compose.yml` runs.

### Tools

| Tool | Wraps |
|---|---|
| `get_kpi_tree` | `kpi_crud.get_kpi_tree` |
| `add_kpi_node` | `kpi_crud.add_kpi_node` |
| `create_kpi_indicator` | `kpi_crud.create_kpi_indicator` |
| `update_target_value` | `kpi_crud.update_target_value` (the flat `kpi_targets` system, not `/targets/annual` — no repartition) |
| `get_performance_status` | `data_retriever.get_kpi_performance_status` |
| `soft_delete_kpi` | `kpi_crud.soft_delete_kpi` |

`tools/list` returns the full JSON Schema for each tool's parameters; `tools/call` invokes one.
