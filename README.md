# Data Entry KPI Target Manager

## Overview

This project is a specialized data entry application designed for managing and distributing Key Performance Indicator (KPI) targets. It is **not** a dashboard or analytics platform, but a robust tool for inputting annual KPI targets and automatically splitting them into periodic targets (monthly, weekly, daily) using advanced, configurable logic.

The application is available as both a desktop (Tkinter) and web (Streamlit) interface, providing flexibility for different environments and user preferences.

## Purpose

- **Centralize KPI Target Entry:** Provide a structured interface for entering annual KPI targets for various indicators, departments, and facilities.
- **Automate Target Distribution:** Enable users to define how annual targets are split into smaller periods (months, weeks, days) using customizable distribution profiles and logic.
- **Support Complex KPI Structures:** Allow for hierarchical KPI definitions, template-based indicator creation, and master/sub-KPI relationships with weighted distributions.
- **Facilitate Data Export:** Make it easy to export all target data for integration with external reporting or dashboard systems.

## Key Features

### 1. KPI Target Entry & Management

- **Annual Target Input:** Enter yearly targets for each KPI, with support for multiple target values per KPI (e.g., Target 1, Target 2).
- **Manual or Automatic Entry:** Choose to enter targets manually for each period or let the system calculate them based on distribution logic.

### 2. Advanced Target Distribution Logic

- **Flexible Splitting:** Distribute annual targets into months, quarters, weeks, or days using several built-in profiles:
  - Even distribution
  - Progressive (front-loaded or back-loaded)
  - Sinusoidal (seasonal patterns)
  - Custom parabolic or event-based adjustments
- **Custom Period Allocations:** Override automatic splits by specifying custom percentages for each period (e.g., custom monthly weights).
- **Event Adjustments:** Apply spikes, dips, or other adjustments to daily targets for specific events or periods.

### 3. KPI Hierarchy & Templates

- **Hierarchical Structure:** Organize KPIs into groups, subgroups, and indicators for clear management.
- **Templates:** Define reusable templates for indicator sets, making it easy to apply standard KPIs across multiple subgroups.
- **Master/Sub-KPI Linking:** Link KPIs in master/subordinate relationships, with support for weighted target distribution among sub-KPIs.

### 4. Facility (Stabilimento) Management

- **Facility List:** Manage a list of facilities for which KPI targets are tracked.
- **Visibility Controls:** Mark facilities as visible or hidden for target entry.

### 5. Data Export

- **Export to CSV/Excel:** Export all entered and calculated target data in standard formats for use in external dashboards or reporting tools.
- **ZIP Packaging:** Bundle all exports into a single ZIP file for easy sharing or backup.

### 6. User Experience

- **Desktop & Web UI:** Use either a Tkinter-based desktop app or a Streamlit web app for data entry.
- **Validation & Guidance:** The UI guides users to ensure correct data entry, including validation of distribution percentages and logic.

## What This Project Is **Not**

- **No Dashboard/Visualization:** This tool does not provide KPI dashboards, charts, or analytics. It is focused solely on target entry and distribution.
- **No Real-Time Data Tracking:** It does not track actual KPI performance or collect operational data—only target values are managed.

## Data Sources & Storage

- **SQLite Databases:** All KPI definitions, targets, and distribution logic are stored in local SQLite databases.
- **CSV/Excel Export:** Data can be exported for use in other systems.

## Installation

### Prerequisites

- Python 3.7+
- Pip (Python package installer)

### Steps

1.  Clone the repository:

    ```bash
    git clone <repository_url>
    cd dataentryKPI
    ```

2.  Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Tkinter Desktop Application

The Tkinter desktop application provides a rich graphical interface for managing and visualizing data entry KPIs.

1.  Navigate to the `src` directory:

    ```bash
    cd src
    ```

2.  Run the application:

    ```bash
    python app_tkinter.py
    ```

3.  The application window will open, providing access to all features through a tabbed interface:

    *   **🎯 Inserimento Target (Target Entry):**
        *   Set annual targets for KPIs, specifying the year and facility.
        *   Choose a distribution profile (e.g., annual progressive, even distribution) to allocate the annual target across different periods.
        *   Define a repartition logic (monthly, quarterly, weekly) to further refine the target distribution.
        *   Manually override target values for specific sub-KPIs in a master-subordinate relationship.

    *   **🗂️ Gestione Gerarchia KPI (KPI Hierarchy Management):**
        *   Define a hierarchical structure for KPIs by creating groups, subgroups, and individual indicators.
        *   Add, edit, and delete KPI groups, subgroups, and indicators.
        *   Assign indicators to specific subgroups to categorize and organize KPIs.

    *   **📋 Gestione Template Indicatori (Indicator Template Management):**
        *   Create reusable templates for KPI indicators to streamline the KPI creation process.
        *   Define default calculation types, units of measure, and visibility settings for indicators within a template.
        *   Apply templates to KPI subgroups to automatically create and configure indicators based on the template definition.

    *   **⚙️ Gestione Specifiche KPI (KPI Specification Management):**
        *   Define detailed specifications for each KPI, including a description, calculation type, unit of measure, and visibility setting.
        *   Specify whether a KPI is visible for target entry, controlling its availability in the target setting section.
        *   Link KPIs to specific indicators to associate them with the defined KPI hierarchy.

    *   **🔗 Gestione Link Master/Sub (Master/Sub KPI Linking):**
        *   Establish master-subordinate relationships between KPIs to enable weighted target distribution.
        *   Define a distribution weight for each sub-KPI to control its share of the master KPI's target.
        *   Easily manage and visualize the master-subordinate relationships between KPIs.

    *   **🏭 Gestione Stabilimenti (Facility Management):**
        *   Manage a list of facilities for which KPIs are tracked.
        *   Add, edit, and delete facilities.
        *   Specify whether a facility is visible for target entry, controlling its availability in the target setting section.

    *   **📈 Visualizzazione Risultati (Results Visualization):**
        *   Visualize KPI results using charts and graphs.
        *   Filter data based on year, facility, KPI group, subgroup, and indicator.
        *   View target values and actual results for different periods (monthly, quarterly, weekly).

    *   **📦 Esportazione Dati (Data Export):**
        *   Export KPI data and visualizations in various formats (CSV, Excel, ZIP).
        *   Generate global CSV files containing all KPI data for external analysis and reporting.

### Streamlit Web Application

1.  Navigate to the `src` directory:

    ```bash
    cd src
    ```

2.  Run the application:

    ```bash
    streamlit run app_streamlit.py
    ```

3.  The dashboard will open in your web browser (usually at `http://localhost:8501`).

4.  Use the sidebar to select data, apply filters, and navigate between different sections of the dashboard.

## Customization

You can customize the dashboard by modifying the Python code in the `src` directory. Specifically, you can:

*   Add new KPIs and visualizations.
*   Modify data filtering options and UI elements.
*   Implement custom data processing logic.
*   Extend the functionality of the application with new features.

## Contributing

Contributions to this project are welcome! To contribute:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Implement your changes and write tests.
4.  Submit a pull request with a clear description of your changes.

## License

This project is licensed under the [MIT License](LICENSE).

## Contact

For questions or feedback, please contact Matteo Griot at matteo.griot@gmail.com.

