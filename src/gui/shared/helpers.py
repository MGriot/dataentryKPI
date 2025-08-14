def get_kpi_display_name(kpi_data_row):
    if not kpi_data_row:
        return "N/A (Missing KPI Data)"
    try:
        g_name = (
            kpi_data_row["group_name"]
            if "group_name" in kpi_data_row.keys()
            else "N/G (No Group)"
        )
        sg_name = (
            kpi_data_row["subgroup_name"]
            if "subgroup_name" in kpi_data_row.keys()
            else "N/S (No Subgroup)"
        )
        i_name = (
            kpi_data_row["indicator_name"]
            if "indicator_name" in kpi_data_row.keys()
            else "N/I (No Indicator)"
        )
        g_name = g_name or "N/G (Empty Group Name)"
        sg_name = sg_name or "N/S (Empty Subgroup Name)"
        i_name = i_name or "N/I (Empty Indicator Name)"
        return f"{g_name} > {sg_name} > {i_name}"
    except (
        AttributeError,
        KeyError,
        IndexError,
        TypeError,
    ) as ex:
        print(f"Error in get_kpi_display_name (Data: {type(kpi_data_row)}): {ex}")
        return "N/A (KPI Data Structure Error)"
    except Exception as ex_general:
        print(f"Unexpected error in get_kpi_display_name: {ex_general}")
        return "N/A (Unexpected Display Name Error)"
