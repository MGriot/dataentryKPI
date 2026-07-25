# KPI Target Manager — Frontend

React + TypeScript + Vite web app for the Data Entry KPI Target Manager. This is the primary UI: KPI definition, target entry with automatic daily/weekly/monthly repartition, global seasonal split templates (including an ML-driven predictor), multi-plant analysis, facility management, and data/backup utilities.

It's a thin client — all business logic (repartition math, formula evaluation, ML model racing, audit history) lives in the FastAPI backend (`../src/api.py`). This app just renders it and calls the REST API.

## Requirements

- Node 20+
- The backend running and reachable (default `http://localhost:8000`) — see the [repo root README](../README.md) for how to start it.

## Development

```bash
npm install
npm run dev
```
Opens on `http://localhost:5173`. Set `VITE_API_URL` if the backend isn't at the default `http://localhost:8000`:
```bash
VITE_API_URL=http://localhost:9000 npm run dev
```

## Build

```bash
npm run build      # tsc -b && vite build -> dist/
npm run preview    # serve the production build locally
```

## Structure

```
src/
├── App.tsx                 # QueryClientProvider, tab state, wires Header + the active workspace
├── components/
│   ├── Header.tsx           # Nav tabs, year/plant/search selectors, UserPicker
│   ├── UserPicker.tsx        # Active-profile selector (localStorage) -- stamped on every save as `changed_by`
│   ├── TargetEntryWorkspace.tsx   # Per-KPI target cards, dynamic target count, repartition + global split controls
│   ├── KpiManagerWorkspace.tsx    # Hierarchy tree, spec inspector, plant visibility matrix, audit history
│   ├── GlobalSplitsWorkspace.tsx  # Split template CRUD + multivariate ML predictor & chart
│   ├── AnalysisWorkspace.tsx      # Multi-plant target charts + summary table
│   ├── PlantsWorkspace.tsx        # Facility CRUD
│   ├── SettingsWorkspace.tsx      # CSV export, ZIP backup/restore
│   └── UsersAdminPanel.tsx        # User + MCP API key management (rendered inside SettingsWorkspace)
├── hooks/index.ts            # React Query hooks (one per API resource/mutation)
├── services/api.ts           # Typed REST client -- the only place that knows the backend's URL shape
├── types/index.ts            # Shared TS interfaces + option constants (mirrors backend Pydantic/DB shapes)
└── utils/currentUser.ts      # getCurrentUserName()/setCurrentUserName() -- the localStorage-backed active profile
```

No router is used — navigation is a single `activeTab` string in `App.tsx`, matching the tab-based layout; each workspace is a sibling, not a route.

## Design system

Dark glassmorphism theme defined entirely in `src/index.css` as CSS custom properties (`--bg-*`, `--accent-*`, `--text-*`) plus reusable classes (`.glass-card`, `.card`, `.btn`, `.badge`, `.select-control`, `.nav-tab`). New UI should reuse these classes/tokens rather than introducing new colors.

## Container build

`Dockerfile` is a two-stage build: `npm ci && npm run build` in a Node stage, then the static `dist/` is served by `nginx` (`nginx.conf`) on port 80. `VITE_API_URL` is a build-time `ARG` — it gets baked into the JS bundle, so set it at `podman-compose build` time (see `compose.yml`), not at container runtime.
