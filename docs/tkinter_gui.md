# Tkinter Desktop Application Guide

## Overview

The Tkinter desktop application provides a graphical interface for entering, managing, and distributing KPI targets. It is focused solely on data entry and target repartition, not on visualization or analytics.

## How to Launch

1. Navigate to the project directory containing the source code (e.g., `src`).
2. Run the application:

    ```bash
    python app_tkinter.py
    ```

3. The application window will open, providing access to all features through a tabbed interface.

## Main Sections

- **🎯 Inserimento Target (Target Entry):**
    - Set annual targets for KPIs, specifying the year and facility.
    - Choose a distribution profile (e.g., annual progressive, even distribution) to allocate the annual target across different periods.
    - Define repartition logic (monthly, quarterly, weekly) to further refine the target distribution.
    - Manually override target values for specific sub-KPIs in a master-subordinate relationship.

- **🗂️ Gestione Gerarchia KPI (KPI Hierarchy Management):**
    - Define a hierarchical structure for KPIs by creating groups, subgroups, and individual indicators.
    - Add, edit, and delete KPI groups, subgroups, and indicators.
    - Assign indicators to specific subgroups to categorize and organize KPIs.

- **📋 Gestione Template Indicatori (Indicator Template Management):**
    - Create reusable templates for KPI indicators to streamline the KPI creation process.
    - Define default calculation types, units of measure, and visibility settings for indicators within a template.
    - Apply templates to KPI subgroups to automatically create and configure indicators based on the template definition.

- **⚙️ Gestione Specifiche KPI (KPI Specification Management):**
    - Define detailed specifications for each KPI, including a description, calculation type, unit of measure, and visibility setting.
    - Specify whether a KPI is visible for target entry, controlling its availability in the target setting section.
    - Link KPIs to specific indicators to associate them with the defined KPI hierarchy.

- **🔗 Gestione Link Master/Sub (Master/Sub KPI Linking):**
    - Establish master-subordinate relationships between KPIs to enable weighted target distribution.
    - Define a distribution weight for each sub-KPI to control its share of the master KPI's target.
    - Easily manage and visualize the master-subordinate relationships between KPIs.

- **🏭 Gestione Stabilimenti (Facility Management):**
    - Manage a list of facilities for which KPI targets are tracked.
    - Add, edit, and delete facilities.
    - Specify whether a facility is visible for target entry, controlling its availability in the target setting section.

- **📦 Esportazione Dati (Data Export):**
    - Export KPI target data in CSV, Excel, or ZIP format for use in external reporting or dashboard tools.

## Notes

- The application does **not** provide charts, dashboards, or analytics. It is strictly for data entry and target repartition.
- All data is stored locally in SQLite databases.
- For troubleshooting, check the application logs or contact the maintainer.

# [DEPRECATED] See [Usage Guide: Tkinter Desktop Application](usage_tkinter.md)

