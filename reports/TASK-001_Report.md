# TASK-001: Architectural Analysis & Dependency Check Report

## 1. Dependency Analysis
- **Database**: `annual_targets` is the central hub for KPI target data. Existing reporting queries in `src/data_retriever.py` fetch from this table and periodic aggregation tables (`daily_targets`, `weekly_targets`, etc.).
- **Calculations**: `src/target_management/annual.py` currently handles formula evaluation and master/sub distribution. It triggers `repartition.py` which populates the periodic tables.
- **UI**: `TargetEntryTab` is the primary interface for data entry. It currently operates synchronously.

## 2. Impact of "Calculated" Fields
- New node-based calculation fields will store their logic in a new DAG-compatible table.
- These fields will populate `annual_target1` and `annual_target2` in the existing `annual_targets` table.
- Since reporting queries pull from these standard columns, **zero impact** is expected on existing reports, provided the repartitioning logic is triggered correctly.

## 3. Tkinter Responsiveness Strategy
- **Threading**: Long-running operations (like saving and repartitioning 100+ KPIs) will be moved to a background thread using `threading.Thread`.
- **UI Feedback**: A "Processing..." overlay or progress bar will be implemented to prevent user interaction during heavy calculations.
- **Incremental Updates**: If calculations are very heavy, we will implement a queue-based update system for the UI.

## 4. Stability & Compatibility
- All database updates will be **additive** (new tables or optional columns).
- The existing `eval`-based formula logic will be maintained as a fallback during the transition period.
- **Global Splits** will be implemented as an optional reference in `annual_targets`, defaulting to existing logic if null.

## 5. Conclusion
The proposed architectural evolution is safe and compatible with the current codebase. No major conflicts with existing reporting queries were identified.
