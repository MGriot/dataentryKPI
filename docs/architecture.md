# Architecture Overview

## Components

- **src/app_config.py:**  
  Centralized configuration loader (paths, constants, profiles).

- **src/database_manager.py:**  
  Core logic for database setup, CRUD operations, and target distribution.

- **src/data_retriever.py:**  
  Read-only data access for UI and exports.

- **src/export_manager.py:**  
  Global CSV/ZIP export logic.

- **src/app_tkinter.py / src/app_streamlit.py:**  
  User interfaces (desktop/web), sharing backend logic.

## Data Flow

1. **User defines KPI structure** (groups, subgroups, indicators, templates).
2. **Annual targets are entered** for each KPI/stabilimento.
3. **Automatic distribution**: Targets are split into quarters, months, weeks, days using mathematical profiles.
4. **Results are visualized** and can be exported.

## Extensibility

- Add new distribution profiles in `database_manager.py`.
- Extend UI tabs or export logic as needed.

## See Also

- [Automatic Target Generation Logic](target_generation.md)
