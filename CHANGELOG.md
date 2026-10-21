# Changelog

All notable changes to this project will be documented in this file.

## [2.1.0] - 2026-10-21

A security, correctness and operability release, from the audit in [AUDIT.md](AUDIT.md). That file has the per-finding status and commits.

### Security
- **Formulas no longer use `eval`.** They are parsed with `ast` and walked through a strict whitelist, which closes a remote-code-execution hole. Formulas are validated when saved: syntax, known KPIs, no self-reference, no cycles.
- **Roles.** The first account is the admin, and self-registration then closes (`ALLOW_REGISTRATION=true` reopens it for regular accounts). Only admins can create or edit other users, reset passwords, manage other people's API keys, or restore backups. The rules live in one module (`user_management/access.py`) shared by REST and MCP.
- **Login.** Logins are rate-limited (429), unknown names cost the same as known ones, changing your password signs out your other sessions, and deactivating a user revokes their sessions and API keys.
- **Hardening.**
  - CORS is limited to `CORS_ORIGINS`.
  - Uploads are size-capped (`MAX_UPLOAD_MB`).
  - Clients no longer receive tracebacks or raw errors.
  - Swagger UI has an **Authorize** button.
  - Containers run as non-root, and the backend and MCP ports are published on loopback.
  - nginx sends a CSP and other security headers.

### MCP server
- **Rebuilt on the official `mcp` SDK.** Real clients (Claude Desktop and Code) can now connect, over stdio or Streamable HTTP with per-user API keys.
- **Full REST parity: 60 tools.** New: plants, visibility, actuals, history, KPI templates, bulk multi-plant saves with split settings, the ML predictor (`analyze_seasonality`), CSV export, backup and restore, users, password changes and API keys. A test fails if a REST route has no tool.
- **Writes are attributed to the API key's owner**, and admin tools follow that user's role. Over stdio, writes go to `MCP_STDIO_USER`, and admin tools are allowed unless `MCP_STDIO_ADMIN=false`.
- Tool errors now reach the model with their message; tools carry read-only and destructive annotations; migrations run on start; `python src/mcp_server.py` works from any directory.

### Calculation engine
- **Rewritten repartition.**
  - Month, quarter and week weights per period, with the profile as the day shape inside each period.
  - Year-agnostic week keys `W01`..`W53`, and correct ISO-week edges.
  - Reconciliation by scaling, so no day goes negative.
  - Separate rules for additive (Sum, Count) and level (Average, Last, Min, Max) types.
  - The default is a true even split.
- **Formula KPIs are actually computed.** Annual and daily values are calculated per target scenario, in dependency order, and can't be overwritten by hand.
- **Recalculation on change.** Changing a split template, a split assignment, a formula or an aggregation type recalculates the stored targets. A split applies only to the years it covers.
- **ML predictor.** Weights come back keyed like templates and as percentages summing to 100, with no artificial 0% period; it runs off the event loop.

### Data
- **One connection layer** (`data_access/db.py`). Connections are always closed, have a busy timeout and enforce foreign keys. Saves, repartitions and deletes that span several database files commit atomically.
- **Migrations repair legacy databases** created by earlier versions: the calc-type CHECK, the foreign key to a dropped table, cross-file foreign keys, and untyped columns.
- **Backup and restore.**
  - Backups keep NULL as `\N`, and include units and history.
  - Restore validates the ZIP, snapshots the databases first, and *replaces* the data in one transaction.
- Soft-deleted KPIs are hidden everywhere, KPI templates work, and periodic results come back in chronological order.

### Web app
- **Target Entry.** Inputs reset when the year or plant has no data, blank boxes are never saved as 0, formula KPIs are read-only, and a confirmation appears before saving to all facilities.
- **KPI Explorer.** No render loop, edits survive refetches, deletes ask for confirmation, and the tree works with the keyboard. The audit history says what changed, and names plants and target scenarios.
- **First run.** A fresh install offers to create the first (admin) account. This regressed during the release.
- **Sessions and errors.** Only a 401 signs you out; network errors show a retry screen. Failed saves raise a toast, and the cache is cleared on sign-out.
- **Container.** The app calls `/api` on its own origin (Vite and nginx proxy it), so it works from any host.
- **Accessibility and tooling.** Labelled inputs, ARIA names, visible focus, and better contrast. Strict TypeScript, react-hooks lint rules, vitest, and a smaller initial bundle (charts are lazy-loaded).

### Packaging and operations
- Fixed `requirements.txt` and `pyproject.toml` (the `mcp` dependency was missing; removed GUI dependencies were dropped) and pinned versions; regenerated `uv.lock`.
- The backend image shrank from 1.24 GB to 513 MB and is built once for both backend and MCP.
- Compose gained healthchecks, start ordering, and configurable ports (`FRONTEND_PORT`, `BACKEND_BIND_ADDRESS`, `MCP_BIND_ADDRESS`).
- Containers no longer run as root. Existing volumes may need `chown -R 1000:1000` (see the README).
- New scripts: `scripts/dev_backend.py` (throwaway dev database), `scripts/seed_demo.py` (demo data), `scripts/capture_screenshots.py` (doc screenshots).

### Removed
- The Tkinter and Streamlit GUIs. They bypassed login, wrote to SQLite directly, and Streamlit no longer started.

### Docs
- Rewrote the README and every guide.
- New [user guide](docs/user_guide.md) with screenshots of every screen, a new [MCP guide](docs/mcp.md), and an architecture diagram.

## [2.0.0] - 2026-07-25

### Added
- **React Web App** (`frontend/`): full-featured primary UI covering Target Entry (dynamic per-KPI target count, repartition/global-split controls, broadcast-to-all-plants), KPI Explorer (spec inspector, formula editor with quick-insert KPI/operator/function toolbar, plant visibility matrix, audit history viewer), Global Splits & multivariate ML predictor, Analysis, Facilities, and Data Utilities.
- **FastAPI REST API** (`src/api.py`): ~70 endpoints exposing the full backend (KPI/hierarchy CRUD, annual targets + repartition trigger, global splits, templates, plants, multivariate analysis, CSV export, ZIP backup/restore, users/auth).
- **MCP Server** (`src/mcp_server.py`): stdio transport (local clients) and a new HTTP transport (`--http`, API-key gated) for shared/containerized use.
- **Accounts & login**: password-based registration/login required to use the React app and REST API (server-enforced via middleware, not just UI). Sessions, password hashing (PBKDF2-HMAC-SHA256), and a password-change flow under Data Utilities.
- **Audit trail**: every target value and KPI definition change is attributed to the authenticated user and timestamped; visible in the KPI Explorer.
- **MCP API keys**: separate per-user credential for the MCP HTTP transport, issued/revoked from Data Utilities; the resolved identity overrides any caller-claimed `changed_by`.
- **Custom target labels**: each KPI can name its own target scenarios (e.g. "Budget"/"Committed") instead of the fixed "Target 1/2".
- **Containerization**: `Dockerfile`s for backend and frontend, `compose.yml` (renamed from `podman-compose.yml` for tool auto-discovery) orchestrating backend + frontend + `mcp_server`, all three images built and verified end-to-end.

### Changed
- **Backup/restore**: replaced the human-readable CSV export (which never matched what restore expected) with a raw per-table dump/restore pair that actually round-trips, preserving primary keys and relationships.
- **Container base image**: bumped from `python:3.10-slim` to `python:3.12-slim` (`requirements.txt`'s `numpy>=2.3.2` requires 3.11+; this previously made the backend image unbuildable).
- **Repo hygiene**: moved `multivariate_test_results.png` into `data/` alongside its source CSV; test script now writes both there instead of the repo root.
- Rewrote `README.md`, `frontend/README.md`, and `docs/` (architecture, database schema, new API reference, new code-depth guide) to reflect the current four-interface architecture; removed a stale, partly-fictional legacy spec doc.

### Known gaps
- Selecting a Global Split on a Target Entry card silently overrides that KPI's own Repartition Logic/Distribution Profile fields, but the UI still lets you edit them without saying so.
- `target_granularity` is stored and editable per KPI but not yet read by any calculation logic — descriptive only for now.
- No role-based access control yet: any logged-in user can create other accounts.

## [1.4.0] - 2026-04-01

### Added
- **Universal Global Splits**: Introduced a unified split definition that automatically applies to all aggregation levels (Daily, Weekly, Monthly, Quarterly).
- **Multi-Year Support**: Global Splits can now be assigned to multiple years simultaneously, with a dedicated mapping table in the database.
- **Enhanced KPI Explorer (Tkinter)**: 
    - Added "Move Node" and "Move KPI" functionality to easily reorganize the hierarchy.
    - Improved creation logic to allow placing new elements at the Root level or inside selected nodes.
- **Standardized Split Indicator**: Both GUIs now identify and highlight "Standard" Global Split assignments with a ⭐ icon in the Target Entry page.
- **Automated Weight Preview**: The Global Split editor now dynamically generates and previews weights for all levels (Monthly/Quarterly) when a profile is selected.

### Changed
- **Project Structure**: Consolidated redundant entry points and moved utility scripts to `src/scripts/` for better project organization.
- **UI Optimization**: Cleaned up labels in Target Entry; `(Incremental)` calc type is now hidden by default to reduce visual noise.
- **Dependency Update**: Refined `requirements.txt` with strict versioning and missing ML/Excel libraries.

### Fixed
- **Root Level Visibility**: Fixed an issue where indicators moved to the root level were hidden in the KPI Explorer tree.
- **AttributeError**: Resolved a crash in the Tkinter Target Entry tab caused by incorrect module mapping.
- **SQL Security**: Audited and improved SQL query safety across the backend logic.

## [1.3.0] - 2026-03-31

### Added
- **Visual Node Editor (Streamlit)**: High-performance Canvas-based graph editor for KPI formulas. Supports draggable nodes, dynamic sockets, and bidirectional sync with raw expressions.
- **Individual Table Export**: Granular export functionality for specific database tables (Plants, Hierarchy, Definitions, Targets) in both GUIs.
- **Handshake Protocol**: Implemented strict Streamlit component handshake to resolve iframe loading timeouts.

### Changed
- **Workspace Hygiene**: Cleaned up the project root by moving management files to `conductor/` and user configurations to `user_config/`.
- **Streamlit Data Center**: Promoted individual table exports to the top of the interface for better accessibility.

## [1.2.0] - 2026-03-20

### Added
- **"On-the-Fly" Calculation Engine**: Implemented daily formula evaluation for calculated KPIs, allowing them to dynamically inherit seasonality from dependencies.
- **Precision Reconciliation**: Added a layer to ensure that daily splits perfectly align with annual targets (Sum for Incremental, Mean for Average), automatically adjusting for rounding errors.
- **Topological Sort**: Implemented dependency-based calculation order for complex KPI chains.
- **Multivariate Seasonality Predictor (Streamlit)**: Ported the ML-driven predictor to the web interface with interactive Plotly fit charts and unified creation/edit workflows.
- **Sequential Timeline Analysis**: Implemented a continuous chronological X-axis for multi-year trends, enabling clear year-over-year comparisons.
- **Recursive Tree Navigation**: Redesigned Streamlit KPI Explorer with a nested expander system for better hierarchy visualization.
- **Quick-Find Sidebar**: Added a fast search and navigation sidebar to the Streamlit Target Entry page.
- **Sample Data**: Added `multivariate_test_data.csv` for verifying the predictive model.

### Changed
- **Optimized Data Export**: Refactored `export_manager` to reduce file count from 14 to 8, while enriching CSVs with human-readable metadata (names, paths).
- **Streamlit Navigation**: Restructured the web interface into logical categories (Operation, KPI Management, Configuration, Data & Analysis) to match the Tkinter desktop app.
- **Documentation Overhaul**: Recreated the `docs/` directory with structured technical references (Architecture, Database Schema, Feature Guides).
- **Project Structure**: Moved reports and guides to `docs/` for better workspace hygiene.

### Fixed
- **Plotly ID Conflicts**: Resolved duplicate element IDs in the Analysis dashboard.
- **KeyError 'period'**: Fixed data frame parsing issues in periodic trend views.
- **URL Path Conflicts**: Resolved Streamlit page title inference errors by implementing explicit `url_path` parameters.

## [1.1.0] - 2026-03-19
### Added
- Initial support for averaging multiple historical target columns in multivariate analysis.
- Basic circular dependency checking for formulas.

## [1.0.0] - 2026-03-15
### Added
- Initial release with dual Tkinter/Streamlit interfaces and SQLite backend.
