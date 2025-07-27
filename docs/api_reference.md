# API Reference

This document provides a reference for the key functions and modules within the Data Entry KPI application.

## 1. Core Utilities

### 1.1 `db_core.utils`

Provides utility functions related to database path management.

```python
def get_database_path(db_name: str) -> Path:
    """Constructs the absolute path to the database file.

    Args:
        db_name (str): The name of the database file (e.g., 'db_kpis.db').

    Returns:
        Path: The absolute path to the database file.
    """
```

### 1.2 `utils.kpi_utils`

Provides utility functions for KPI data manipulation and display.

```python
def get_kpi_display_name(kpi_data_dict: dict) -> str:
    """
    Generates a user-friendly display name for a KPI based on its hierarchical data.
    Expects a dictionary with 'group_name', 'subgroup_name', and 'indicator_name'.

    Args:
        kpi_data_dict (dict): A dictionary containing KPI data, typically from data_retriever.

    Returns:
        str: A formatted string representing the KPI's full name (e.g., "Group > Subgroup > Indicator").
    """
```

### 1.3 `utils.repartition_utils`

Provides mathematical utility functions for target repartitioning and distribution profiles.

```python
def get_weighted_proportions(num_periods: int, initial_factor: float, final_factor: float, decreasing: bool = True) -> list[float]:
    """
    Generates a list of proportions that are weighted, either increasing or decreasing.
    The sum of proportions is 1.
    """

def get_parabolic_proportions(num_periods: int, peak_at_center: bool = True, min_value_epsilon: float = 1e-09) -> list[float]:
    """
    Generates proportions following a parabolic curve. Sum of proportions is 1.
    """

def get_sinusoidal_proportions(num_periods: int, amplitude: float = 0.5, phase_offset: float = 0, min_value_epsilon: float = 1e-09) -> list[float]:
    """
    Generates proportions following a sinusoidal curve. Sum of proportions is 1.
    Amplitude is a fraction of the mean (e.g., 0.5 means +/- 50% of mean).
    """

def get_date_ranges_for_quarters(year: int) -> dict:
    """
    Returns a dictionary of quarter names (Q1, Q2, Q3, Q4) to tuples of (start_date, end_date).
    """
```

## 2. Data Retrieval

### 2.1 `data_retriever`

Provides functions to retrieve various types of data from the application's databases.

```python
def get_kpi_groups() -> list:
    """Fetches all KPI groups, ordered by name. Returns list of sqlite3.Row."""

def get_kpi_indicator_templates() -> list:
    """Fetches all KPI indicator templates, ordered by name. Returns list of sqlite3.Row."""

def get_kpi_indicator_template_by_id(template_id: int):
    """Fetches a specific KPI indicator template by its ID."""

def get_template_defined_indicators(template_id: int) -> list:
    """Fetches all indicators defined within a specific template, ordered by name."""

def get_template_indicator_definition_by_name(template_id: int, indicator_name: str):
    """Fetches a specific indicator definition within a template by its name."""

def get_template_indicator_definition_by_id(definition_id: int):
    """Fetches a specific indicator definition by its ID."""

def get_kpi_subgroups_by_group_revised(group_id: int) -> list:
    """Fetches all KPI subgroups for a given group ID, including the name of their linked template."""

def get_kpi_subgroup_by_id_with_template_name(subgroup_id: int):
    """Fetches a specific KPI subgroup by ID, including its template name if linked."""

def get_kpi_indicators_by_subgroup(subgroup_id: int) -> list:
    """Fetches all KPI indicators for a given subgroup ID, ordered by name."""

def get_all_kpis_detailed(only_visible: bool = False, stabilimento_id: int = None) -> list:
    """Fetches all KPI specifications with their full hierarchy names.
    Can filter by global visibility and per-stabilimento visibility.
    """

def get_kpi_detailed_by_id(kpi_spec_id: int, stabilimento_id: int = None):
    """Fetches a specific KPI specification by its ID, including hierarchy and template info.
    Can filter by per-stabilimento visibility.
    """

def get_all_stabilimenti(visible_only: bool = False) -> list:
    """Fetches all stabilimenti, optionally filtering by visibility, ordered by name."""

def get_linked_sub_kpis_detailed(master_kpi_spec_id: int) -> list:
    """Fetches detailed information for all Sub-KPIs linked to a Master KPI."""

def get_annual_target_entry(year: int, stabilimento_id: int, kpi_spec_id: int):
    """Fetches the annual target entry for a specific year, stabilimento, and KPI spec ID."""

def get_annual_targets(stabilimento_id: int, year: int):
    """Retrieves annual targets for a given stabilimento and year."""

def get_periodic_targets_for_kpi(year: int, stabilimento_id: int, kpi_spec_id: int, period_type: str, target_number: int) -> list:
    """Fetches repartited (periodic) target data for a specific KPI, year, stabilimento, period type, and target number."""

def get_sub_kpis_for_master(master_kpi_spec_id: int) -> list:
    """Returns a list of sub_kpi_spec_id linked to a master_kpi_spec_id."""

def get_master_kpi_for_sub(sub_kpi_spec_id: int):
    """Returns the master_kpi_spec_id for a given sub_kpi_spec_id, or None."""

def get_all_master_sub_kpi_links() -> list:
    """Returns all links (id, master_kpi_spec_id, sub_kpi_spec_id, distribution_weight)."""

def get_kpi_role_details(kpi_spec_id: int) -> dict:
    """Determines KPI role (Master, Sub, or None) and related info."""

def get_all_annual_target_entries_for_export() -> list:
    """Fetches all records from annual_targets for CSV export. Selects all relevant columns."""

def get_all_periodic_targets_for_export(period_type: str) -> list:
    """Fetches all records from a specific periodic target table for CSV export."""

def get_distinct_years() -> list:
    """Fetches all distinct years from the annual_targets table."""

def get_periodic_targets_for_kpi_all_stabilimenti(kpi_spec_id: int, period_type: str, year: int = None) -> list:
    """Fetches periodic targets for a specific KPI across all stabilimenti."""
```

## 3. KPI Management

### 3.1 `kpi_management.specs`

Functions for managing KPI specifications.

```python
def add_kpi_spec(indicator_id: int, description: str, calculation_type: str, unit_of_measure: str, visible: bool) -> int:
    """Adds a new KPI specification to the database."""

def update_kpi_spec(kpi_spec_id: int, indicator_id: int, description: str, calculation_type: str, unit_of_measure: str, visible: bool):
    """Updates an existing KPI specification's details."""

def delete_kpi_spec(kpi_spec_id: int):
    """Deletes a KPI specification by its ID."""
```

### 3.2 `kpi_management.indicators`

Functions for managing KPI indicators.

```python
def add_kpi_indicator(name: str, subgroup_id: int) -> int:
    """Adds a new KPI indicator to the database."""

def update_kpi_indicator(indicator_id: int, name: str, subgroup_id: int):
    """Updates an existing KPI indicator's details."""

def delete_kpi_indicator(indicator_id: int):
    """Deletes a KPI indicator by its ID."""
```

### 3.3 `kpi_management.visibility`

Functions for managing KPI visibility settings per stabilimento.

```python
def set_kpi_stabilimento_visibility(kpi_id: int, stabilimento_id: int, is_enabled: bool):
    """Sets or updates the visibility of a KPI for a specific stabilimento.
    If the entry does not exist, it will be created.
    """

def get_kpi_stabilimento_visibility(kpi_id: int, stabilimento_id: int) -> bool:
    """Gets the visibility status of a KPI for a specific stabilimento.
    Returns True if enabled, False if disabled, and True if no specific entry exists (default).
    """

def get_stabilimenti_for_kpi(kpi_id: int) -> list:
    """Returns a list of stabilimento IDs for which a KPI has explicit visibility settings.
    Each item in the list is a dictionary with 'stabilimento_id' and 'is_enabled'.
    """

def get_kpis_for_stabilimento(stabilimento_id: int) -> list:
    """Returns a list of KPI IDs for which a stabilimento has explicit visibility settings.
    Each item in the list is a dictionary with 'kpi_id' and 'is_enabled'.
    """

def delete_kpi_stabilimento_visibility(kpi_id: int, stabilimento_id: int):
    """Deletes a specific KPI-stabilimento visibility entry.
    This effectively reverts to the default visibility (True) for that pair.
    """
```

## 4. Stabilimenti Management

### 4.1 `stabilimenti_management.crud`

Functions for CRUD operations on Stabilimento records.

```python
def add_stabilimento(name: str, description: str = "", visible: bool = True, color: str = "#000000") -> int:
    """Adds a new stabilimento to the database."""

def update_stabilimento(stabilimento_id: int, name: str, description: str, visible: bool, color: str):
    """Updates an existing stabilimento's details."""

def update_stabilimento_color(stabilimento_id: int, color: str):
    """Updates the color of an existing stabilimento."""

def is_stabilimento_referenced(stabilimento_id: int) -> bool:
    """Checks if a stabilimento is referenced in the annual_targets table."""

def get_stabilimento_by_id(stabilimento_id: int) -> dict | None:
    """Retrieves a single stabilimento by its ID."""

def delete_stabilimento(stabilimento_id: int, force_delete_if_referenced: bool = False):
    """Deletes a stabilimento. By default, deletion is prevented if referenced in targets."""
```

## 5. Target Management

### 5.1 `target_management.annual`

Functions for managing annual KPI targets.

```python
def save_annual_targets(year: int, stabilimento_id: int, targets_data_map: dict, initiator_kpi_spec_id: int = None):
    """Saves annual targets, calculates formula-based targets, handles master/sub KPI
    distribution, and triggers repartition calculations.
    """

def calculate_and_save_all_repartitions(year: int, stabilimento_id: int, kpi_spec_id: int, target_number: int):
    """Main function to calculate and save all periodic repartitions (daily, weekly,
    monthly, quarterly) for a given annual target (Target 1 or Target 2).
    """
```