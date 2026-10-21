# REST API reference

The FastAPI backend (`src/api.py`) is the source of truth for request and response shapes. Every route is documented interactively in **Swagger UI at `/docs`** (ReDoc at `/redoc`). To call protected routes from Swagger UI:
1. Use **POST /auth/login** to get a token.
2. Click **Authorize** and paste the token.

This page maps the routes to what they do and who may call them. AI agents should use the [MCP server](mcp.md), which exposes the same features as tools.

## Authentication and roles

- **Sessions.** Every route needs `Authorization: Bearer <session token>`, except `/`, `/health`, `/auth/status`, `/auth/register`, `/auth/login`, `/auth/logout` and the docs routes.
  - This is enforced by one HTTP middleware, so a new route can't accidentally ship unauthenticated.
  - Tokens come from `/auth/login` or `/auth/register` and last 30 days. Only their SHA-256 hash is stored.
- **Passwords** use PBKDF2-HMAC-SHA256 with 260,000 iterations and a per-user salt. They must be 8–256 characters.
- **Roles.**
  - The first account ever created is the **admin**.
  - Self-registration then closes, unless `ALLOW_REGISTRATION=true`, which lets people register *non-admin* accounts.
  - Admins can create users, edit anyone (including `is_active` and `is_admin`), reset passwords, manage anyone's API keys, and restore backups.
  - Everyone else can edit only their own profile and keys.
  - The last active admin can't be demoted or deactivated.
  - These rules live in `src/user_management/access.py` and are shared with the MCP server. A violation returns **403**.
- **Login throttling.** Failed logins are rate-limited per client and name (8) and per client (40) in a 15-minute window, returning **429**. Unknown names cost the same hashing time as known ones.
- **Password changes and deactivation.** Changing your password signs out your other sessions. Deactivating a user revokes their sessions and API keys.
- **Audit identity.** Writes record `changed_by` from the session, never from the request body.
- **CORS** only allows `CORS_ORIGINS`. The bundled frontend calls the API same-origin through its `/api` proxy, so it doesn't need CORS.
- **Errors.** Invalid input returns 400 or 422 with a `detail` message. Unexpected errors return a generic 500, and the traceback stays in the server log.

## Auth

| Route | Notes |
|---|---|
| `GET /auth/status` | Public. `{has_users, registration_open}`, used by the login screen. |
| `POST /auth/register` | Public. `{name, password, email?, color?}`. Creates an account and returns `{token, expires_at, user}`. 403 when registration is closed. |
| `POST /auth/login` | Public. `{name, password}`, returns `{token, expires_at, user}` |
| `POST /auth/logout` | Revokes the presented token |
| `GET /auth/me` | The signed-in user (includes `is_admin`) |
| `POST /auth/change-password` | `{current_password, new_password}`. Signs out your other sessions. |

## KPIs and hierarchy

`kpi_id` is the KPI's spec id: the `id` from `GET /kpis`.

| Route | Notes |
|---|---|
| `GET /kpis` | Active KPIs. `?only_visible=` and `?plant_id=` (omits KPIs disabled for that plant). |
| `GET /kpis/tree` | Folder hierarchy with KPIs. `?root_id=&depth=` |
| `GET /kpis/{id}` | One KPI (404 if missing or deleted) |
| `POST /kpis` | Create a KPI in a folder: `{node_id, name, calculation_type, unit_of_measure, direction, threshold_json, target_count, ...}` |
| `PUT /kpis/{id}` | `{data_updates: {...}}`. Only the fields in `kpi_crud.UPDATABLE_SPEC_FIELDS`. A `formula_string` is validated (syntax, known KPIs, no cycles). Formula, aggregation-type and target-count changes recalculate stored targets. |
| `DELETE /kpis/{id}` | Soft delete: hidden everywhere, data kept |
| `POST /kpis/nodes` | Create a folder `{name, parent_id?}` |
| `GET /kpis/{id}/status` | `?plant_id=&target_number=&target_value=`. Latest actual against the stored target for that day and scenario (`target_number`, default 1), and the trend. `target_value` overrides it; 404 if there is no stored target. |
| `GET /kpis/{id}/history` | Definition audit trail |
| `GET /kpis/{id}/target-history` | Target value audit trail, `?plant_id=` |
| `GET` / `PUT /kpis/{id}/visibility` | Per-plant enable/disable overrides `[{plant_id, is_enabled}]` |
| `GET /kpis/{id}/global-splits` | The split template assigned to the KPI |
| `PUT /kpis/{id}/global-split` | `{global_split_id}` (null clears it). Recalculates the KPI. |
| `GET` / `POST /units-of-measure` | Units registry |

## Facilities

| Route | Notes |
|---|---|
| `GET /plants` | `?visible_only=` |
| `POST /plants` | `{name, description?, visible?, color?}`. 409 if the name exists. |
| `PUT /plants/{id}` | Full update |
| `DELETE /plants/{id}` | 409 if the plant has targets or actuals, unless `?force=true` (which deletes them too) |

## Targets

| Route | Notes |
|---|---|
| `POST /targets/annual` | **The save path.** `{year, plant_id: int or [int], targets_data_map: {"<kpi_id>": {targets: [{target_number, target_value}], repartition_logic?, repartition_values?, distribution_profile?, profile_params?, global_split_id?}}}`. Blank (`null`) values are left unchanged. Values for calculated KPIs are rejected. Everything (values, audit rows, formula KPIs, periodic targets) is committed in one transaction. |
| `GET /targets/annual-entry` | `?year=&plant_id=&kpi_id=`. The annual record with every scenario's value. |
| `GET /targets/annual` | `?plant_id=&year=`. All KPIs' annual records. |
| `GET /targets/available-numbers` | Scenario numbers that have values |
| `GET /kpis/{id}/periodic-targets` | `?plant_id=&year=&period_type=Day\|Week\|Month\|Quarter\|Year&target_number=`. Returns `[{period, target_value}]` in chronological order; an unknown `period_type` returns 400. |
| `GET /kpis/{id}/periodic-targets/all-plants` | The same across plants (`plant_id`, `plant_name`, `target_number`, `period`, `target_value`) |
| `GET /targets/lean` | Every periodic target as flat rows for BI tools |
| `GET` / `POST /targets` | *Deprecated.* A legacy flat target table that repartition doesn't use. |

## Actuals

| Route | Notes |
|---|---|
| `POST /actuals` | `{kpi_id, plant_id, measurement_date: YYYY-MM-DD, actual_value}`. Upserts per day. |
| `GET /actuals` | `?kpi_id=&plant_id=&start_date=&end_date=` |

## Split templates

| Route | Notes |
|---|---|
| `GET /global-splits` | `?year=` limits the list to templates covering that year (year-agnostic ones are always included) |
| `GET /global-splits/curve-preview` | `?profile=&logic=&year=`. Suggested starting weights. |
| `GET /global-splits/{id}` | One template |
| `POST /global-splits` | `{name, repartition_logic, repartition_values, distribution_profile, profile_params?, years?, afflicted_indicators?}` |
| `PUT /global-splits/{id}` | Partial update. Every KPI using the template, before or after the change, is recalculated. |
| `DELETE /global-splits/{id}` | Its KPIs fall back to an even split and are recalculated |
| `GET` / `PUT /global-splits/{id}/indicators` | Linked indicators `[{indicator_id, override_distribution_profile?}]` |

Weights are percentages keyed by month name, `Q1`..`Q4`, or `W01`..`W53`.

## Seasonality predictor

`POST /analysis/multivariate` takes a multipart form:

| Field | Value |
|---|---|
| `file` | `.csv` or `.xlsx`, at most `MAX_UPLOAD_MB` |
| `target_cols` | Comma-separated target columns |
| `feature_cols` | Optional driver columns |
| `date_col` | The date column |
| `period_type` | `Month`, `Quarter` or `Week` |

It returns `{weights, coefficients, r_squared, plot_data, winning_model, period_type}`. The `weights` are ready to be posted as a template's `repartition_values`. The work runs in FastAPI's thread pool, so other requests aren't blocked.

## KPI definition templates

| Route | Notes |
|---|---|
| `GET` / `POST /templates` | List or create (`{name, description?}`) |
| `DELETE /templates/{id}` | Unlinks its folders. KPIs created from it are kept. |
| `GET` / `POST /templates/{id}/indicators` | Definitions in a template. Adding one creates the KPI in every linked folder. |
| `PUT` / `DELETE /templates/indicators/{definition_id}` | Edit or remove. Changes propagate; removal soft-deletes the KPIs created from it. |
| `POST /templates/{id}/apply` | `{node_id}`. Links a folder and creates the KPIs. |

## Data utilities

| Route | Notes |
|---|---|
| `GET /years` | Years with targets |
| `GET /export/lean` | Lean CSV |
| `GET /export/csv/{table_key}` | `Plants`, `KPI Hierarchy`, `KPI Definitions`, `Plant Visibility`, `Annual Targets` or `Periodic Targets`. Human-readable, **not** restorable. |
| `GET /export/all` | Raw backup ZIP: every table 1:1 plus a manifest, NULL written as `\N`. User accounts are excluded. |
| `POST /import/restore` | **Admin only.** Multipart `file`. Validates the ZIP (known files, size cap, columns), snapshots the databases to `databases/backups/pre-restore-<timestamp>/`, then **replaces** the contents of every table in the backup, in one transaction. Returns `{tables, snapshot, warnings}`. |

## Users and MCP API keys

| Route | Who | Notes |
|---|---|---|
| `GET /users` | anyone | Admins get full profiles; others get id, name, colour and active flag |
| `POST /users` | admin | `{name, password, email?, color?, is_admin?}` |
| `PUT /users/{id}` | self or admin | `{name, email?, color?, is_active?, is_admin?}`. Only admins can change `is_active` and `is_admin`. |
| `POST /users/{id}/reset-password` | admin | `{new_password}`. Signs the user out everywhere. |
| `GET /users/{id}/api-keys` | self or admin | Prefix, label, last use. Never the key itself. |
| `POST /users/{id}/api-keys` | self or admin | `{label}`, returns `{raw_key, ...}` **once** |
| `DELETE /api-keys/{id}` | key owner or admin | Revokes immediately |

Login sessions (`sessions` table) and MCP API keys (`api_keys`) are separate credentials: neither works in place of the other. See [mcp.md](mcp.md).

## System

`GET /health` is public and returns `{status, version}`.
