# Data Entry KPI Dashboard

## Overview

This project provides a comprehensive dashboard solution for visualizing, analyzing, and managing Key Performance Indicators (KPIs) related to data entry processes. It offers both a desktop application (Tkinter) and a web application (Streamlit) to cater to different user preferences and deployment scenarios.

## Goals

*   Provide a user-friendly interface for monitoring data entry performance.
*   Enable data-driven decision-making through insightful visualizations.
*   Facilitate efficient target setting and performance tracking.
*   Offer flexible deployment options with both desktop and web applications.

## Features

*   **Data Visualization:** Displays KPIs using a variety of charts and graphs for easy understanding of trends and performance.
*   **Data Filtering:** Allows users to filter data based on various criteria such as date ranges, data entry operators, departments, and more.
*   **Performance Tracking:** Tracks the performance of data entry operators, teams, and the overall process over time.
*   **Target Setting:** Enables users to set annual targets for KPIs and distribute them across different periods (monthly, quarterly, weekly).
*   **Data Export:** Allows exporting analyzed data and visualizations in various formats (CSV, Excel, ZIP).
*   **KPI Hierarchy Management:** Provides tools to define and manage a hierarchical structure for KPIs (Groups, Subgroups, Indicators).
*   **KPI Specification Management:** Allows defining detailed specifications for each KPI, including calculation types, units of measure, and visibility settings.
*   **Stabilimento (Facility) Management:** Manages a list of facilities for which KPIs are tracked.
*   **Master/Sub KPI Linking:** Allows linking KPIs to create master-subordinate relationships, enabling weighted target distribution.
*   **User Authentication (Future):** (Planned) Secure access to the dashboard with user accounts and permission levels.

## Data Sources

The application uses data primarily from structured data sources, including:

*   **SQLite Databases:** Stores KPI definitions, targets, and historical data.
*   **CSV/Excel Files:** Used for importing historical data and exporting analyzed results.

Ensure that data is properly formatted with columns for date, operator, facility, and relevant data entry metrics.

## Installation

### Prerequisites

*   Python 3.7+
*   Pip (Python package installer)

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

