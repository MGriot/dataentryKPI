# Core logic

How the system turns annual targets into periodic ones, computes formula KPIs, derives seasonality from data, and judges performance. All of this lives in the shared Python core, so the web app, the REST API and the MCP server behave identically. Code-level details are in [code_depth.md](code_depth.md).

## 1. Aggregation types

A KPI's **aggregation type** decides what its annual target means:

| Type | Meaning of the annual target | Days → periods |
|---|---|---|
| **Sum**, **Count** (*additive*) | A total. Periods add up to it. | sum |
| **Average** (*level*) | A level the year should average | mean |
| **Last**, **Min**, **Max** (*level*) | A level | last day, minimum, maximum |

Legacy names are still accepted: `Incremental` means Sum.

## 2. Repartition: annual → day, week, month, quarter

Every saved annual target is turned into a **daily series** for its year. The daily series is then aggregated into ISO weeks (`2026-W05`), months and quarters using the KPI's aggregation type. The daily series is built in four steps (`target_management/repartition.py`).

1. **Day shape (the profile).** Gives every day of the year a relative weight:
   - `even_distribution`: flat.
   - `annual_progressive`: a linear ramp from 0.8 to 1.2 over the year.
   - `annual_progressive_weekday_bias`: the ramp × 1.3 on weekdays and 0.7 at weekends (configurable).
   - `true_annual_sinusoidal`: 1 + *a*·sin(2πt + φ), with amplitude *a* (default 0.1) and phase φ.
   - `event_based_spikes_or_dips`: flat, plus events (see step 3).
2. **Period weights (the repartition logic).** **Month**, **Quarter** or **Week** weights decide how much of the year each period gets. They are keyed by month name, `Q1`..`Q4` or `W01`..`W53`, and matched by ISO week number. Week templates are therefore year-agnostic.
   - **Additive KPIs:** each period gets `weight / Σweights` of the annual total. Its days split that share according to the day shape. A period with weight 0 really gets 0.
   - **Level KPIs:** weights are relative levels, normalised so that the day-weighted average is the annual target. Periods without a weight get the average weight.
   - **Year logic,** or no usable weights, means one period: the whole year follows the day shape.
3. **Events.** `profile_params.events` is a list of `{start_date, end_date, multiplier, addition}`, applied to the days in each range. A shutdown, for example, uses multiplier 0.
4. **Reconciliation by scaling.** The series is scaled so its sum (additive KPIs) or mean (level KPIs) equals the annual target exactly. Scaling never makes a day negative, unlike the earlier shift-by-a-constant approach.

**Where the settings come from**, in order of precedence:
1. the split template assigned to the KPI, if it covers the year;
2. a template or settings saved on the annual record by older API clients;
3. the KPI's default profile;
4. an even split.

The UI's "Default even split" is literally that.

Edge cases are covered by tests: leap years (366 days), ISO weeks that belong to the neighbouring year (29–31 Dec in W01, 1–3 Jan in W52/53), and all-zero weights.

## 3. Split templates

A split template (`global_kpi_splits`) is a named combination of repartition logic, weights, day shape and profile parameters. It can apply to every year or to specific years (`global_split_years`) and is linked to KPIs through `global_split_indicators`. Every change recalculates the affected KPIs' stored targets:
- assigning or clearing a template;
- editing its weights, profile or years;
- changing its linked KPIs;
- deleting it.

Five presets are seeded once: Uniform / Even, Annual Progressive, Annual Progressive (Weekday Bias), Sinusoidal Seasonal Curve, and Event Based (Shutdowns). `GET /global-splits/curve-preview` (MCP: `get_curve_weight_suggestions`) turns a curve into starting weights for a new template.

## 4. Formula KPIs

A KPI with a formula is **calculated**: it can't be typed in, and it is recomputed whenever an input changes.

- **Syntax.** KPI references are written `[id]` (the input KPI's spec id). Allowed: numbers, `+ - * / % **`, parentheses, unary minus, and `abs`, `min`, `max`, `round`. Example: `([1] - [5]) / max([2], 1)`.
- **Safety.** Formulas are parsed with Python's `ast` and evaluated by walking a strict whitelist of node types (`core/formula.py`). Nothing reaches `eval`.
  - Attribute access, names, subscripts, strings, comprehensions and keyword arguments are rejected.
  - Formulas are capped at 2,000 characters and 300 nodes. Exponents are bounded, and division by zero yields 0.
- **Validation on save.** The formula must parse, every referenced KPI must exist, it may not reference itself, and it may not create a dependency cycle. An error names the cycle, e.g. `[2] -> [4] -> [2]`.
- **Per scenario.** Target *N* of a calculated KPI is computed from target *N* of its inputs.
- **Annual and daily.** The annual value is computed from the inputs' annual values. The daily series is computed day by day from the inputs' daily series, then scaled to the annual value. A ratio KPI therefore follows the seasonality of its inputs, instead of re-splitting the annual ratio evenly.
- **Dependency order.** A save recomputes, in topological order, every formula KPI that depends directly or transitively on what changed, all inside the same transaction.
- A visual DAG (`formula_json`, evaluated by `core/node_engine.py`) is also supported. Its input nodes can pin a specific target number.

## 5. ML seasonality predictor

`services/split_analyzer.py` derives split weights from history:

1. **Load** a CSV or Excel file (size-capped; at most 1M rows and 200 columns). Parse the date column; coerce targets and drivers to numbers.
2. **Aggregate per period** (month, quarter or ISO week). Targets are averaged across years, so a period that appears in more years isn't over-weighted. Drivers are averaged.
3. **Normalise.** Each target is expressed as a **share of its mean**, so a value of 1.2 means 20% above an average period. Several targets are averaged. Drivers are min-max scaled.
4. **Race the models.**
   - Without drivers, the historical profile is used directly ("Historical Average").
   - With drivers, OLS, Ridge (α = 1) and a Random Forest (100 trees, depth ≤ 5) are fitted.
   - The best R² wins, after a complexity penalty: the forest loses 0.2 below 24 periods and 0.1 below 50, and OLS loses 0.05 when there are more drivers than half the periods.
5. **Uncertainty.** 100 Monte Carlo runs perturb the drivers and add residual noise, giving the 5th and 95th percentile band.
6. **Weights.** The prediction becomes **percentages summing to 100**, keyed exactly like template weights (`January`, `Q1`, `W01`). It can be published as a template unchanged.

The result also includes the coefficients (or the forest's feature importances), R², the plot data and the winning model's name.

## 6. Actuals and performance status

Measured values (`actual_measurements`, one per KPI, plant and day) are compared with a target by `services/actuals_service.py`:

| Direction | on_track | warning | out_of_range |
|---|---|---|---|
| Higher is better | actual ≥ target | within `warning_margin` below the target | further below |
| Lower is better | actual ≤ target | within `warning_margin` above the target | further above |
| Range | inside [`min_target`, `max_target`] | within `error_margin` × span outside the range | further out |

- Margins come from the KPI's `threshold_json` (defaults: warning 0.05, error 0.15) and are relative to |target|, so negative targets work too.
- The **trend** is the least-squares slope of the actuals series.
- With `time_filter_type = Rolling`, only the last *N* days are considered.

## 7. Audit trail

- **Definition changes.** Every KPI create, update and delete is stored with the user, the time, and the old and new values. Re-saving identical values isn't recorded.
- **Target values.** Every annual target value that actually changes is recorded with the plant, the scenario, and the old and new values.
- The user is always taken from the session or API key, never from the request.

## 8. Backup and restore

- **Backup** is a ZIP with a 1:1 CSV dump of every KPI table, plus a manifest. All columns and primary keys are kept, and NULL is written as `\N` so it survives the round trip. User accounts, sessions and API keys are deliberately excluded.
- **Restore** happens in this order:
  1. It validates the ZIP: known file names, bounded uncompressed size, and every column must exist.
  2. It copies the current databases to `backups/pre-restore-<timestamp>/`.
  3. It *replaces* the contents of every table in the backup, in one transaction across all files.

  Tables missing from an older backup are left untouched. Only admins can restore.
- **CSV exports** (plants, hierarchy, definitions, visibility, annual and periodic targets, lean) are human-readable joins for people and BI tools. They can't be restored.
