# Usage Guide: Tkinter Desktop Application

## Launching

From the project root:

```bash
python src/main.py tkinter
```

## Features

-   **Tabbed Interface:**
    Access all features (KPI hierarchy, templates, targets, results analysis, exports) via tabs.

-   **Target Entry:**
    Enter annual targets, automatically distribute to periods, and adjust as needed.

-   **KPI Management:**
    Create/edit groups, subgroups, indicators, and templates.

-   **Results Analysis & Export/Import:**
    Analyze distributed targets with charts and tables, and export/import all data to/from CSV/ZIP.

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

## See Also

-   [Automatic Target Generation Logic](target_generation.md)
-   [Architecture Overview](architecture.md)