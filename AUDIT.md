# Application Audit: Data Entry KPI Target Manager

**Date:** 2026-10-02/03
**Scope:** whole repository, at v2.0.0 (commit `d49bb80`)
**Branch with fixes:** `audit-fixes`

## How this audit was done

1. **Static review** of every tracked file:
   - backend core;
   - REST API and auth;
   - MCP server;
   - React frontend;
   - containers and packaging;
   - tests;
   - docs;
   - legacy GUIs.
2. **Runtime testing.** I ran the full `compose.yml` stack under Podman (project `kpiaudit`, on a fresh volume). Then I:
   - seeded it with `scripts/seed_demo.py`;
   - went through every tab of the React app in a browser;
   - exercised the REST and MCP endpoints directly.
3. **Harmless proofs** of each security finding, run against that local stack only. For example, the formula escape only *counts* Python classes.

**Severity scale**

| Severity | Meaning |
|---|---|
| **Critical** | Remote code execution or injection |
| **High** | Data corruption, broken core feature, or authorization bypass |
| **Medium** | Wrong behaviour with a workaround, hardening, or operational risk |
| **Low** | Polish, hygiene, or docs |

The **Status** column shows the state after the `audit-fixes` branch (see the bottom of this file).

---

## Security

| ID | Sev | Finding | Location | Evidence | Status |
|---|---|---|---|---|---|
| SEC-01 | Critical | **Formula `eval` sandbox escape (RCE).** `eval(expr, {"__builtins__": None}, ...)` is not a sandbox. Any logged-in user can submit a formula, through `PUT /kpis/{id}` (`formula_string`), the `formula` field of `POST /targets/annual`, or MCP. | `target_management/annual.py:43`, `target_management/repartition.py:44` | Runtime: as a non-admin, saved the formula `().__class__.__base__.__subclasses__().__len__()`. The target stored **1529.0**, which shows arbitrary object traversal. | Open |
| SEC-02 | Critical | **SQL injection over MCP.** `update_global_split` forwards every argument key to `splits.update_global_split(**kwargs)`, which pastes each key into SQL as a column name. | `mcp_server.py:341`, `kpi_management/splits.py:57-70` | Runtime: the injected `changed_by` key reached SQL (`no such column: changed_by`). | Open |
| SEC-03 | High | **No authorization layer.** Any user can mint an MCP key for *any* user (and so impersonate them), list or revoke anyone's keys, rename or deactivate any user, and restore the whole database. | `api.py:699-751` | Runtime: `demo-user` minted a key for `demo-admin`, then wrote a target through MCP. The audit trail recorded **`changed_by = demo-admin`**. `demo-user` then revoked `demo-admin`'s key. | Open |
| SEC-04 | High | **Open self-registration.** Anyone who can reach `:8000` can create an account. Combined with SEC-01, that means anyone on the network gets code execution. | `api.py:47,232` | Runtime: an extra account was registered from the browser while the stack was up. | Open |
| SEC-05 | Medium | **Login weaknesses.**<br>• No rate limit or lockout.<br>• Timing-based user enumeration: no hash is computed for unknown names.<br>• Changing the password doesn't revoke other sessions.<br>• Deactivating a user doesn't revoke their API keys (they stay valid until checked). | `user_management/crud.py:88-123` | Code | Open |
| SEC-06 | Medium | **Exposure.**<br>• CORS is `*`.<br>• Backend (`:8000`) and MCP (`:8001`) are published on every host interface.<br>• Containers run as root.<br>• nginx sends no security headers or CSP. | `api.py:27-33`, `compose.yml`, `Dockerfile`, `frontend/nginx.conf` | Runtime: `id` inside the backend container returns `uid=0(root)`. | Open |
| SEC-07 | Medium | **Uploads and error leaks.**<br>• No size limit on the ML dataset or the restore ZIP (zip bomb).<br>• Restore returns a Python traceback to the client.<br>• `save_annual_targets` returns raw exception text with a 500. | `api.py:573-606,737-751,561`, `import_manager.py:83` | Code | Open |
| SEC-08 | Low | The 30-day session token is kept in `localStorage`, with no CSP to limit the impact of XSS. | `frontend/src/utils/session.ts` | Code | Open |

## MCP server

| ID | Sev | Finding | Location | Evidence | Status |
|---|---|---|---|---|---|
| MCP-01 | High | **Not MCP-protocol compliant.** There is no `initialize` handshake, and notifications get a reply when they shouldn't. Tools use `parameters` instead of `inputSchema`, and errors use `id: null`. Real MCP clients (Claude Desktop/Code) can't connect. | `mcp_server.py:376-394` | Runtime: `initialize` → `-32601 Method not found`, and `notifications/initialized` got an error reply. | Open |
| MCP-02 | High | **`update_global_split` always fails over HTTP**, because the injected `changed_by` is treated as a column. | `mcp_server.py:247,341` | Runtime: `no such column: changed_by` | Open |
| MCP-03 | Medium | **`create_kpi_indicator` hard-codes `changed_by="mcp_agent"`** and ignores the API-key identity. | `mcp_server.py:271` | Code | Open |
| MCP-04 | Medium | **Startup problems.**<br>• The MCP server never runs DB migrations; it can start against an empty volume before the backend.<br>• `python src/mcp_server.py` (as the README says) fails locally with `No module named 'src'`. | `mcp_server.py`, `README.md` | Code | Open |
| MCP-05 | Low | **`get_kpi_global_split` (and REST `/kpis/{id}/global-splits`) fall back to treating `kpi_id` as an `indicator_id`** when the KPI isn't found, which returns another KPI's split. | `mcp_server.py:353`, `api.py:507` | Code | Open |

## Calculation engine (targets, repartition, formulas, ML)

| ID | Sev | Finding | Location | Evidence | Status |
|---|---|---|---|---|---|
| ENG-01 | High | **Formula KPIs are never calculated.** The KPI Explorer formula editor sets `formula_string`, but the engine only evaluates KPIs that have an annual-target row with `is_formula_based=1`, which nothing creates. Saving the card from Target Entry stores **0** and clears the formula flag. | `annual.py:174-190`, `TargetEntryWorkspace.tsx:58-61` | Runtime:<br>• "Units per Hour = [1]/[2]" showed `n/a` after its inputs were saved.<br>• Clicking Save on it stored `target_value=0.0, is_formula_based=0`. | Open |
| ENG-02 | High | **`re` isn't imported in `annual.py`.** The `NameError` is swallowed by `except: pass`, so formula dependency ordering never works. | `annual.py:324,349` | Code | Open |
| ENG-03 | High | **Formula KPIs for target *N* are built from target-1 dependency series.** Daily data is keyed by `kpi_id` only. | `repartition.py:386-397`, `core/node_engine.py:308` | Code | Open |
| ENG-04 | High | **ML-predicted weights are incompatible with the engine.**<br>• The analyzer returns keys `"1".."12"` as fractions; the engine looks for `January`, `Q1` or `YYYY-Wnn` as percentages. A published split is therefore silently ignored and the engine falls back to Even.<br>• Min-max normalisation always gives the lowest period **0%**.<br>• "Day" is offered but not supported. | `services/split_analyzer.py:53-66,143`, `repartition.py:94-127` | Runtime: on synthetic seasonal data the result had keys `'1'..'12'` summing to 1.0, with **December = 0.0** even though real December sales were around 5% of the year. | Open |
| ENG-05 | High | **Week logic problems.**<br>• Days that belong to the neighbouring ISO year (e.g. 29–31 Dec) get 0.<br>• Unpadded keys (`2024-W1`) never match.<br>• Week templates are tied to a single year. | `repartition.py:127-142`, `kpi_management/splits.py:229` | Code | Open |
| ENG-06 | Medium | **Weight handling for Average KPIs.**<br>• Average KPIs ignore Quarter weights.<br>• A 0% weight becomes 100% (`or 100.0`). | `repartition.py:145-156,225-229` | Code | Open |
| ENG-07 | Medium | **The UI says "Default even split", but the backend default is `annual_progressive`.** | `annual.py:108`, `repartition.py:449` | Runtime: OEE (Average, no split) ramped from 81.9 to 88.1 across the months. | Open |
| ENG-08 | Medium | **The distribution profile is ignored whenever logic isn't "Year".** All presets are Month-based, so "Annual Progressive (Weekday Bias)" behaves exactly like Even. | `repartition.py:176-201` | Code | Open |
| ENG-09 | Medium | **Split changes don't update existing targets.**<br>• Changing a KPI's split, or a template's weights, doesn't recalculate periodic targets that already exist.<br>• The assigned split is `assigned[0]`, regardless of year. | `api.py:399-410`, `repartition.py:418-449` | Code | Open |
| ENG-10 | Medium | **Calculation types are inconsistent.**<br>• API and MCP default to `Sum`.<br>• Databases created before v2 have `CHECK(calculation_type IN ('Incremental','Average'))`, so KPI creation fails on them. **Your local `databases/db_kpis.db` has this constraint.**<br>• `Last`, `Min`, `Max` and `Count` are accepted but ignored by repartition. | `kpi_management/crud.py:117`, `specs.py:34`, `setup.py:76`, `repartition.py:348` | Read-only check of the local DB schema | Open |
| ENG-11 | Medium | **Formula DAG engine gaps.**<br>• It has no `abs` evaluator (always returns 0).<br>• No cycle guard: a cycle raises `RecursionError` after phase 1 has already committed.<br>• `pow` can raise `OverflowError`. | `core/node_engine.py:189,242,274-300` | Code | Open |
| ENG-12 | Medium | **Sum reconciliation can produce negative daily targets.** It shifts every day by the same amount instead of scaling. | `repartition.py:58-64` | Code | Open |
| ENG-13 | Low | **Unhandled edge cases.**<br>• Weekday-bias divide-by-zero gives NaN.<br>• `json.loads(None)` on a nullable `profile_params`.<br>• `actuals_service` crashes on a None direction or a non-dict threshold.<br>• An unknown `period_type` silently returns `[]`. | `utils/repartition_utils.py:73`, `data_retriever.py:442`, `splits.py:170,198,275`, `services/actuals_service.py:97-193` | Runtime: `period_type=Bogus` returned `[]` with HTTP 200. | Open |
| ENG-14 | Low | **Inconsistent periodic-target responses.**<br>• Months come back in alphabetical order (April, August, …).<br>• Per-plant rows use the key `Target`, while all-plants rows use `target_value`. | `data_retriever.py:229-300` | Runtime | Open |
| ENG-15 | Medium | **The ML endpoint blocks the server.** It is `async def` but runs CPU-heavy sync work (Random Forest, leave-one-out cross-validation, Monte Carlo) on the event loop, which stalls *every* request. | `api.py:573` | Runtime: the run took **20 s** on a 3-year daily dataset, and `GET /health` took **5.8 s** while it ran. | Open |

## Data integrity and storage

| ID | Sev | Finding | Location | Evidence | Status |
|---|---|---|---|---|---|
| DATA-01 | High | **The backup writes NULL as an empty string.** On restore, `parent_id=''` hides root folders, and an empty `target_value` crashes repartition. | `export_manager.py:220`, `import_manager.py:77` | Runtime: `raw_kpi_nodes.csv` contains `1,Demo Operations,,folder,,1` (the NULL `parent_id` became empty). | Open |
| DATA-02 | High | **Restore is a merge, not a restore.**<br>• It's an `INSERT OR IGNORE` merge that keeps the backup's primary keys, so colliding rows are dropped silently and child rows attach to the wrong parents.<br>• No snapshot is taken first.<br>• It commits per table across 7 database files, with no atomicity.<br>• Any user can run it. | `import_manager.py:60-80` | Code | Open |
| DATA-03 | High | **Soft-deleted KPIs don't go away.** They are still listed in every tab, still repartitioned, and still exported. | `data_retriever.py:73-119`, `annual.py:176` | Code | Open |
| DATA-04 | High | **The templates feature is broken.** It queries `kpi_nodes.indicator_template_id`, which doesn't exist. | `kpi_management/templates.py:54-120` | Runtime: `DELETE /templates/1` → **500 Internal Server Error** | Open |
| DATA-05 | Medium | **Your local DB still has the legacy `kpis` schema.** It has the calc-type CHECK, and an FK pointing at a table that no longer exists (`kpi_indicators_old`), which is a leftover of an earlier migration's rename. | `databases/db_kpis.db`, `setup.py:208-232` | Read-only schema check | Open |
| DATA-06 | Medium | **SQLite connections and locking.**<br>• `with sqlite3.connect(...)` commits but **never closes** connections; this pattern is used everywhere.<br>• There's no `busy_timeout`, while two containers share one volume. | repo-wide | Code | Open |
| DATA-07 | Medium | **Multi-database writes aren't atomic.**<br>• Annual save, repartition and hard-delete each write several DB files with separate commits.<br>• Hard deletes and plant force-deletes leave orphaned rows (actuals, periodic targets, split links, visibility). | `annual.py`, `repartition.py:283-333`, `kpi_management/indicators.py:98-150`, `plants_management/crud.py:91-132` | Code | Open |
| DATA-08 | Low | **Assorted storage issues.**<br>• `ATTACH` paths are built with f-strings.<br>• Period columns are untyped.<br>• There is an FK that crosses database files.<br>• The backup omits `units_of_measure` and history.<br>• Export temp dirs are never cleaned up.<br>• The "Annual Targets" CSV reads the legacy `annual_target1/2` columns. | `data_retriever.py:261,289,372`, `setup.py:343,607`, `export_manager.py`, `api.py:654-691` | Code | Open |
| DATA-09 | Low | **Settings issues.**<br>• No environment override for the data directory.<br>• The legacy `database_path` setting is ignored.<br>• Some paths are frozen at import time. | `config/settings.py`, `plants_management/crud.py:9-10`, `export_manager.py:46` | Code | Open |

## React frontend

| ID | Sev | Finding | Location | Evidence | Status |
|---|---|---|---|---|---|
| FE-01 | High | **Target Entry keeps the previous year's or plant's numbers** when the new selection has no saved entry, and Save writes them. Empty inputs are saved as 0. | `TargetEntryWorkspace.tsx:41-63` | Runtime: switched to **2027** (no data); the inputs still showed 120000 / 8000 / 85. Save stored **120000** for 2027. | Open |
| FE-02 | High | **Calculated KPIs keep an active Save button** that overwrites the formula result with 0. | `TargetEntryWorkspace.tsx:58-105` | Runtime (see ENG-01) | Open |
| FE-03 | High | **KPI Explorer render loop.** `const { data = [] }` creates a new array on every render. The effect then sets state, which re-renders, forever, whenever no KPI is selected or the visibility query is loading. | `KpiManagerWorkspace.tsx:185-196` | Code; it doesn't trigger while data is already loaded. | Open |
| FE-04 | Medium | **A stray "0" appears after every KPI name.** SQLite returns `0` for `is_calculated` and React renders it. | `TargetEntryWorkspace.tsx:90` | Runtime: "Units Produced **0** pcs" | Open |
| FE-05 | Medium | **The plant filter uses `selectedPlantId`**, which is null until the dropdown changes. As a result, KPIs disabled for the default plant still show, and once a plant is picked, KPI Explorer hides KPIs disabled for it, so they can't be re-enabled. | `App.tsx:29` | Code | Open |
| FE-06 | Medium | **Any `/auth/me` error logs you out**, including a backend restart or a network glitch. | `App.tsx:102` | Code | Open |
| FE-07 | Medium | **Errors and caching.**<br>• Every mutation swallows its errors.<br>• Several cache keys aren't invalidated, so Analysis, history and badges go stale.<br>• The restore result message is overwritten.<br>• Logging out keeps cached data visible for the next user. | `hooks/index.ts`, `SettingsWorkspace.tsx:36-42` | Code | Open |
| FE-08 | Medium | **The API base is hard-coded at build time to `http://localhost:8000`.** The app only works in a browser on the Docker host itself. | `services/api.ts:22`, `frontend/Dockerfile` | Runtime: all calls go to `localhost:8000`. | Open |
| FE-09 | Low | **Input handling.**<br>• Clearing a number box stores `NaN`, or snaps it to 0.<br>• No check that split weights add up to 100.<br>• No confirmation before deleting a KPI or a split.<br>• Unit hard-coded as `'Units'`.<br>• A `fetchJson` header-merge bug. | `GlobalSplitsWorkspace.tsx:338`, `KpiManagerWorkspace.tsx:208-214,416,521,665,678`, `api.ts:37-40` | Code | Open |
| FE-10 | Low | **Missing or awkward UI.**<br>• Missing for existing API features: edit/delete facility, edit/deactivate user.<br>• The year list is hard-coded.<br>• The Analysis year doesn't follow the header.<br>• A new API key stays visible after switching to another user. | `PlantsWorkspace.tsx`, `UsersAdminPanel.tsx`, `Header.tsx`, `AnalysisWorkspace.tsx` | Code | Open |
| FE-11 | Low | **Accessibility.**<br>• No label is linked to its input.<br>• Icon-only buttons have no name.<br>• Clickable `<div>`s can't be reached by keyboard.<br>• Muted text contrast is about 3.9:1.<br>• The focus outline is removed.<br>• New plants default to black, which is invisible on the dark background. | `frontend/src/**`, `index.css`, `api.py:121` | Runtime: the login textboxes have no accessible name. | Open |
| FE-12 | Low | **Tooling.**<br>• TypeScript `strict` is off.<br>• No react-hooks lint rules.<br>• No frontend tests.<br>• `clsx` is unused.<br>• The image uses `node:20`, which is end-of-life. | `frontend/` | Code | Open |

## Containers, packaging, tests, docs, legacy code

| ID | Sev | Finding | Location | Evidence | Status |
|---|---|---|---|---|---|
| INF-01 | Medium | **The backend image is 1.24 GB and is built twice** (backend and mcp). It ships things it doesn't need:<br>• `frontend/` source<br>• `docs/`, `old/`<br>• `.omniscan/state.db`<br>• stale `src/databases/*.db`<br>• streamlit, matplotlib, plotly. | `Dockerfile`, `.dockerignore`, `compose.yml` | Runtime: `ls /app` in the container | Open |
| INF-02 | Medium | **Container setup.**<br>• Containers run as root.<br>• No healthchecks.<br>• `depends_on` doesn't wait for a healthy backend.<br>• `restart: always`.<br>• An unused `./csv_exports` bind mount. | `Dockerfile`, `compose.yml` | Runtime | Open |
| INF-03 | Medium | **Python version and dependency drift.**<br>• Python 3.12 (Docker) vs 3.13 (`pyproject.toml`, `.python-version`) vs "3.11+" (docs).<br>• `pyproject.toml` is missing fastapi, uvicorn and scikit-learn.<br>• A bogus `[tool.uv.workspace]` member.<br>• `requirements.txt` is unpinned, even though the CHANGELOG claims "strict versioning". | `pyproject.toml`, `requirements.txt` | Code | Open |
| TEST-01 | Medium | **Test gaps.**<br>• No tests at all for the REST API, auth, repartition totals, backup/restore or the formula engine.<br>• `tests/test_mcp_server.py` is broken since d49bb80.<br>• pytest isn't installed or configured.<br>• `src/scripts/test_*.py` write to the real `databases/`. | `tests/`, `src/scripts/` | Code | Open |
| LEG-01 | Medium | **The legacy Tkinter/Streamlit GUIs.**<br>• Both bypass login and write to SQLite directly.<br>• Streamlit fails at import (4 missing constants).<br>• Legacy `groups`/`subgroups` modules call functions that don't exist. | `src/interfaces/**`, `src/kpi_management/{groups,subgroups}.py` | Code | Open |
| DOC-01 | Low | **Docs drift.**<br>• The API reference lists 6 MCP tools; there are 22.<br>• It claims healthchecks that don't exist.<br>• No CHANGELOG entry for d49bb80.<br>• Versions disagree: 2.0.0 / 0.1.0 / 0.0.0.<br>• Old `podman-compose` naming. | `docs/*`, `README.md`, `CHANGELOG.md` | Code | Open |

---

## Fix log (branch `audit-fixes`)

Filled in as each workstream lands. See `git log` on the branch for the exact commits.
