def get_kpi_display_name(kpi_data_row):
    if not kpi_data_row:
        return "N/D (KPI Data Mancante)"
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
        g_name = g_name or "N/G (Nome Gruppo Vuoto)"
        sg_name = sg_name or "N/S (Nome Sottogruppo Vuoto)"
        i_name = i_name or "N/I (Nome Indicatore Vuoto)"
        return f"{g_name} > {sg_name} > {i_name}"
    except (
        AttributeError,
        KeyError,
        IndexError,
        TypeError,
    ) as ex:
        print(f"Errore in get_kpi_display_name (Dati: {type(kpi_data_row)}): {ex}")
        return "N/D (Errore Struttura Dati KPI)"
    except Exception as ex_general:
        print(f"Errore imprevisto in get_kpi_display_name: {ex_general}")
        return "N/D (Errore Display Nome Imprevisto)"