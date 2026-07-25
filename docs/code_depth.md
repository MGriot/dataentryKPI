# Code-Level Deep Dive

This page covers the parts of the core logic that are dense enough to deserve a walkthrough with real code references, and that aren't already covered by [architecture.md](architecture.md), [database_schema.md](database_schema.md), or [api_reference.md](api_reference.md).

## The Formula/DAG Engine (`src/core/node_engine.py`)

A calculated KPI (`kpis.is_calculated = 1`) can be defined two ways, both ultimately evaluated by `KpiDAG`:

- **Visual node graph** (`formula_json`): a graph of `KpiNode`s (`kpi_input`, `constant`, `operator`, `output`) connected by `KpiEdge`s, built by the Tkinter Node Editor dialog. `KpiDAG.from_json(...)` reconstructs the graph; `KpiDAG.evaluate(kpi_resolver, default_target_num=...)` walks it, calling `kpi_resolver(kpi_id, target_num)` for each `kpi_input` node to fetch that dependency's value.
- **Expression string** (`formula_string`): a simpler `[KPI_ID]`-token syntax, e.g. `[12] * 0.85 + [7]`, evaluated by substituting each `[id]` with `context_vars["kpi_{id}"]` and running `eval()` against an allowlist of builtins (`abs`, `min`, `max`, `round`) with `__builtins__` set to `None`.

Both `target_management/annual.py` (annual target resolution) and `target_management/repartition.py` (per-day resolution during repartition) call into this — see the "Data Flow: Target Calculation" section in [architecture.md](architecture.md) for why dependency order matters for the latter.

## Reconciliation Math (`target_management/repartition.py`)

After a distribution profile (even/progressive/sinusoidal/weekday-bias/event-based) generates raw daily values, floating-point drift means the sum (Incremental KPIs) or mean (Average KPIs) won't exactly equal the annual target. `_reconcile_and_adjust_daily_values(daily_values, target_annual, kpi_calc_type)` fixes this by computing the difference and spreading it evenly across every day:

```python
diff = target_annual - current_val         # current_val = sum() or mean() depending on calc type
adjustment = diff / daily_values.size
daily_values += adjustment                  # same operation works for both Sum and Average KPIs --
                                             # adding a constant to every day shifts the mean by exactly
                                             # that constant, and shifts the sum by constant * n_days
```

Event adjustments (`_apply_event_adjustments_to_daily_values` — start/end date, multiplier or addition, from a distribution profile's `profile_params.events`) are applied *before* this reconciliation step, so a shutdown event's effect is preserved rather than smoothed away.

## Actuals Status & Trend (`src/services/actuals_service.py`)

`evaluate_performance_status(actual, target, direction, threshold_json)` — the exact thresholding logic (Higher/Lower/Range is Better, `warning_margin`/`error_margin`) is documented in [api_reference.md](api_reference.md) and was covered in detail when the KPI spec's threshold fields were added to the UI.

`calculate_trend_slope(values)` is a plain least-squares linear regression slope over the index (not the date) of each value in the series:

```python
x_mean = (n - 1) / 2.0
y_mean = mean(values)
slope = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values)) / sum((i - x_mean) ** 2 for i in range(n))
```

Positive = trending up, negative = trending down, `0.0` for fewer than 2 points. `get_performance_status_for_kpi` applies the KPI's `time_filter_type`/`time_filter_value` (a rolling N-day window) to the actuals series *before* computing status and trend, not after.

## CSV Export Layouts (`src/export_manager.py`)

Two independent shapes exist for two independent purposes — see the note in [architecture.md](architecture.md) for why only one of them round-trips through restore:

**Enriched (BI-friendly, `export_all_data_to_global_csvs` / single-table export, not restorable):**
- `dict_plants.csv` — `id, name, description, visible, color`
- `dict_kpi_hierarchy.csv` — `id, name, parent_id, node_type`
- `dict_kpi_definitions.csv` — `kpi_id, indicator_name, hierarchy_path, description, calculation_type, unit_of_measure, visible` (joined/computed columns, not raw table columns)
- `dict_kpi_plant_visibility.csv` — `kpi_id, plant_id, is_enabled`
- `all_annual_targets.csv` — `id, year, plant_id, plant_name, kpi_id, indicator_name, annual_target1, annual_target2, repartition_logic`
- `all_periodic_targets.csv` — `year, plant_id, kpi_id, target_number, period_type, period_value, target_value` (days/weeks/months/quarters unified into one file)

**Raw (backup/restore, `export_raw_backup_csvs`, exactly matches what `import_manager.import_from_zip` expects):** one file per table (`raw_plants.csv`, `raw_kpis.csv`, `raw_annual_targets.csv`, `raw_kpi_annual_target_values.csv`, ...), every column including primary and foreign keys, via `PRAGMA table_info` — see [database_schema.md](database_schema.md) for the full table list.
