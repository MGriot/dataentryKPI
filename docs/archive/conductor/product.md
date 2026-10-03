# Product Requirements Document: dataentryKPI Evolution

## 1. Executive Summary
*   **Elevator Pitch**: A high-performance KPI management and target repartition system for manufacturing, featuring a visual node-based formula engine and automated seasonal target distribution.
*   **Target Audience**: Plant managers, production controllers, and data analysts.
*   **Success Metrics (KPIs)**: 
    *   100% parity between Tkinter and Streamlit UI features.
    *   Target entry time reduced by showing historical context.
    *   0% formula errors through visual node validation.

## 2. Technical Strategy
*   **Recommended Stack**: 
    *   **Frontend**: Streamlit (Modern Web), Tkinter (Legacy Desktop).
    *   **Backend**: Python 3.13, SQLite (Multi-DB).
    *   **Logic**: Custom Directed Acyclic Graph (DAG) for KPI formulas.
*   **Architecture Diagram**: 
    *   UI (Streamlit/Tkinter) -> KPI Manager (Recursive Hierarchy) -> Node Engine (Formula Evaluation) -> Target Repartition (Seasonal Splits) -> SQLite DBs.
*   **Buy vs. Build**: Custom build for the repartition logic and node engine to handle specific manufacturing seasonality patterns.

## 3. Core Features & Functional Requirements

### 3.1 Advanced Target Entry & Context
*   **Historical Context**: Display the previous two years' target values (if available) next to current target inputs.
*   **Dynamic Targets**: Allow users to add an arbitrary number of targets (Target 1, 2, 3...) per KPI.
*   **UX Consistency**: After creating any hierarchy element (Folder, Group, Subgroup, Indicator), the tree explorer must refresh and reset to the root state.

### 3.2 Visual Node Engine (v2)
*   **Hierarchical Selection**: Indicator selection within the node editor must follow the same tree structure as the rest of the app.
*   **Dynamic Operators**: 
    *   Support fundamental operations (+, -, *, /).
    *   Dynamic input ports for multi-input operators (Sum, Product).
    *   Support multiple connections to a single input point.
*   **Visual Polish**: 90-degree "ortho" connection lines (no diagonals).
*   **Bi-directional Conversion**: Freely switch between "Formula Mode" (text) and "Node Mode" (visual) with automatic state synchronization.
*   **Real-time Preview**: Show formula/node evaluation results in the right-hand preview panel during editing.

### 3.3 KPI & Template Management
*   **Template Table Fix**: Ensure indicators added to a template are immediately visible in the management table.
*   **Master/Sub Clarity**: Visually indicate in the tree view if a KPI is a Master or linked Sub-KPI.
*   **Global Splits with Profiles**: 
    *   Centralized split templates.
    *   Per-KPI distribution profiles.
    *   Selection of specific indicators affected by a global split.

### 3.4 Advanced Multivariate Seasonality (AI-Ready Splits)
*   **Multivariate Input**: Support CSV/XLSX uploads containing external factors (e.g., historical production, weather, energy costs).
*   **Mapping UI**: Manual column-to-indicator mapping for uploaded data.
*   **Trend Suggestion**: Analyze uploaded data to suggest a seasonal distribution pattern based on historical trends.

### 3.5 Analytics & Results
*   **Selector Overhaul**: Improve toggle between Single KPI and Global Dashboard.
*   **Multi-Year Analysis**: Allow selection of multiple years for a single KPI (while disabling "All Plants" to maintain focus).
*   **Optimization**: Prevent unnecessary tree refreshes; improve day-scale axis visualization.

### 3.6 Streamlit Parity & Maintenance
*   **Full Parity**: Systematically migrate every panel, tab, and feature from Tkinter to Streamlit.
*   **Verification**: Ensure Backup, Load, and Export functions are robust and verified.

## 4. Data Model Draft
*   **Entities**: 
    *   `KpiNode`: Recursive hierarchy (Folder -> Indicator).
    *   `FormulaDAG`: JSON blob of node connections.
    *   `Target`: Annual/Monthly/Weekly/Daily values.
    *   `SplitProfile`: Distribution logic (Sine, Linear, Custom).
*   **Relationships**: 
    *   `KpiNode` 1:1 `FormulaDAG`.
    *   `KpiNode` 1:N `Target`.

## 5. UX/UI Guidelines
*   **Consistency**: Use the same color coding for Master/Sub KPIs across all views.
*   **Navigation**: Sidebar-based tree navigation for all modules.
*   **Feedback**: Toasts for save confirmation; visual indicators for "Dirty" states (unsaved changes).

## 6. Risks & Mitigation
*   **Technical Risk**: Circular dependencies in Node Mode. *Mitigation*: Implement cycle detection during DAG creation.
*   **UX Risk**: Complexity of multivariate splitting. *Mitigation*: Start with simple mapping and provide "Reset to Default" options.
*   **Maintenance Risk**: Maintaining two GUIs. *Mitigation*: Prioritize Streamlit as the primary interface, moving Tkinter to "maintenance mode".
