# TODO

Open work, roughly by priority. Completed items are recorded in [CHANGELOG.md](../CHANGELOG.md) and the [audit report](audit.md).

## Security
- **Session token storage (AUDIT SEC-08).** The 30-day token lives in `localStorage`; a CSP now limits the impact of XSS. Moving to an HttpOnly, SameSite cookie would also need CSRF protection on the API.
- **Password reset without an admin.** There is no "forgot password" flow; an admin resets passwords.

## Features
- **Actuals in the UI.** Actuals and the performance status (`/actuals`, `/kpis/{id}/status`, and the matching MCP tools) have no screen in the web app yet. Add actuals entry or import, and show the status in Target Entry and Analysis.
- **KPI definition templates in the UI.** Templates work through the API and MCP, but the web app has no screen for them yet (the API client already has the read calls).
- **Move and rename** folders and KPIs (there is no API for it yet).
- **`target_granularity`** is stored and editable but informational only. Either make it drive the default repartition logic, or remove it.
- **Named scenarios everywhere.** Custom target names are shown in Target Entry and the history, but Analysis still says "Target 1/T1".

## Performance
- Target Entry loads each KPI's annual entry for three years with one request per KPI per year. Use one batched `GET /targets/annual` per year instead.
- `recalculate_kpis` re-runs every year and plant a KPI has data for. That's fine at the current scale; consider a background job if it grows.

## Engineering
- Generate the TypeScript API types from the FastAPI OpenAPI schema instead of maintaining `frontend/src/types` by hand.
- Add an end-to-end browser test suite. `scripts/capture_screenshots.py` already drives every screen with Playwright and could become the base.
- Add CI: pytest, frontend typecheck, lint and test, and a compose build.
