# Project TODO List

This document outlines potential improvements, refactoring tasks, and future features for the Data Entry KPI Target Manager project.

## Codebase Refactoring & Organization (Ongoing)

*   **Standardize `src` directory structure:**
    *   [x] Initial migration to `src/` directory completed.
    *   [x] Core logic separated into `kpi_management`, `target_management`, `plants_management`.
    *   [x] GUI code separated into `gui/app_tkinter` and `gui/app_streamlit`.
    *   [x] Adopted layered structure: `config`, `data_access`, `interfaces`.
    *   [x] Consolidate `db_core` into `data_access`.
    *   [ ] Migrate feature modules (`kpi_management`, etc.) into `core` (models) and `services` (logic) fully.
*   **Legacy Script Cleanup:**
    *   [x] Move root-level utility scripts (`get_distinct_calc_types.py`, etc.) to `scripts/`.
    *   [x] Update scripts in `scripts/` to use `src.app_config` for portability.
    *   [ ] Review `temp_db_query.py` and `update_kpis_db.py` for long-term utility; convert to proper CLI tools or tests if needed.
*   **Improve GUI module organization:**
    *   [x] Moved GUIs to `src/interfaces`.
    *   [x] Extracted common UI logic into `src/interfaces/common_ui`.
    *   [ ] Further refactor components to reduce redundancy between Tkinter and Streamlit.
*   **Centralize configuration management:**
    *   [x] Moved `app_config.py` to `src/config/settings.py`.
    *   [x] Updated all references to use `src.config.settings`.

## Features & Enhancements

*   **Error Handling and Logging:** Implement robust error handling and a standardized logging system across the application.
*   **Tests:** Implement a comprehensive test suite (Unit and Integration) for core logic, especially for `target_management/repartition.py` and formula calculations. Also add pytest coverage for `src/api.py` itself (currently only tested manually/via the React app) and the auth flow.
*   **Database Migrations:** Introduce a migration tool (e.g., Alembic, or a custom light version) for easier database schema updates.
*   **Performance Optimization:** Profile and optimize critical sections, especially target distribution algorithms and database queries. `save_annual_targets` currently rescans every calculated KPI system-wide on every single save, not just affected ones.
*   **Advanced Distribution Models:** Research and implement additional mathematical models for target distribution.
*   [x] **User Authentication/Authorization:** Implemented for the React app + REST API (password login, sessions, audit trail) — see CHANGELOG 2.0.0. Still open:
    *   Role-based access control (currently any logged-in user can create other accounts, no admin/read-only distinction).
    *   Wire Swagger UI's "Authorize" button to the session-bearer scheme so `/docs` can call protected endpoints without manually setting headers.
    *   No "forgot password" / admin password reset flow.
*   **Global Split UX:** When a KPI has a Global Split linked, its own Repartition Logic/Distribution Profile fields are silently ignored (the split wins) but the Target Entry UI doesn't disable or explain this — should gray them out with an explanatory note.
*   **`target_granularity`:** Stored and editable per KPI but not read by any calculation logic yet (repartition uses the separate per-save Repartition Logic instead). Either wire it in as a real constraint/default, or drop it from the UI to stop implying it does something.
*   **Streamlit:** Improve responsive design; document a cloud deployment strategy. (Login/auth was implemented for the React app and REST API only — Streamlit and Tkinter remain unauthenticated, direct-to-database.)

## Documentation Improvements

*   **API Reference Generation:** Consider using Sphinx to auto-generate API documentation from docstrings (a hand-written reference exists at `docs/api_reference.md`).
*   **Contribution Guidelines:** Expand on the existing contribution guidelines in `README.md`.

---

**Note:** This TODO list should be regularly reviewed and updated as the project evolves.
