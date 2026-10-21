# Plan: KPI Management Refactor & Schema Fix

## Objective
1. Fix the `NOT NULL constraint failed: kpi_indicators.subgroup_id` error.
2. Complete the KPI Management layout by adding a "Global Splits" tab.
3. Modernize the KPI Explorer and align it with the new sidebar design and hierarchy model.

## Phase 1: Database & Core Logic Alignment
- **`src/data_access/setup.py`**: Update migration logic to handle the `subgroup_id` NOT NULL constraint by recreating the `kpi_indicators` table if necessary.
- **`src/kpi_management/indicators.py`**: Update `add_kpi_indicator` and other functions to primarily use `node_id`.
- **Standardize `CREATE TABLE`**: Update all occurrences of `CREATE TABLE IF NOT EXISTS kpi_indicators` to use the new schema (nullable `subgroup_id`).

## Phase 2: KPI Management UI Improvement
- **`src/interfaces/tkinter_app/components/kpi_management_tab.py`**:
    - Add a "✂️ Global Splits" tab for managing standardized annual distributions.
    - Refactor "📁 KPI Explorer" detail pane for better information density and visual appeal.
    - Add buttons for creating 'group' and 'subgroup' node types.
    - Add "🛠️ Visual Formula" button that launches the `NodeEditorDialog`.
- **`src/interfaces/tkinter_app/dialogs/split_editor.py`**: (New File) Create a dialog for editing Global KPI Splits.

## Phase 3: Verification
- Verify that creating new KPIs no longer triggers `IntegrityError`.
- Verify that Global Splits can be created, edited, and deleted.
- Verify the Visual Formula editor integrates correctly with the Explorer detail pane.
