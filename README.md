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

- **KPI hierarchy.** Folders of KPIs. Each KPI has:
  - a unit, a direction (higher, lower or range) and alert thresholds;
  - a number of target scenarios with your own names (e.g. *Budget* / *Stretch*);
  - an aggregation type: **Sum** and **Count** split the target across periods, while **Average**, **Last**, **Min** and **Max** treat it as a level.
- **Formula KPIs.** `[1] / [2]` computes *Units per Hour* from *Units Produced* and *Hours Worked*. Formulas are recalculated automatically, in dependency order, whenever an input changes. They're evaluated by a whitelisted AST walker (no `eval`), and cycles are rejected when you save.
- **Repartition.** Every saved annual target becomes day, week, month and quarter targets:
  - Month, Quarter or ISO-week weights decide how much each period gets.
  - A *day shape* spreads each period over its days: even, progressive, weekday-biased, sinusoidal, or with event spikes and dips.
  - The result is reconciled exactly to the annual figure.
- **Global split templates.** Reusable seasonal curves, assigned to KPIs, optionally limited to specific years. Editing a template recalculates every KPI that uses it.
- **ML seasonality predictor.** Upload historical data (CSV or Excel) with optional driver columns, such as temperature or promotions. OLS, Ridge and Random Forest are raced, and the winner's seasonal weights, with a 5–95% band, can be published as a template.
- **Facilities.** Per-plant visibility of KPIs, chart colours, and "apply to all facilities" saves.
- **Analysis.** Multi-plant charts and an annual summary table, with a periodic-target CSV export.
- **Accounts and audit trail.**
  - The first account becomes the administrator, and self-registration then closes.
  - Admins manage users, password resets and restores; everyone else manages only their own account.
  - Every target value and definition change records who made it and when.
- **Data utilities.** Human-readable CSV exports and a full ZIP backup. Restore *replaces* the data in one transaction, after snapshotting the current databases.

See the **[user guide](docs/user_guide.md)** for a tour of every screen.

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
| `CORS_ORIGINS` | localhost:3000/5173 | Origins allowed to call the REST API directly |
| `ALLOW_REGISTRATION` | `false` | Let anyone register (non-admin) accounts after the first one |
| `MAX_UPLOAD_MB` | `20` | Size cap for ML datasets and backup restores (REST and MCP) |
| `LOG_LEVEL` | `INFO` | Backend log level |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8001` | HTTP transport bind address |
| `MCP_PUBLIC_URL` | `http://localhost:8001` | URL clients use (advertised in auth metadata) |
| `MCP_ALLOWED_HOSTS` | `localhost:*,127.0.0.1:*` | Host headers accepted when binding to a non-loopback address |
| `MCP_STDIO_USER` | `mcp_agent` | Who stdio writes are attributed to |
| `MCP_STDIO_ADMIN` | `true` | Whether the local stdio operator may use admin tools |
| `FRONTEND_PORT`, `BACKEND_BIND_ADDRESS`, `MCP_BIND_ADDRESS` | `3000`, `127.0.0.1`, `127.0.0.1` | Compose port publishing |

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
docs/                     guides, reference, screenshots
```

## Documentation

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
