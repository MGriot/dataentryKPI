# Stage: Architectural Evolution - Visual KPI & Standardized Splits

## Goal
Evolve the KPI management system to support dynamic node-based calculations, hierarchical data entry, and standardized annual distribution templates while maintaining backward compatibility.

## Current Status
- Research phase complete.
- Core dependencies identified in `src/target_management/` and `src/interfaces/tkinter_app/`.
- Tasks decomposed into atomic steps in `tasks.json`.

## Architecture Strategy
### 1. Visual Node Engine
- **Serialization**: JSON-based DAG (Directed Acyclic Graph) stored in a new `kpi_formula_nodes` table.
- **UI**: Custom Tkinter canvas implementation using `tk.Canvas` to draw nodes and edges.
- **Execution**: Recursive evaluation of the DAG within `annual.py`, replacing the current `eval`-based placeholder.

### 2. Standardized Splits
- **Storage**: `global_kpi_splits` table in `db_kpi_templates.db`.
- **Logic**: `repartition.py` will be refactored to check for a `global_split_id` in `annual_targets`. If present, it loads the template; otherwise, it falls back to current plant-specific logic (additive).

### 3. Smart Data Entry
- **Hierarchical View**: `TargetEntryTab` will use `ttk.Treeview` or nested `ttk.LabelFrame`s organized by `kpi_groups` and `kpi_subgroups`.
- **Reactivity**: Calculated fields will be updated via a shared state or event bus when dependencies change.

## Verification Strategy
- **Unit Testing**: Validate repartition math and formula evaluation.
- **Integrity**: Scripts to check for circular dependencies.
- **Manual QA**: Visual confirmation of UI changes and color-coding.

## Timeline
- **Phase 1**: DB Evolution & Refactoring (Tasks 1-5)
- **Phase 2**: Node Engine (Tasks 6-8)
- **Phase 3**: Smart Data Entry (Tasks 9-11)
- **Phase 4**: Validation (Task 12)
