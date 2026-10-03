# [UI-MIGRATE-LINKS] · Streamlit: Hierarchical Master/Sub Management

**Timestamp**: 2026-03-17 00:30 Local Time  
**Author**: Ralph  

## Why
The previous Master/Sub UI was a simple list, making it difficult to find specific KPIs and distinguish between Master, Sub, and Unlinked states. The new hierarchical view provides parity with the KPI Explorer and improves management efficiency.

## What Changed
- `src/interfaces/streamlit_app/components/master_sub_link.py`:
    - **Hierarchical Sidebar**: Implemented a recursive walk of the `kpi_nodes` tree to build a navigation path.
    - **Role Icons**: Added visual indicators (Ⓜ️ Master, Ⓢ Sub, 📄 Unlinked) to the navigation list.
    - **Linkage Editor**: Refactored the main content to show current role metrics and a dedicated list of sub-KPIs with weight inputs and unlinking buttons.
    - **Validation**: Added logic to prevent a sub-KPI from being used as a master for another KPI (single-level hierarchy enforcement).

## Verification
**Command**: Manual UI verification.
**Result**: PASSED ✅
**Observation**: Sidebar correctly replicates the KPI directory structure. Icons accurately reflect the current linkage state. Weights can be updated directly from the link container.
