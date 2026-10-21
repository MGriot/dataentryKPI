# KPI Target Manager: frontend

The React, TypeScript and Vite web app for the Data Entry KPI Target Manager. It covers KPI definitions, target entry, split templates and the ML seasonality predictor, multi-plant analysis, facilities, backups and accounts. See the [user guide](../docs/user_guide.md) for screenshots.

It is a thin client: repartition, formulas, the ML race, roles and the audit trail all live in the FastAPI backend (`../src/api.py`).

## Requirements

- Node 22+
- The backend running. In development: `python scripts/dev_backend.py` from the repo root (API on :8000).

## Scripts

```bash
npm install
```
```bash
npm run dev
```
`npm run dev` serves the app on http://localhost:5173 and proxies `/api` to the backend.

| Script | What it does |
|---|---|
| `npm run build` | Type-check, then a production build into `dist/` |
| `npm run typecheck` | `tsc -b` (strict mode) |
| `npm run lint` | oxlint, including react-hooks rules, with warnings treated as errors |
| `npm test` | vitest (jsdom): API client, form and split utilities, history descriptions, and the sign-in screen |
| `npm run preview` | Serve the production build |

## How it talks to the API

The app always calls **`/api/...` on its own origin** (`API_BASE` in `src/services/api.ts`):

| Where | What forwards `/api` |
|---|---|
| Development | Vite proxies `/api` to `VITE_DEV_BACKEND` (default `http://127.0.0.1:8000`) and strips the prefix |
| Container | nginx (`nginx.conf`) proxies `/api/` to `backend:8000` |

Set `VITE_API_URL` at build time only if the API lives on another origin. It must then be listed in the backend's `CORS_ORIGINS`.

Error and session handling:
- Errors arrive as `ApiError` with the server's `detail` message.
- A **401** clears the session and shows the sign-in screen.
- Network errors and 5xx keep the session and show a retry screen.
- Failed saves raise a toast.

## Structure

```
src/
├── App.tsx                    Query client, auth gate (sign-in / retry / workspace), tab state, lazy chart tabs
├── components/
│   ├── Header.tsx             Tabs, quick search, year and facility selectors, refresh, user menu
│   ├── LoginScreen.tsx        Sign in / first-account creation / registration (when open)
│   ├── TargetEntryWorkspace.tsx   Per-KPI target cards, named scenarios, broadcast to all facilities
│   ├── KpiManagerWorkspace.tsx    Hierarchy tree, KPI inspector, formula editor, visibility, audit history
│   ├── GlobalSplitsWorkspace.tsx  Split template CRUD and the ML seasonality predictor (lazy-loaded)
│   ├── AnalysisWorkspace.tsx      Multi-plant charts and the annual summary table (lazy-loaded)
│   ├── PlantsWorkspace.tsx        Facility CRUD
│   ├── SettingsWorkspace.tsx      CSV exports, backup and restore
│   ├── ChangePasswordPanel.tsx    Your password
│   ├── UsersAdminPanel.tsx        Users (admins) and MCP API keys
│   ├── UserMenu.tsx, Toasts.tsx
├── hooks/index.ts             React Query hooks. Every data mutation invalidates the data queries;
│                              sign-out drops every cached query except the sign-in status.
├── services/api.ts            Typed REST client (the only place that knows URLs)
├── types/index.ts             Shared types, option lists, targetLabel()
└── utils/                     session.ts (token storage + cross-tab sign-out), forms.ts, splits.ts,
                               history.ts (audit history in words), toast.ts
```

There is no router: navigation is the `activeTab` state in `App.tsx`.

The app shell is `100vh`, and each workspace scrolls inside `<main>`. Keep that in mind when scrolling programmatically or taking full-page screenshots; `scripts/capture_screenshots.py` handles it.

## Design system

A dark theme defined in `src/index.css`:
- CSS custom properties: `--bg-*`, `--accent-*`, `--text-*`;
- shared classes: `.card`, `.glass-card`, `.sub-panel`, `.btn`, `.badge`, `.select-control`, `.nav-tab`, `.field-label`, `.field-hint`.

Reuse these rather than adding colours. Muted text meets 4.5:1 contrast, and focus rings are visible.

Accessibility:
- Inputs have linked `<label>`s.
- Icon-only buttons have `aria-label`s.
- The active tab has `aria-current`.

## Container build

`Dockerfile` builds in two stages:
1. `npm ci && npm run build` on `node:22-alpine`;
2. `dist/` served by `nginx:1.27-alpine`, using `nginx.conf`.

nginx serves the app with SPA fallback and sends security headers (CSP, `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`). It proxies `/api/` to the backend container, using the client's address as `X-Forwarded-For` for the login rate limiter.
