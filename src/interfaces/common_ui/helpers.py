def get_kpi_display_name(kpi_data):
    if not kpi_data:
        return "N/A (Missing KPI Data)"
    
    # Handle sqlite3.Row or dict
    if hasattr(kpi_data, 'keys'):
        keys = kpi_data.keys()
    else:
        # Fallback for sqlite3.Row if keys() is not available (though it usually is if row_factory is Row)
        # But some versions/wrappers might differ.
        try:
            keys = [d[0] for d in kpi_data.description]
        except:
            # If it's a dict-like object
            try:
                keys = list(kpi_data.keys())
            except:
                # Last resort: just try access
                keys = ["group_name", "subgroup_name", "indicator_name"]

    try:
        g_name = kpi_data["group_name"] if "group_name" in keys else "N/G"
        sg_name = kpi_data["subgroup_name"] if "subgroup_name" in keys else "N/S"
        i_name = kpi_data["indicator_name"] if "indicator_name" in keys else "N/I"
        
        g_name = g_name or "N/G"
        sg_name = sg_name or "N/S"
        i_name = i_name or "N/I"
        
        return f"{g_name} > {sg_name} > {i_name}"
    except Exception as ex:
        print(f"Error in get_kpi_display_name: {ex}")
        return "N/A (Error)"
