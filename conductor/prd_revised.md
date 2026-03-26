# Product Requirements Document: dataentryKPI Evolution (Revised)

## 1. Executive Summary
*   **Elevator Pitch**: A high-performance KPI management and target repartition system for manufacturing, featuring automated seasonal target distribution.
*   **Target Audience**: Plant managers, production controllers, and data analysts.
*   **Success Metrics (KPIs)**: 
    *   100% parity between Tkinter and Streamlit UI features.
    *   Target entry time reduced by showing historical context.

## 2. Technical Strategy
*   **Recommended Stack**: 
    *   **Frontend**: Streamlit (Modern Web), Tkinter (Legacy Desktop).
    *   **Backend**: Python 3.13, SQLite (Multi-DB).
*   **Architecture Diagram**: 
    *   UI (Streamlit/Tkinter) -> KPI Manager (Recursive Hierarchy) -> Target Repartition (Seasonal Splits) -> SQLite DBs.
*   **Buy vs. Build**: Custom build for the repartition logic to handle specific manufacturing seasonality patterns.

## 3. Core Features & Functional Requirements

### 3.1 Target Entry & Context
*   **Historical Context**: In the target entry page, show the previous two years' target values (if available) next to current target inputs.
*   **Dynamic Targets**: Allow users to add an arbitrary number of targets (Target 1, 2, 3...) per KPI at their discretion.
*   **UX Consistency**: After creating any hierarchy element (Folder, Group, Subgroup, Indicator), the tree explorer must refresh and reset to the initial root state on the left.

### 3.2 KPI & Template Management
*   **Template Table Fix**: Fix the issue where added indicators are not visible in the template page table.
*   **Global Splits & Distribution**: 
    *   Distribution splits must be global but allow different profiles based on KPI.
    *   Allow users to specify which indicators are affected by a split.

### 3.3 Results Analysis
*   **Selector Improvement**: Better toggle/selector for Single KPI vs. Global Dashboard.
*   **Single KPI Focus**: Avoid "All Plants" selection; allow selecting multiple years.
*   **Optimization**: Avoid tree view refresh on every change unless necessary.
*   **Visualization**: Improve day-scale visualization on charts.

### 3.4 Advanced Split Logic (Multivariate)
*   **Functionality**: Allow users to upload a CSV or XLSX file.
*   **Analysis**: Analyze the data (multivariate) to understand trends and suggest seasonal splitting.
*   **Mapping**: Provide a manual mapping UI for users to link columns to indicators.
*   **Logic**: More complex and specific splitting logic per indicator or KPI based on the provided historical data.

### 3.5 System Maintenance & GUI Parity
*   **Verification**: Check if Backup, Load, and Export functions still work.
*   **Streamlit Migration**: Drastically update the Streamlit GUI to match the Tkinter GUI page-by-page, panel-by-panel, and feature-by-feature. Each step must be mapped as a Ralph task.

## 4. UX/UI Guidelines
*   **Navigation**: Sidebar-based tree navigation for all modules.
*   **Feedback**: Toasts for save confirmation; visual indicators for "Dirty" states (unsaved changes).

## 5. Risks & Mitigation
*   **UX Risk**: Complexity of multivariate splitting. *Mitigation*: Start with simple mapping and provide "Reset to Default" options.
*   **Maintenance Risk**: Maintaining two GUIs. *Mitigation*: Prioritize Streamlit as the primary interface.
