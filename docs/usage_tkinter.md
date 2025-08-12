# Usage Guide: Tkinter Desktop Application

## Launching

From the project root:

```bash
python src/main.py tkinter
```

## Features

-   **Tabbed Interface:**
    Access all features (KPI hierarchy, templates, targets, results analysis, data management) via tabs.

-   **Target Entry:**
    Enter annual targets, automatically distribute to periods, and adjust as needed.

-   **KPI Management:**
    Create/edit groups, subgroups, indicators, and templates.

-   **Data Management:**
    The "Gestione Dati" tab allows you to create a full backup of your data and restore it.
    -   **Crea Backup (ZIP):** This will export all your data (KPIs, Stabilimenti, Targets, etc.) into a single ZIP file. This is useful for migrating data or creating a restore point.
    -   **Ripristina da Backup (ZIP):** This will restore the application's state from a ZIP backup. **Warning:** This is a destructive operation and will overwrite all existing data.

### Managing KPI Visibility per Stabilimento

In the **'Gestione Specifiche KPI'** tab, when adding or editing a KPI, you can now control its visibility for each individual 'Stabilimento'.

*   Below the global 'Visibile per Target (Globale)' checkbox, a new section titled **'Visibilità per Stabilimento'** appears.
*   This section lists all configured 'Stabilimenti' with a checkbox next to each name.
*   **Check** a checkbox to make the KPI visible and active for that specific 'Stabilimento' in target entry and analysis views.
*   **Uncheck** a checkbox to hide the KPI for that 'Stabilimento'.
*   By default, if no specific setting is made for a 'Stabilimento', the KPI's global visibility setting applies.

### Setting Stabilimento Colors

In the **'Gestione Stabilimenti'** tab, when adding a new 'Stabilimento' or modifying an existing one, you can now assign a specific color.

*   When you open the 'Aggiungi' or 'Modifica' dialog for a 'Stabilimento', a new **'Colore'** field with a color preview and a **'Scegli...'** button is available.
*   Click the **'Scegli...'** button to open a color picker dialog.
*   Select your desired color, and it will be saved with the 'Stabilimento' record.
*   This color will then be used in various parts of the application, such as charts and displays, to visually distinguish data related to that 'Stabilimento'.

## Backup Data Structure

The backup ZIP file contains a set of CSV files that represent the entire state of the application. Here is a description of each file:

-   `dict_stabilimenti.csv`: Contains the list of all stabilimenti.
-   `dict_kpis.csv`: Contains the specifications of all KPIs.
-   `all_annual_kpi_master_targets.csv`: Contains the annual master targets for all KPIs and stabilimenti.
-   `all_daily_kpi_targets.csv`: Contains the daily targets.
-   `all_weekly_kpi_targets.csv`: Contains the weekly targets.
-   `all_monthly_kpi_targets.csv`: Contains the monthly targets.
-   `all_quarterly_kpi_targets.csv`: Contains the quarterly targets.

## See Also

-   [Automatic Target Generation Logic](target_generation.md)
-   [Architecture Overview](architecture.md)
