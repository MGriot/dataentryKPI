# Data Entry KPI Target Manager

Define KPIs, enter annual targets per facility, and let the system split them into daily, weekly, monthly and quarterly targets, using seasonal curves you design or derive from historical data with a small ML model race.

![Target Entry: annual targets per KPI, with named target scenarios and the assigned seasonal split](docs/images/target-entry.png)

One Python core (SQLite storage, repartition engine, formula engine, seasonality predictor) is exposed three ways:

| Interface | Use it for | Code |
|---|---|---|
| **React web app** | Everyday work: KPI definitions, target entry, splits, analysis, facilities, backups, accounts | `frontend/` |
| **REST API** | The app's backend; also scripts and BI tools (Swagger UI at `/docs`) | `src/api.py` |
| **MCP server** | AI agents (Claude Desktop, Claude Code, any MCP client). 60 tools covering everything the API does | `src/mcp_server.py` |

All three share the same databases and the same rules (validation, roles, audit trail), so a target saved by an agent shows up in the app immediately and is attributed to the agent's user.

![Architecture](docs/images/architecture.svg)

## Features

The web app covers everyday work. The REST API and the MCP server expose all of it, plus a few features marked *API/MCP only*.

[Web app](#web-app) · [Calculation engine](#calculation-engine) · [Accounts, security and audit](#accounts-security-and-audit) · [Data and storage](#data-and-storage) · [REST API](#rest-api) · [MCP server](#mcp-server-ai-agents) · [Deployment and tooling](#deployment-and-tooling)

### Web app

- **One header for every screen:**
  - tabs for the six workspaces;
  - a quick search that filters the KPI cards;
  - **year** and **facility** selectors, which Target Entry and Analysis follow;
  - a reload button;
  - your account, with an **Admin** badge for administrators.
- **Target Entry.** One card per KPI enabled for the selected facility:
  - Each card shows the unit, the number of target scenarios and the split template in use.
  - Under each box, the previous two years' values are shown for reference.
  - Scenarios carry their own names, e.g. *Budget* and *Stretch*.
  - **Save** stores the annual values. It then recalculates the day, week, month and quarter targets, and every formula KPI that depends on this one.
  - Blank boxes are left unchanged; they are never saved as 0.
  - Switching to a year or facility with no data clears the boxes.
  - **Apply saves to all visible facilities** writes the same values everywhere, after a confirmation.
  - Formula KPIs are read-only and marked *Formula derived*.
- **KPI Explorer.**
  - **Folder tree.** Add top-level folders, sub-folders and KPIs. The tree can be driven entirely from the keyboard.
  - **Definition fields:**
    - description;
    - unit of measure, with a *New unit* shortcut;
    - aggregation type;
    - directional goal (higher, lower or range);
    - number of targets (1–10) and their scenario names;
    - target granularity;
    - owner;
    - default visibility;
    - performance alert thresholds;
    - actuals time filter (a rolling window of *N* days).
  - **Split template.** Assign one per KPI; saving it recalculates the KPI's stored targets.
  - **Formula editor.** A toolbar inserts KPI references `[id]`, operators, and `abs`, `min`, `max` and `round`. Formulas are validated when saved: syntax, known KPIs, no self-reference, no cycles. A cycle error names the loop, e.g. `[2] -> [4] -> [2]`.
  - **Facility enablement.** Turn a KPI off for specific facilities.
  - **Audit history.** Who changed which target value, for which facility and scenario, and which definition fields changed (old → new).
  - **Delete.** Deleting is soft: the KPI disappears everywhere, but its targets and history are kept. A confirmation comes first.
- **Global Splits & ML.**
  - Create, edit and delete split templates. Weights are set per **month**, **quarter** or **ISO week**, and a running total shows their sum.
  - Choose a day shape inside each period, and limit the template to specific years or let it cover all years.
  - Five presets are included: Uniform, Annual Progressive, Weekday Bias, Sinusoidal, Event Based (shutdowns).
  - The ML seasonality predictor is built in. See below.
- **Analysis & Results.**
  - Charts of any KPI's targets per day, week, month, quarter or year, for one facility or all of them side by side.
  - An annual summary table for this year and last year.
  - Export of the chart's periodic targets to CSV.
- **Facilities.** Add, edit and delete facilities.
  - Each facility has a chart colour and can be hidden; hidden facilities are skipped by *apply to all*.
  - A facility that has data can only be deleted after a second confirmation, which deletes its data too.
- **Data Utilities.**
  - CSV exports and a full ZIP backup, plus restore (admins only).
  - Change your own password.
  - User administration (admins only).
  - MCP API keys.
- **Usability.**
  - A toast appears when a save fails, and a retry screen when the backend can't be reached. Only a real 401 signs you out.
  - Labelled inputs, ARIA names, visible focus and WCAG-friendly contrast.
  - Charts are lazy-loaded, which keeps the first load small.

### Calculation engine

- **Aggregation types.** **Sum** and **Count** treat the annual target as a total that the periods add up to. **Average**, **Last**, **Min** and **Max** treat it as a level. Weeks, months and quarters are aggregated from the daily series accordingly.
- **Repartition.** Every saved annual target becomes a daily series for its year, which is then rolled up into ISO weeks (`2026-W05`), months and quarters:
  1. A **day shape** gives every day a weight: even, progressive ramp, weekday-biased, sinusoidal, or event-based.
  2. **Period weights** (month, quarter or week) decide how much of the year each period gets. A weight of 0 really means 0.
  3. **Events** (`start_date`, `end_date`, `multiplier`, `addition`) model shutdowns, spikes and dips.
  4. **Reconciliation by scaling** makes the sum (Sum and Count) or the mean (level types) match the annual figure exactly, without pushing any day negative.
  - Leap years, ISO weeks that belong to the neighbouring year, and all-zero weights are handled, and tests cover them.
- **Split templates.**
  - Templates are reusable and can be limited to specific years.
  - Week keys `W01`..`W53` don't depend on the year.
  - Every change recalculates the affected KPIs: assigning, editing, relinking or deleting a template.
  - A curve preview turns a shape into starting weights.
- **Formula KPIs.**
  - `[1] / [2]` computes *Units per Hour* from *Units Produced* and *Hours Worked*.
  - **Safe evaluation.** A whitelisted AST walker evaluates formulas, never `eval`. Size and exponents are bounded, and division by zero gives 0.
  - **Per scenario.** Target *N* is computed from target *N* of its inputs.
  - **Daily values.** The daily series is computed day by day from the inputs' daily series, so a ratio follows its inputs' seasonality.
  - **Dependency order.** A save recomputes every dependent formula, in topological order, in the same transaction.
  - A visual formula DAG (`formula_json`) is also supported.
- **ML seasonality predictor.**
  1. Upload a CSV or Excel file of history (size-capped). Name the date column, one or more target columns, and optional **driver** columns (temperature, promotions, a market index…).
  2. Targets are averaged per month, quarter or ISO week across years and normalised to a share of the mean. Drivers are min-max scaled.
  3. **OLS**, **Ridge** and a **Random Forest** are raced. The best R² wins, after a complexity penalty for small datasets.
  4. 100 Monte Carlo runs give a **5–95% band**.
  5. The weights come back as percentages summing to 100, keyed like template weights, so **Publish as template** uses them as they are.
  - The predictor runs in a worker thread, so it never blocks the API.
- **Actuals and performance status** *(API/MCP only)*:
  - Record measured values per KPI, plant and day.
  - The status of the latest actual against its target is `on_track`, `warning` or `out_of_range`. It follows the KPI's direction and threshold margins, which are relative to |target|.
  - It includes a least-squares **trend** and an optional rolling window.
- **KPI definition templates** *(API/MCP only)*. Reusable sets of KPI definitions. Applying one to a folder creates its KPIs there, and later edits to the template propagate.
- **Units of measure registry**, shared by every KPI.

### Accounts, security and audit

- **Accounts.** The **first account becomes the administrator**, and self-registration then closes. `ALLOW_REGISTRATION=true` reopens it for regular accounts.
- **Roles.**
  - Admins create and edit users, reset passwords, grant or remove admin rights, manage anyone's API keys, and restore backups.
  - Everyone else manages only their own profile, password and keys.
  - The last active admin can't be removed.
  - One module (`user_management/access.py`) enforces these rules for both REST and MCP.
- **Sign-in.**
  - Passwords are hashed with PBKDF2-HMAC-SHA256, and sessions last 30 days.
  - Logins are rate-limited (HTTP 429), and unknown names take as long to reject as known ones.
  - Changing your password signs out your other sessions. Deactivating a user revokes their sessions and API keys.
- **Audit trail.**
  - Every KPI definition change is recorded with the user, the time, and the old and new values.
  - So is every annual target value that actually changes, with the plant and scenario.
  - Re-saving identical values isn't recorded.
  - The user always comes from the session or API key, never from the request.
- **Hardening.**
  - CORS allowlist (`CORS_ORIGINS`) and upload size caps (`MAX_UPLOAD_MB`).
  - Clients never see tracebacks.
  - nginx sends a CSP and other security headers.
  - Containers run as a non-root user, with the API and MCP ports published on loopback only.

### Data and storage

- **SQLite, split across several files** (KPIs, targets, days, weeks, months, quarters, plants, users, templates, history, actuals). One connection layer closes every connection, sets a busy timeout and enforces foreign keys. Writes that span several files commit **atomically**.
- **Automatic migrations** upgrade and repair databases created by earlier versions, every time the backend or the MCP server starts.
- **CSV exports.** Seven human-readable tables (plants, hierarchy, definitions, visibility, annual targets, periodic targets, lean BI rows), for people and BI tools.
- **Backup.** A full ZIP of every KPI table, 1:1, with NULLs preserved. User accounts, sessions and keys are excluded.
- **Restore** *(admins only)*:
  1. The ZIP is validated.
  2. The current databases are snapshotted to `databases/backups/pre-restore-<timestamp>/`.
  3. All KPI data is **replaced** in one transaction.
- **Configurable locations.** `KPI_DB_DIR`, `KPI_EXPORT_DIR`, or `user_config/settings.json`.

### REST API

- **67 routes** for:
  - auth;
  - KPIs and folders;
  - units;
  - visibility;
  - plants;
  - split templates;
  - annual and periodic targets;
  - actuals;
  - the ML analysis;
  - KPI templates;
  - exports, backup and restore;
  - users and API keys.
- **Swagger UI** at `/docs`, with an **Authorize** button. The OpenAPI schema is at `/openapi.json`.
- Bearer session tokens, and `/health` for container healthchecks.

### MCP server (AI agents)

- **60 tools** covering everything the REST API does. They're built on the official `mcp` SDK, and a parity test fails if a REST route has no tool.
- **Transports:**
  - **stdio** for local clients such as Claude Desktop and Claude Code;
  - **Streamable HTTP** for shared use. Every request needs a per-user API key.
- Writes are attributed to the API key's owner (`changed_by`), and admin tools follow that user's role.
- Tools carry read-only and destructive annotations. Errors reach the model as readable messages.

### Deployment and tooling

- **Compose stack** (Podman or Docker):
  - three services: the nginx frontend, the backend and the MCP server;
  - healthchecks and start ordering, with the backend running the migrations;
  - one shared data volume;
  - one 513 MB backend image, shared by the backend and the MCP server.
- **Dev scripts:**
  - `dev_backend.py` runs the API on a throwaway database;
  - `seed_demo.py` loads demo data;
  - `capture_screenshots.py` regenerates the doc screenshots and the guide's annotations.
- **Tests:** 147 pytest tests and 15 vitest tests, strict TypeScript, and oxlint with the react-hooks rules and no warnings allowed.

See the **[illustrated guide](docs/guide/index.html)** (open it in a browser) or the **[user guide](docs/user_guide.md)** for a tour of every screen.

## Quick start

### Option A: local development

Requires Python 3.12+ and Node 22+.

```bash
python -m venv .venv
```
```bash
.venv/Scripts/python -m pip install -r requirements.txt
```
On macOS or Linux, use `.venv/bin/python` instead.

```bash
.venv/Scripts/python scripts/dev_backend.py
```
This runs the API on http://127.0.0.1:8000 (Swagger UI at `/docs`), using a throwaway database in `.dev-data/`. To use `databases/` instead, run `python -m uvicorn src.api:app`.

```bash
npm --prefix frontend install
```
```bash
npm --prefix frontend run dev
```
This serves the app on http://localhost:5173. Vite proxies `/api` to the backend.

Open the app and **create the first account. It becomes the administrator.** Optionally, load demo data (two plants, KPIs, a formula KPI, a seasonal split, and two years of targets):

```bash
.venv/Scripts/python scripts/seed_demo.py
```

### Option B: containers (Podman or Docker Compose)

```bash
podman compose up --build -d
```

| Service | URL | Notes |
|---|---|---|
| `frontend` | http://localhost:3000 | nginx serves the app and proxies `/api` to the backend. Set `FRONTEND_PORT` to change the port. |
| `backend` | http://127.0.0.1:8000 | Loopback only by default (`BACKEND_BIND_ADDRESS`) |
| `mcp_server` | http://127.0.0.1:8001/mcp | Loopback only by default (`MCP_BIND_ADDRESS`); needs an API key |

How the containers run:
- They run as a non-root user and have healthchecks.
- Data lives in the `kpi_databases` volume.
- The backend runs the migrations; the MCP server waits until the backend is healthy.

Copy `.env.example` to `.env` to change settings.

> **Windows:** Hyper-V sometimes reserves port 3000. Check with `netsh interface ipv4 show excludedportrange protocol=tcp`; if 3000 is in a listed range, set `FRONTEND_PORT=8080`.

> **Upgrading from 2.0 containers:** the images no longer run as root. If the existing `kpi_databases` volume was created by root, give it to uid 1000 once:
> `podman run --rm -v dataentrykpi_kpi_databases:/data alpine chown -R 1000:1000 /data`

## Connecting an AI agent (MCP)

The MCP server exposes every REST feature as a tool. That covers KPIs, targets, splits, the ML predictor, templates, actuals, history, backups, users and API keys. See **[docs/mcp.md](docs/mcp.md)** for the full list.

**Local, over stdio.** The client starts the server itself, using the repo's `databases/` folder (or `KPI_DB_DIR`), and writes are attributed to `MCP_STDIO_USER`. For Claude Code:

```bash
claude mcp add kpi --env MCP_STDIO_USER=claude-code -- /path/to/dataentryKPI/.venv/bin/python /path/to/dataentryKPI/src/mcp_server.py
```

For Claude Desktop, add this to `claude_desktop_config.json`:

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

**Shared, over HTTP** (the `mcp_server` container, or `python -m src.mcp_server --http`):
1. Create an API key in **Data Utilities → MCP API keys**.
2. Point the client at the server:

```bash
claude mcp add --transport http kpi http://127.0.0.1:8001/mcp --header "Authorization: Bearer kpi_mcp_..."
```

The key's owner is recorded as `changed_by` on every write, and their role decides access to the admin tools.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `KPI_DB_DIR` | `./databases` | Where the SQLite files live |
| `KPI_EXPORT_DIR` | `./csv_exports` | Where CSV exports are written |
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8000` | Bind address for `python src/api.py` (`dev_backend.py` reads `API_PORT`) |
| `CORS_ORIGINS` | localhost:3000/5173 | Origins allowed to call the REST API directly |
| `ALLOW_REGISTRATION` | `false` | Let anyone register (non-admin) accounts after the first one |
| `MAX_UPLOAD_MB` | `20` | Size cap for ML datasets and backup restores (REST and MCP) |
| `LOG_LEVEL` | `INFO` | Backend log level |
| `MCP_TRANSPORT` | `stdio` | `http` does the same as `--http` |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8001` | HTTP transport bind address |
| `MCP_PUBLIC_URL` | `http://localhost:8001` | URL clients use (advertised in auth metadata) |
| `MCP_ALLOWED_HOSTS` | `localhost:*,127.0.0.1:*` | Host headers accepted when binding to a non-loopback address |
| `MCP_STDIO_USER` | `mcp_agent` | Who stdio writes are attributed to |
| `MCP_STDIO_ADMIN` | `true` | Whether the local stdio operator may use admin tools |
| `FRONTEND_PORT`, `BACKEND_BIND_ADDRESS`, `MCP_BIND_ADDRESS` | `3000`, `127.0.0.1`, `127.0.0.1` | Compose port publishing |
| `VITE_API_URL` | *(empty)* | Frontend **build-time** API base. Leave it empty to use the same-origin `/api` proxy. If you set it, add that origin to `CORS_ORIGINS`. |

Outside containers, `user_config/settings.json` (`database_base_dir`, `csv_export_base_dir`) can also set the two data directories. Environment variables take precedence over it.

## Tests

```bash
.venv/Scripts/python -m pytest tests -q
```
```bash
npm --prefix frontend run typecheck
```
```bash
npm --prefix frontend run lint
```
```bash
npm --prefix frontend test
```

The backend suite (147 tests) covers:
- auth and the authorization matrix;
- formula sandboxing;
- repartition math, including leap years and ISO-week boundaries;
- the backup round trip and legacy-schema migrations;
- the MCP server, including a parity test that fails when a REST route has no MCP tool.

## Project layout

```
frontend/                 React + TypeScript + Vite app (one workspace component per tab)
src/
  api.py                  FastAPI REST API
  mcp_server.py           MCP server (stdio / Streamable HTTP)
  core/                   formula.py (safe formula evaluator), node_engine.py (formula DAG)
  target_management/      annual.py (save + recalculation pipeline), repartition.py (the math)
  kpi_management/         KPIs, folders, splits, templates, visibility
  plants_management/      facilities
  user_management/        accounts, sessions, API keys; access.py = who may do what
  services/               actuals & status, audit history, ML seasonality predictor
  data_access/            db.py (connections, ATTACH), setup.py (schema + migrations)
  export_manager.py       CSV exports + raw backup ZIP
  import_manager.py       validated, transactional restore
scripts/                  dev_backend.py, seed_demo.py, capture_screenshots.py
tests/                    pytest suite
docs/                     guides, reference, screenshots, HTML guide (guide/), audit report
```

## Documentation

- **[Illustrated guide (HTML)](docs/guide/index.html)**: the complete manual, with annotated screenshots. Open it in a browser; GitHub shows the HTML source.
- **[User guide](docs/user_guide.md)**: every screen, with screenshots.
- **[MCP server](docs/mcp.md)**: transports, authentication, roles, and all 60 tools.
- **[REST API reference](docs/api_reference.md)**: every route, auth and roles.
- **[Architecture](docs/architecture.md)**: components, data flow, deployment.
- **[Core logic](docs/features.md)**: repartition, formulas, seasonality predictor, performance status.
- **[Code-level deep dive](docs/code_depth.md)**: the engine internals, with code references.
- **[Database schema](docs/database_schema.md)**: the SQLite files and tables.
- [CHANGELOG](CHANGELOG.md) · [Audit report](docs/audit.md) · [TODO](TODO.md)

## License

MIT, see [LICENSE](LICENSE).
