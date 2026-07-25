# Data Entry KPI Target Manager

A platform for defining KPIs, entering annual targets, and automatically distributing them into daily/weekly/monthly/quarterly values across facilities. The system is built around one shared Python core (SQLite data layer, repartition engine, ML seasonality predictor) exposed through **four** interfaces:

| Interface | What it's for | Where it lives |
|---|---|---|
| **React web app** | Primary UI — KPI definition, target entry, global splits, analysis, facilities, data utilities, user profiles | `frontend/` (talks to the FastAPI backend) |
| **FastAPI REST API** | Backend for the React app; also usable directly (Swagger UI at `/docs`) | `src/api.py` |
| **MCP server** | Lets AI agents/tools query and edit KPI data (stdio for local clients, HTTP+API-key for shared/remote use) | `src/mcp_server.py` |
| **Tkinter / Streamlit** | Original desktop and web GUIs, still functional, share the same databases | `src/interfaces/tkinter_app/`, `src/interfaces/streamlit_app/` |

All four read and write the same SQLite databases in `databases/`, so data entered in one is immediately visible in the others.

## Core capabilities

- **KPI hierarchy** — nested Groups/Subgroups/Folders, each holding indicators with a description, unit, calculation type, formula (string or visual DAG), directional goal, performance thresholds, target granularity, and a **per-KPI target count** (1..N target scenarios — Base/Stretch/etc., not hardcoded to two).
- **Target entry & repartition** — enter an annual target and it's automatically split into daily/weekly/monthly/quarterly values using a chosen logic (Year/Month/Quarter/Week) and distribution profile (even, progressive, sinusoidal, weekday-biased, event-based). Calculated (formula-based) KPIs are recomputed and repartitioned in dependency order — a KPI's drivers are always repartitioned before the KPI itself.
- **Global Split templates** — reusable seasonal weight curves that can be linked to one or more indicators; when linked, the template's logic/profile/weights override the KPI's own settings.
- **Multivariate seasonality predictor** — upload a CSV/Excel of historical drivers and the backend races OLS, Ridge, and Random Forest models (with cross-validation and Monte Carlo confidence bands) to derive seasonal weights, which can be published straight into a Global Split.
- **Plants** — facility CRUD with per-plant visibility, accent colors, and broadcast-to-all-facilities target saves.
- **Data utilities** — CSV export (lean or per-table), full ZIP backup/restore (raw table dumps, preserves IDs/relationships so restore is a true round-trip), formula/DAG editor.
- **Accounts & audit trail** — password-based login is required before entering or modifying anything (register/sign in gate the whole app, not just a UI overlay — the REST API itself rejects unauthenticated requests). Every save is stamped with the logged-in user's name automatically; full history of who changed a target value or a KPI's definition, and when, is visible in the KPI Explorer. Password changes live under Data Utilities. MCP callers authenticate separately, with a per-user API key rather than a login session.
- **Custom target names** — each KPI can name its own target scenarios (e.g. "Budget" / "Committed" instead of "Target 1" / "Target 2") from the KPI Explorer, independent of how many targets it has.

## Project structure

```
dataentryKPI/
├── frontend/                    # React + TypeScript + Vite web app (primary UI)
│   ├── src/components/          # One workspace component per tab (TargetEntry, KpiManager, GlobalSplits, ...)
│   ├── src/hooks/                # React Query hooks wrapping the API client
│   ├── src/services/api.ts       # REST client
│   └── Dockerfile, nginx.conf    # Container build (served on :80 / mapped to :3000)
│
├── src/
│   ├── api.py                   # FastAPI REST API (backend for the React app)
│   ├── mcp_server.py             # MCP server: stdio (local) or HTTP (--http, API-key gated)
│   ├── main.py                   # Launcher for the legacy GUIs (tkinter | streamlit)
│   ├── core/                     # DAG/formula engine, rollup aggregation
│   ├── services/                 # actuals, history, ML seasonality predictor
│   ├── interfaces/               # Tkinter desktop app, Streamlit web app, shared UI constants
│   ├── data_access/               # DB setup + migrations (setup.py) — additive, safe to re-run
│   ├── kpi_management/            # Hierarchy/indicator/spec/template/global-split/visibility CRUD
│   ├── target_management/         # annual.py (save + orchestration), repartition.py (the math)
│   ├── plants_management/         # Facility CRUD
│   ├── user_management/           # Named profiles + API key issuance/validation
│   ├── data_retriever.py          # Read-only query facade
│   ├── export_manager.py          # CSV export + raw-table ZIP backup dump
│   └── import_manager.py          # ZIP restore (matches export_manager's raw table format)
│
├── databases/                    # SQLite files, one per domain (kpis, targets, plants, users, ...)
├── docs/                          # Architecture, schema, API reference, GUI manuals
├── tests/                         # pytest suite
├── Dockerfile, compose.yml # backend + frontend + mcp_server containers
└── requirements.txt
```

## Running it

### Option A — React app + API (recommended)

```bash
pip install -r requirements.txt
python -m uvicorn src.api:app --reload          # backend on :8000, http://localhost:8000/docs for Swagger UI
```
```bash
cd frontend
npm install
npm run dev                                      # frontend on :5173, talks to the backend above
```

### Option B — Docker / Podman Compose (backend + frontend + MCP, all three containers)

```bash
podman compose up --build
# frontend  -> http://localhost:3000
# backend   -> http://localhost:8000
# mcp_server -> http://localhost:8001 (HTTP transport, requires an API key -- see below)
```

### Option C — Legacy desktop/web GUIs

```bash
pip install -r requirements.txt
python src/main.py tkinter      # desktop app
python src/main.py streamlit    # web app on the Streamlit dev server
```

### Logging in

The REST API rejects every request without a valid session (`Authorization: Bearer <token>`), except `/auth/register`, `/auth/login`, `/health`, and the docs routes — this is enforced server-side, not just hidden in the UI. The React app shows a Sign In / Register screen until you authenticate; register once (name + password, 8+ characters) to get in, and change your password any time under **Data Utilities → Password Management**. Sessions last 30 days and are stored client-side in `localStorage`.

### MCP server for AI agents

MCP authentication is a **separate mechanism from login** — a session token from `/auth/login` will not work against the MCP server, and vice versa.

- **Local (stdio)** — the default: `python src/mcp_server.py`. Point a local MCP client (e.g. Claude Desktop) at this command; no auth, since it's a private subprocess pipe.
- **Shared (HTTP)** — `python src/mcp_server.py --http` (or `MCP_TRANSPORT=http`, which is what the Docker container runs). Every request needs `Authorization: Bearer <key>`. Mint a key for a user via `POST /users/{id}/api-keys` on the backend (or the "MCP API Keys" panel under Data Utilities in the React app) — the key is shown once, and the user it belongs to is force-stamped as `changed_by` on anything that key writes, regardless of what the caller claims.

## Documentation

- **[Documentation Index](docs/index.md)**
- **[System Architecture](docs/architecture.md)** — layers, data flow, how the four interfaces share one core.
- **[REST & MCP API Reference](docs/api_reference.md)** — endpoint list, request/response shapes, MCP tools.
- **[Database Schema](docs/database_schema.md)** — the partitioned SQLite schema.
- **[Tkinter Manual](docs/gui_tkinter.md)** / **[Streamlit Manual](docs/gui_streamlit.md)** — legacy interface guides.
- **[Core Logic & Algorithms](docs/features.md)** — formula engine, repartition math, ML predictor.
- **[Code-Level Deep Dive](docs/code_depth.md)** — DAG engine, reconciliation math, trend calc, CSV layouts, with code references.

## Tests

```bash
python -m pytest tests/ -q
```

## License & History

- MIT License — see [LICENSE](LICENSE).
- [CHANGELOG.md](CHANGELOG.md) for release history.
