# Changelog

All notable changes to this project will be documented in this file.

## [1.3.0] - 2026-03-31

### Added
- **Visual Node Editor (Streamlit)**: High-performance Canvas-based graph editor for KPI formulas. Supports draggable nodes, dynamic sockets, and bidirectional sync with raw expressions.
- **Individual Table Export**: Granular export functionality for specific database tables (Plants, Hierarchy, Definitions, Targets) in both GUIs.
- **Handshake Protocol**: Implemented strict Streamlit component handshake to resolve iframe loading timeouts.

### Changed
- **Workspace Hygiene**: Cleaned up the project root by moving management files to `conductor/` and user configurations to `user_config/`.
- **Streamlit Data Center**: Promoted individual table exports to the top of the interface for better accessibility.

## [1.2.0] - 2026-03-20

### Added
- **"On-the-Fly" Calculation Engine**: Implemented daily formula evaluation for calculated KPIs, allowing them to dynamically inherit seasonality from dependencies.
- **Precision Reconciliation**: Added a layer to ensure that daily splits perfectly align with annual targets (Sum for Incremental, Mean for Average), automatically adjusting for rounding errors.
- **Topological Sort**: Implemented dependency-based calculation order for complex KPI chains.
- **Multivariate Seasonality Predictor (Streamlit)**: Ported the ML-driven predictor to the web interface with interactive Plotly fit charts and unified creation/edit workflows.
- **Sequential Timeline Analysis**: Implemented a continuous chronological X-axis for multi-year trends, enabling clear year-over-year comparisons.
- **Recursive Tree Navigation**: Redesigned Streamlit KPI Explorer with a nested expander system for better hierarchy visualization.
- **Quick-Find Sidebar**: Added a fast search and navigation sidebar to the Streamlit Target Entry page.
- **Sample Data**: Added `multivariate_test_data.csv` for verifying the predictive model.

### Changed
- **Optimized Data Export**: Refactored `export_manager` to reduce file count from 14 to 8, while enriching CSVs with human-readable metadata (names, paths).
- **Streamlit Navigation**: Restructured the web interface into logical categories (Operation, KPI Management, Configuration, Data & Analysis) to match the Tkinter desktop app.
- **Documentation Overhaul**: Recreated the `docs/` directory with structured technical references (Architecture, Database Schema, Feature Guides).
- **Project Structure**: Moved reports and guides to `docs/` for better workspace hygiene.

### Fixed
- **Plotly ID Conflicts**: Resolved duplicate element IDs in the Analysis dashboard.
- **KeyError 'period'**: Fixed data frame parsing issues in periodic trend views.
- **URL Path Conflicts**: Resolved Streamlit page title inference errors by implementing explicit `url_path` parameters.

## [1.1.0] - 2026-03-19
### Added
- Initial support for averaging multiple historical target columns in multivariate analysis.
- Basic circular dependency checking for formulas.

## [1.0.0] - 2026-03-15
### Added
- Initial release with dual Tkinter/Streamlit interfaces and SQLite backend.
