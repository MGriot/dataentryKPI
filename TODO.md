# Project TODO List

This document outlines potential improvements, refactoring tasks, and future features for the Data Entry KPI Target Manager project. This list is generated based on a structural overview and the user's feedback regarding the repository's organization.

## Codebase Refactoring & Organization

*   **Standardize `src` directory structure:**
    *   Review and potentially consolidate modules within `src` for better separation of concerns (e.g., `db_core` might be integrated into a more general `data_access` or `database` module).
    *   Ensure consistent naming conventions for modules and files.
    *   Consider creating a `services` or `logic` layer to house core business logic, separating it from UI-specific implementations.
*   **Improve GUI module organization:**
    *   Refactor `gui/app_tkinter/components` and `gui/app_streamlit/components` to reduce redundancy or extract common UI logic into `gui/shared` where applicable.
    *   Evaluate if there's a more abstract way to define UI elements or interactions that both GUIs can leverage.
*   **Centralize configuration management:**
    *   Ensure `app_config.py`, `config.ini`, and `settings.json` are used consistently and avoid redundancy.
    *   Consider a single, robust configuration loading mechanism.
*   **Add Unit and Integration Tests:** Implement a comprehensive test suite for core logic, KPI calculations, and database interactions.
*   **Dependency Management Review:** Ensure `requirements.txt` is up-to-date and reflects all necessary dependencies.

## Features & Enhancements

*   **Error Handling and Logging:** Implement robust error handling and a standardized logging system across the application.
*   **User Authentication/Authorization (for Streamlit):** If the web application is intended for multi-user access, implement appropriate security measures.
*   **Database Migrations:** Introduce a migration tool for easier database schema updates.
*   **Performance Optimization:** Profile and optimize critical sections, especially target distribution algorithms and database queries.
*   **More Advanced Distribution Models:** Research and implement additional mathematical models for target distribution.
*   **Improved UI/UX:**
    *   Gather user feedback to enhance the usability and aesthetics of both Tkinter and Streamlit interfaces.
    *   Consider responsive design improvements for the Streamlit application.
*   **Reporting & Visualization:** Enhance data visualization capabilities beyond current analysis features.
*   **Cloud Deployment Strategy:** Document or implement a clear strategy for deploying the Streamlit application to cloud platforms.

## Documentation Improvements

*   **API Reference Generation:** Consider using Sphinx or similar tools to auto-generate API documentation from docstrings.
*   **Contribution Guidelines:** Expand on the existing contribution guidelines in `README.md` to include coding standards, test requirements, and PR submission process.
*   **Deep-dive into specific features:** Add more detailed documentation for complex features like formula-based calculations or custom KPI rules.

---

**Note:** This TODO list is a starting point and should be regularly reviewed and updated as the project evolves.
