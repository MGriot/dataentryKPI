# Implementation Plan: dataentryKPI Enhancement

This plan outlines the steps required to fulfill the user's requirements for the `dataentryKPI` project, addressing missing features, bugs, and parity gaps between Tkinter and Streamlit interfaces.

## Phase 1: Core Analysis & UI Fixes (Immediate Priority)

Focus on improving data entry context and analysis usability in the existing Tkinter application.

### Task 1.1: Target Entry History (Req 1)
- **Problem:** Historical target data (previous 2 years) is fetched but not displayed near current targets.
- **Action:** Update `src/interfaces/tkinter_app/components/target_entry_tab.py` to add label widgets showing `hist_y1_t1`, `hist_y1_t2`, etc., next to the input fields.

### Task 1.2: Master/Sub Link Indication (Req 10)
- **Problem:** The KPI tree view does not distinguish between standalone KPIs and those linked as Master/Sub.
- **Action:**
    - Update `src/data_retriever.py` or `kpi_management_tab.py` to check link status during tree population.
    - Use distinct icons (e.g., `🔗`) or text styles for linked KPIs in `_load_level`.

### Task 1.3: Results Analysis Improvements (Req 11)
- **Problem:**
    - "All Plants" selection in Single KPI mode causes issues/warnings.
    - Tree refreshes unnecessarily on filter change.
    - Day scale visualization is cluttered.
    - Only single year selection supported.
- **Action:**
    - **Single KPI Mode:** Automatically exclude "All Plants" from the combobox or default to the first plant.
    - **Tree Refresh:** Cache the tree structure and only refresh if the underlying *data hierarchy* changes, not when filters change (unless filters affect visibility).
    - **Multiple Years:** Replace `Combobox` with a `Listbox` (multiselect) or checkbuttons for years. Update data fetching to handle list of years.
    - **Day Scale:** Implement `matplotlib.dates` locators/formatters for smarter axis labeling.

## Phase 2: Advanced Features & Logic (High Effort)

Focus on complex new capabilities requiring database schema changes or significant new logic.

### Task 2.1: Advanced Split Logic (Req 9, 12)
- **Problem:**
    - Global splits are 1:1 with profiles. Need per-KPI profiles.
    - No multivariate/seasonality analysis.
- **Action:**
    - **Schema Change:** Create `kpi_split_profiles` table linking `kpi_id` to a `distribution_profile_id`.
    - **Algorithm:** Implement `src/services/seasonality_analysis.py` using `pandas`/`scipy` to analyze historical data (CSV/XLSX input) and suggest split weights.
    - **UI:** Add "Advanced Split" dialog in `kpi_management_tab.py`.

### Task 2.2: Dynamic Node Editor (Req 4, 5, 6, 7)
- **Problem:** Node editor lacks preview, mode switching, and dynamic inputs.
- **Action:**
    - **Preview:** Add a "Preview Result" pane in `NodeEditorDialog` that evaluates the DAG against dummy or historical data.
    - **Switching:** Implement bidirectional conversion between `Node DAG` <-> `Text Formula`.
    - **Inputs:** Allow adding dynamic input ports to Operator nodes.

### Task 2.3: Arbitrary Targets (Req 2)
- **Problem:** System is hardcoded to 2 targets.
- **Action:**
    - **Schema Change:** Refactor `annual_targets` table to be vertical (one row per target index) or add dynamic columns. *Major migration required.*
    - **UI:** Update all grids to generate columns dynamically based on configuration.

## Phase 3: Streamlit Parity (Req 14)

Systematic migration of Tkinter features to Streamlit.

### Task 3.1: Target Entry Page
- **Action:** Rebuild `src/interfaces/streamlit_app/pages/target_entry.py` to match `target_entry_tab.py` (grids, history, saving logic).

### Task 3.2: Analysis Page
- **Action:** Port `analysis_tab.py` features (Single/Global views, charts) to `components/analysis.py`.

### Task 3.3: Data Management
- **Action:** Add Backup/Restore UI to `pages/data_management.py`.

## Phase 4: Bug Fixes & Refinement

### Task 4.1: Template Indicator Bug (Req 8)
- **Action:** Debug `kpi_templates.py` to ensure `add_indicator` updates the template definition immediately.

### Task 4.2: Explorer Tree Refresh (Req 3)
- **Action:** Ensure `refresh_tree` consistently resets/expands nodes as requested after every creation event.

