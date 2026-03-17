# [UI-MIGRATE-PREVIEW] · Streamlit: KPI Detail Real-time Preview

**Timestamp**: 2026-03-17 01:00 Local Time  
**Author**: Ralph  

## Why
Users need immediate feedback when defining complex KPI formulas to ensure correctness without leaving the management page. Providing a visual representation of Node DAGs or syntax-highlighted code blocks improves the developer experience and reduces errors.

## What Changed
- `src/interfaces/streamlit_app/components/kpi_explorer.py`:
    - **Dynamic Layout**: Refactored the KPI detail view to use a 3-column layout (Navigation | Editor | Preview).
    - **Live Preview**: Added a `col3` implementation that fetches the latest KPI specification and renders the formula.
    - **Multi-format Support**: Implemented logic to detect and visualize both textual formula strings (using `st.code`) and visual Node DAGs (using `st.json`).
    - **Contextual Feedback**: Added info messages for manual KPIs and validation status for calculated ones.

## Verification
**Command**: Manual UI verification in KPI Explorer.
**Result**: PASSED ✅
**Observation**: Selecting an indicator opens the preview panel. Formula changes (after save) are reflected. Node-based KPIs display their underlying JSON structure clearly.
