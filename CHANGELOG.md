# Changelog

All notable changes to this project will be documented in this file.

## [1.4.0] - 2026-04-01

### Added
- **Universal Global Splits**: Introduced a unified split definition that automatically applies to all aggregation levels (Daily, Weekly, Monthly, Quarterly).
- **Multi-Year Support**: Global Splits can now be assigned to multiple years simultaneously, with a dedicated mapping table in the database.
- **Enhanced KPI Explorer (Tkinter)**: 
    - Added "Move Node" and "Move KPI" functionality to easily reorganize the hierarchy.
    - Improved creation logic to allow placing new elements at the Root level or inside selected nodes.
- **Standardized Split Indicator**: Both GUIs now identify and highlight "Standard" Global Split assignments with a ⭐ icon in the Target Entry page.
- **Automated Weight Preview**: The Global Split editor now dynamically generates and previews weights for all levels (Monthly/Quarterly) when a profile is selected.

### Changed
- **Project Structure**: Consolidated redundant entry points and moved utility scripts to `src/scripts/` for better project organization.
- **UI Optimization**: Cleaned up labels in Target Entry; `(Incremental)` calc type is now hidden by default to reduce visual noise.
- **Dependency Update**: Refined `requirements.txt` with strict versioning and missing ML/Excel libraries.

### Fixed
- **Root Level Visibility**: Fixed an issue where indicators moved to the root level were hidden in the KPI Explorer tree.
- **AttributeError**: Resolved a crash in the Tkinter Target Entry tab caused by incorrect module mapping.
- **SQL Security**: Audited and improved SQL query safety across the backend logic.

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
