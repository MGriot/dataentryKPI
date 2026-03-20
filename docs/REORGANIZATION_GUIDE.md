# Repository Reorganization Guide

This guide provides recommendations for reorganizing the `dataentryKPI` repository to improve modularity, maintainability, and scalability. The suggestions aim to align the project structure with common Python best practices and principles of clean architecture, promoting better separation of concerns.

## Current Challenges Identified

Based on the existing structure and general development patterns, the following areas could benefit from reorganization:

1.  **Mixed Concerns within `src/`:** The `src` directory, while containing core logic, might have a flat structure or modules that mix different responsibilities (e.g., database interactions directly within business logic modules).
2.  **UI-Specific Logic Duplication/Tight Coupling:** While there's a `gui/shared` directory, it's possible that some UI logic is replicated or tightly coupled to either Tkinter or Streamlit, hindering reusability.
3.  **Configuration Dispersion:** Multiple configuration files (`app_config.py`, `config.ini`, `settings.json`) could lead to confusion and inconsistency.
4.  **Lack of Clear Service/Business Logic Layer:** It's often beneficial to have a distinct layer for application-specific business rules, separate from data access and presentation layers.
5.  **Database Core Integration:** The `src/db_core` directory could potentially be integrated into a more comprehensive data access layer.

## Proposed Reorganization Principles

The following principles should guide the reorganization effort:

*   **Separation of Concerns:** Each module or directory should have a single, well-defined responsibility.
*   **Modularity:** Components should be loosely coupled and highly cohesive, allowing independent development and testing.
*   **Layered Architecture:** Structure the application into distinct layers (e.g., Presentation, Application/Service, Domain/Business Logic, Data Access).
*   **Consistency:** Maintain consistent naming conventions and architectural patterns across the project.

## Recommended Structure

Here's a proposed improved directory structure for the `src` folder, and general repository layout:

```
dataentryKPI/
├── src/
│   ├── core/                  # Core business logic, domain models, KPI rules (framework-independent)
│   │   ├── kpi_models.py      # Data models for KPIs, hierarchies, templates
│   │   ├── target_distribution.py # Algorithms for target distribution
│   │   ├── calculation_engine.py  # Logic for formula-based calculations
│   │   └── ...
│   ├── interfaces/            # UI-specific code (presentation layer)
│   │   ├── streamlit_app/     # All Streamlit related code
│   │   │   ├── __init__.py
│   │   │   └── main.py        # Streamlit app entry point
│   │   │   ├── components/    # Reusable Streamlit components
│   │   │   └── pages/         # Page-specific Streamlit layouts
│   │   ├── tkinter_app/       # All Tkinter related code
│   │   │   ├── __init__.py
│   │   │   └── main.py        # Tkinter app entry point
│   │   │   └── components/    # Reusable Tkinter widgets/frames
│   │   │   └── dialogs/       # Tkinter dialog definitions
│   │   └── common_ui/         # UI utilities or abstract components shared across GUIs
│   ├── services/              # Application services, orchestrating core logic and data access
│   │   ├── kpi_service.py     # Manages KPI lifecycle (create, update, retrieve)
│   │   ├── target_service.py  # Manages target generation and application
│   │   ├── export_service.py  # Handles data export (delegates to data_access)
│   │   ├── import_service.py  # Handles data import (delegates to data_access)
│   │   └── ...
│   ├── data_access/           # Database interactions (repository pattern)
│   │   ├── __init__.py
│   │   ├── database.py        # Database connection and session management
│   │   ├── kpi_repository.py  # CRUD operations for KPI-related entities
│   │   ├── target_repository.py # CRUD operations for target data
│   │   ├── utils.py           # Database-specific utilities (e.g., setup, schema management)
│   │   └── ...
│   ├── config/                # Centralized configuration management
│   │   ├── __init__.py
│   │   └── settings.py        # Loads and provides application settings
│   ├── utils/                 # General utility functions (not specific to any layer)
│   │   ├── decorators.py
│   │   ├── exceptions.py
│   │   └── ...
│   └── main.py                # Main application entry point (orchestrates interfaces)
├── tests/                     # Unit and integration tests
│   ├── unit/
│   ├── integration/
│   └── ...
├── docs/                      # Project documentation
├── scripts/                   # Utility scripts (e.g., database initialization, data migration)
├── .venv/                     # Python virtual environment
├── requirements.txt           # Project dependencies
├── pyproject.toml             # Project metadata and build configuration (if using Poetry/Flit)
├── config.ini                 # Application configuration (if not fully migrated to src/config)
├── README.md                  # Project README
├── TODO.md                    # Project TODO list
└── REORGANIZATION_GUIDE.md    # This guide
```

## Step-by-Step Reorganization Plan

1.  **Define Core Domain Models:** Identify the fundamental entities (KPI, Target, Plant, Template, etc.) and define their structures and relationships in `src/core/kpi_models.py`.
2.  **Extract Core Logic:** Move the business rules, algorithms (like target distribution), and non-UI specific calculations into `src/core/`. This layer should be entirely independent of any UI framework or database implementation.
3.  **Implement Data Access Layer:** Create `src/data_access/` to encapsulate all database interactions. Use a Repository pattern where each repository (`kpi_repository.py`, `target_repository.py`) handles CRUD operations for a specific domain entity, interacting with `src/data_access/database.py`. The existing `db_core` can be integrated here.
4.  **Develop Application Services:** Create `src/services/` to act as an intermediary between the UI and the core/data access layers. Services orchestrate operations, apply business rules (from `core`), and use repositories (from `data_access`). This is where `export_manager.py` and `import_manager.py` would become `export_service.py` and `import_service.py`, using the new data access layer.
5.  **Refactor UI Interfaces:**
    *   Migrate `gui/app_streamlit` to `src/interfaces/streamlit_app` and `gui/app_tkinter` to `src/interfaces/tkinter_app`.
    *   Ensure UI components (`components`, `pages`, `dialogs`) within these directories strictly handle presentation logic and interact with the `src/services` layer for all business operations.
    *   Identify and extract truly shared UI utilities or abstract concepts into `src/interfaces/common_ui`.
6.  **Centralize Configuration:** Consolidate all configuration logic into `src/config/settings.py`. This module should be responsible for loading settings from `config.ini`, environment variables, or other sources, providing a unified access point for configuration throughout the application.
7.  **Update Main Entry Point (`main.py`):** The `main.py` at the project root should primarily be responsible for parsing command-line arguments (e.g., `tkinter` or `streamlit`) and launching the appropriate UI entry point from `src/interfaces/`.
8.  **Implement Testing:** Create a `tests/` directory mirroring the `src/` structure, with `unit/` tests for `core` and `services` layers, and `integration/` tests for data access and UI components.
9.  **Continuous Refinement:** This is an iterative process. Start with small, manageable refactoring tasks and incrementally move towards the desired structure.

## Benefits of this Structure

*   **Clearer Responsibilities:** Easy to understand where different types of code reside.
*   **Improved Testability:** Core business logic and services can be tested independently of the UI and database.
*   **Enhanced Maintainability:** Changes in one layer (e.g., switching database) have minimal impact on other layers.
*   **Easier Onboarding:** New developers can quickly grasp the project's architecture.
*   **Scalability:** Facilitates adding new features or even new UI interfaces more easily in the future.

---

**Note:** This guide provides a conceptual framework. The actual implementation will require careful consideration of existing code and dependencies.
