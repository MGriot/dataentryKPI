# [UI-MIGRATE-SPLITS] · Streamlit: Global Splits Management

**Timestamp**: 2026-03-17 00:15 Local Time  
**Author**: Ralph  

## Why
The Global Splits management feature was present in Tkinter but missing in Streamlit. It is essential for defining shared repartition templates that ensure consistent target distribution across multiple KPIs.

## What Changed
- `src/interfaces/streamlit_app/components/global_splits.py`: (New) Implemented full CRUD UI for Global KPI Splits.
    - Sidebar navigation for template selection.
    - Form-based creation and editing.
    - Automated presets for Monthly, Quarterly, and Weekly logic.
    - Profile parameter presets for Progressive and Sinusoidal curves.
    - JSON validation for custom repartition values.
- `src/interfaces/streamlit_app/main.py`: Registered the new component in the navigation menu.

## Verification
**Command**: Manual UI verification.
**Result**: PASSED ✅
**Observation**: Templates can be created, edited, and deleted. Presets correctly populate JSON areas when left as default.
