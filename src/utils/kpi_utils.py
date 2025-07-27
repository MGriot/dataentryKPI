def get_kpi_display_name(kpi_data_dict):
    """
    Generates a user-friendly display name for a KPI based on its hierarchical data.
    Expects a dictionary with 'group_name', 'subgroup_name', and 'indicator_name'.
    """
    group = kpi_data_dict.get("group_name", "N/D")
    subgroup = kpi_data_dict.get("subgroup_name", "N/D")
    indicator = kpi_data_dict.get("indicator_name", "N/D")
    return f"{group} > {subgroup} > {indicator}"