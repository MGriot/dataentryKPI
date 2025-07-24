# Architecture Overview

## Components


- **src/app_config.py:**  
  Centralized configuration loader (paths, constants, profiles, config.ini integration).

- **src/gui/app_tkinter/main.py / src/gui/app_streamlit/main.py:**  
  User interfaces (desktop/web), sharing backend logic. These are the main entry points for each GUI.

- **src/main.py:**  
  The top-level entry point for launching either the Tkinter or Streamlit interface.

- **src/data_retriever.py:**  
  Provides read-only data access for UI components, export functions, and reporting.

- **src/export_manager.py:**  
  Handles global CSV/ZIP export logic, integrating with `data_retriever`.

- **src/import_manager.py:**  
  Manages the import of data from CSV files into the database, including triggering recalculations.

- **src/db_core/**:  
  Contains database setup and utility functions, including `setup.py` (schema creation) and `utils.py` (distribution helpers).

- **src/kpi_management/**:  
  Modular management of KPI hierarchy:
    - `groups.py`, `subgroups.py`, `indicators.py`, `specs.py`, `templates.py`, `links.py`

- **src/stabilimenti_management/**:  
  Facility (stabilimento) CRUD logic.

- **src/target_management/**:  
  Target entry, annual/periodic repartition, and distribution logic.

- **src/__init__.py** and submodule `__init__.py`:  
  Mark packages for import structure.

## Data Flow

1. **User defines KPI structure** (groups, subgroups, indicators, templates) via the UI (Tkinter/Streamlit).
2. **Facilities (stabilimenti) are managed** (add/edit/delete, visibility).
3. **Annual targets are entered** for each KPI/facility.
4. **Automatic distribution**: Targets are split into quarters, months, weeks, days using mathematical profiles (see `target_management/`).
5. **Results are visualized/exported** (CSV/ZIP) for reporting or integration.

## Extensibility

- Add new distribution profiles in `target_management/repartition.py` or `db_core/utils.py`.
- Extend UI tabs, KPI/facility logic, or export logic as needed.

## See Also

- [Automatic Target Generation Logic](target_generation.md)
