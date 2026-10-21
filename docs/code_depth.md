# Code-level deep dive

The parts of the core that are dense enough to deserve a walkthrough, with file and function references. The behaviour itself is described in [features.md](features.md); this page explains how the code implements it.

## The save and recalculation pipeline (`src/target_management/annual.py`)

`save_annual_targets(year, plant_id, targets_data_map, changed_by)` is called by `POST /targets/annual` and by the MCP `save_annual_targets` and `update_target_value` tools.

1. **Validate before opening a transaction.**
   - The year must be in range and the plants must exist (`TargetValidationError`).
   - `_parse_inputs` rejects values for calculated KPIs and per-target formulas, and keeps `None` as "leave unchanged".
2. **Open one engine connection** (`repartition.engine_connection()`). It has the targets database as `main`, with the four period databases and the history database ATTACHed, so every write below commits or rolls back together.
3. **Per plant:**
   1. `_ensure_annual_row`, then `_upsert_value` for each entered value. `_upsert_value` writes a `target_value_history` row only when the value actually changed.
   2. `_recalculate_in_tx(conn, year, plant, seeds=entered KPIs, ...)` works out what to redo:
      - `formula_graph(specs)` builds `{kpi: {inputs}}` from every calculated KPI's `formula_string`, or from its `formula_json` DAG via `kpi_dependencies`.
      - `_dependents_closure(graph, seeds)` is the set of seeds plus every KPI that depends on them transitively.
      - `_topo_order(graph, affected)` is a DFS topological sort, so inputs are always handled before the KPIs that use them.
   3. For each affected KPI in that order:
      - **Calculated KPIs:** `_compute_formula_annual` evaluates the formula for each target number *N* over the inputs' target *N*, and stores the value with `is_formula_based=1`.
      - **Every KPI:** `_repartition_kpi` runs (next section).

`recalculate_kpis(kpi_ids, years=None)` reruns step 3 for KPIs whose definition changed, for every year and plant that has data. It is called after:
- a formula, aggregation-type or target-count change (`kpi_crud.update_kpi_spec_extended`);
- split assignment (`PUT /kpis/{id}/global-split`).

`recalculate_indicators` does the same for split-template edits, which link indicators rather than KPIs.

**Formula validation** happens on save of the KPI definition, not on target save. `validate_formula(kpi_id, formula)` does three things:
1. compiles the formula (`core.formula.compile_formula`);
2. checks every `[id]` exists and isn't the KPI itself;
3. adds the new edges to the graph and runs `find_cycle`. The error message names the cycle path.

## Repartition (`src/target_management/repartition.py`)

`_repartition_kpi` (annual.py) chooses between two paths for each target number:

- **Calculated KPI with input series.** `_formula_daily_series` reads each input's daily targets (`read_daily_series`) and evaluates the compiled formula day by day. `reconcile(series, annual_value, additive)` then scales the result so it matches the stored annual value exactly.
- **Everything else:**
  1. `resolve_distribution(kpi, entry, year, split_lookup)` returns `(logic, weights, profile, params)`, in precedence order: the assigned split covering the year, legacy per-record settings, the KPI's default profile, then even.
  2. `compute_daily_values(year, value, calc_type, logic, weights, profile, params)` builds the series:

```python
shape = _profile_shape(dates, profile, params)        # relative day weights over the year
groups = [_period_of(d, logic) for d in dates]        # month / quarter / ISO-week index per day
weights = parse_period_weights(logic, values)         # "January"/"Q1"/"W01" (and legacy keys) -> index
if additive:      # each period gets its share of the total, split by the day shape inside it
    daily[g] = target * w[g] / sum(w) * shape[g] / shape[g].sum()
else:             # weights are relative levels, normalised so the day-weighted mean is the target
    daily[g] = target * (w[g] / day_weighted_mean(w)) * shape[g] / shape[g].mean()
daily = _apply_events(daily, dates, params["events"])  # date ranges: value * multiplier + addition
daily = reconcile(daily, target, additive)             # scale (never shift) to the exact sum / mean
```

`reconcile` scales instead of adding a constant. Shifting every day by `(target - sum) / n` could push low days negative; scaling can't. A series that sums to zero is replaced by a flat one.

`save_periodic_targets` replaces the KPI's rows for that year, plant and target number:
- `daily_targets` gets one row per day;
- `aggregate_periods` groups the days by ISO week (`YYYY-Www`, using the ISO year), month name and `Q1`..`Q4`, aggregating with the KPI's own rule (`sum`, `mean`, last, `min`, `max`).

ISO weeks spanning New Year are therefore stored under their ISO year's label.

## The formula evaluator (`src/core/formula.py`)

1. `compile_formula(text)` rewrites each `[12]` as the name `__kpi_12` and parses the result with `ast.parse(mode="eval")`.
2. `_validate` walks the tree and accepts only these nodes:
   - `Expression`, `BinOp` (`+ - * / % **`), `UnaryOp` (`+ -`) and numeric `Constant`s;
   - `Name`s matching `__kpi_<id>`;
   - `Call`s to `abs`, `min`, `max` or `round` with positional arguments.

   Anything else (attributes, subscripts, other names, keywords, strings, lambdas, comprehensions) raises `FormulaError`. Size limits: 2,000 characters and 300 nodes.
3. `CompiledFormula.evaluate(values)` walks the validated tree with plain Python operators:
   - `x / 0` and `x % 0` return `zero_division_value` (default 0);
   - `**` is bounded (exponent ≤ 64, base ≤ 1e12, no fractional power of a negative base);
   - a non-finite result raises `FormulaError`.

`eval` is never called. The security tests (`tests/test_formula.py`) include the old sandbox escape `().__class__.__base__.__subclasses__()`.

## Database connections (`src/data_access/db.py`)

```python
with db.connect(db.TARGETS, attach={"days": db.DAYS, "hist": db.HISTORY}) as conn:
    ...  # main.annual_targets, days.daily_targets, hist.target_value_history
# commit on success, rollback on any exception, always close
```

Every connection gets a busy timeout, foreign keys enabled, and `sqlite3.Row` rows. Identifiers that have to be interpolated, such as column names in `UPDATE ... SET`, go through `db.ident`, which only allows `[A-Za-z_][A-Za-z0-9_]*`. Values are always bound parameters.

Cross-file references (`plant_id` everywhere, `global_split_id`, `indicator_id` in the template tables) can't be SQLite foreign keys, because SQLite foreign keys don't cross files. The code cleans them up instead:
- `plants_management.crud.delete_plant(force=True)` deletes the plant's rows in every file, in one ATTACHed transaction;
- `splits.delete_global_split` returns the affected indicators so they can be recalculated.

## Roles: one implementation, two transports (`src/user_management/access.py`)

`access.py` holds every account rule:
- `require_admin` and `require_self_or_admin`;
- `list_users`, which trims profiles for non-admins;
- `update_user`, where a non-admin can't change `is_active` or `is_admin`;
- `reset_password`, plus `create_api_key`, `list_api_keys` and `revoke_api_key`.

All of them take the authenticated **actor** and raise `AccessDenied` (a `PermissionError` subclass), `LookupError` or `ValueError`.

- **REST:** the actor is the session user. `AccessDenied` becomes 403 through an exception handler in `api.py`.
- **MCP:** `_caller()` in `mcp_server.py` builds the actor. Over HTTP it re-reads the API key's owner on every call, so a demoted or deactivated user loses access at once. Over stdio it is `{id: None, name: $MCP_STDIO_USER, is_admin: $MCP_STDIO_ADMIN}`.

## MCP tool registration (`src/mcp_server.py`)

Tools are plain functions registered through a local `tool(read_only=..., destructive=..., idempotent=...)` decorator inside `build_server`. The decorator does two things:
- It attaches `ToolAnnotations`.
- It wraps the function so that **anticipated** errors (`ValueError`, `LookupError` and their subclasses, plus `AccessDenied`) become `ToolError`s, whose message the model sees. Without this, the SDK reports any other exception only as "Error executing tool …". `KeyError` and `IndexError` are treated as bugs and keep the generic message.

Other details:
- Sync tools run in a worker thread (the SDK uses `anyio.to_thread`), so the CPU-heavy `analyze_seasonality` doesn't block the HTTP server. `contextvars` propagate, so `get_access_token()` still works there.
- `build_http_app()` returns the stateless Streamable HTTP ASGI app with `ApiKeyVerifier` as the SDK token verifier, plus DNS-rebinding protection when bound to a non-loopback host.
- `tests/test_mcp_server.py` drives the server with the SDK's in-memory `Client`, and the HTTP app through Starlette's `TestClient`.

## Backup format (`src/export_manager.py`, `src/import_manager.py`)

`build_backup_zip()` writes:
- `manifest.json` (format version, timestamp, tables);
- one `raw_<table>.csv` per table in `RAW_BACKUP_TABLES`, with every column in dependency order, and `\N` for NULL (an empty string stays an empty string).

`restore_from_zip(bytes)` runs in this order:
1. `_read_backup` checks the ZIP: known names only, the uncompressed-size cap, and parseable CSVs.
2. Every column is checked against the live schema (`PRAGMA table_info`).
3. `_snapshot_databases()` copies the files to `backups/pre-restore-<timestamp>/`.
4. On one connection with every KPI database ATTACHed, foreign keys are turned off, each table in the backup is emptied, and its rows are inserted with their original ids. `_coerce` maps `\N` and empty numeric cells to NULL. The transaction then commits.

Any error rolls back the whole restore and raises `RestoreError` (400), which carries no traceback.
