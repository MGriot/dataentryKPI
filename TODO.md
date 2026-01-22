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
*   **Tests:** Implement a comprehensive test suite (Unit and Integration) for core logic, especially for `target_management/repartition.py` and formula calculations.
*   **Database Migrations:** Introduce a migration tool (e.g., Alembic, or a custom light version) for easier database schema updates.
*   **Performance Optimization:** Profile and optimize critical sections, especially target distribution algorithms and database queries.
*   **Advanced Distribution Models:** Research and implement additional mathematical models for target distribution.
*   **Web Interface (Streamlit):**
    *   Implement User Authentication/Authorization if multi-user access is required.
    *   Improve responsive design.
    *   Document cloud deployment strategy.

## Documentation Improvements

*   **API Reference Generation:** Consider using Sphinx to auto-generate API documentation from docstrings.
*   **Contribution Guidelines:** Expand on the existing contribution guidelines in `README.md`.

---

**Note:** This TODO list should be regularly reviewed and updated as the project evolves.
