import streamlit as st
import pandas as pd
import database_manager as db
import export_manager  # Importa il nuovo modulo
import json
import datetime
import calendar
from pathlib import Path  # Per st.download_button

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="Gestione Target KPI")
st.title("📊 Applicazione Gestione Target KPI")
st.markdown("Utilizza la barra laterale per navigare tra le diverse sezioni.")

# --- Sidebar Navigation (Updated) ---
page = st.sidebar.radio(
    "Seleziona una pagina",
    (
        "Inserimento Target",
        "Gestione KPI e Gerarchia",  # Pages combined and renamed
        "Gestione Stabilimenti",
        "Visualizzazione Risultati",
        "Esportazione Dati",
    ),
)


# --- Utility Functions for KPI Hierarchy ---
# These functions are local to this Streamlit script.
# They act as a bridge between the Streamlit UI and the database manager.
def get_group_options():
    """Fetches KPI groups from the DB and formats them for a Streamlit selectbox."""
    groups = db.get_kpi_groups()
    return {g["name"]: g["id"] for g in groups}


def get_subgroup_options(group_id):
    """Fetches KPI subgroups for a given group ID and formats them."""
    if not group_id:
        return {}
    subgroups = db.get_kpi_subgroups_by_group(group_id)
    return {sg["name"]: sg["id"] for sg in subgroups}


def get_indicator_options(subgroup_id):
    """Fetches KPI indicators for a given subgroup ID and formats them."""
    if not subgroup_id:
        return {}
    indicators = db.get_kpi_indicators_by_subgroup(subgroup_id)
    return {i["name"]: i["id"] for i in indicators}


def get_kpi_display_name(kpi_row):
    """Creates a full hierarchical name for a KPI for display purposes."""
    return f"{kpi_row['group_name']} > {kpi_row['subgroup_name']} > {kpi_row['indicator_name']}"


# --- Cached Data Loading Functions ---
@st.cache_data  # Cache for KPI data which now includes the hierarchy
def get_kpi_df_with_hierarchy():
    """Fetches all KPI specifications with their full hierarchy names."""
    kpis = (
        db.get_kpis()
    )  # This function now returns group_name, subgroup_name, indicator_name
    if not kpis:
        return pd.DataFrame(
            columns=[
                "ID",
                "Gruppo",
                "Sottogruppo",
                "Indicatore",
                "Descrizione",
                "Tipo Calcolo",
                "Unità Misura",
                "Visibile",
            ]
        )

    df_data = []
    for kpi_row in kpis:
        df_data.append(
            {
                "ID": kpi_row["id"],
                "Gruppo": kpi_row["group_name"],
                "Sottogruppo": kpi_row["subgroup_name"],
                "Indicatore": kpi_row["indicator_name"],
                "Descrizione": kpi_row["description"],
                "Tipo Calcolo": kpi_row["calculation_type"],
                "Unità Misura": (
                    kpi_row["unit_of_measure"] if kpi_row["unit_of_measure"] else ""
                ),
                "Visibile": True if kpi_row["visible"] == 1 else False,
            }
        )
    return pd.DataFrame(df_data)


@st.cache_data
def get_stabilimenti_df():
    """Fetches all stabilimenti (locations/plants) from the database."""
    stabilimenti = db.get_stabilimenti()
    if not stabilimenti:
        return pd.DataFrame(columns=["ID", "Nome", "Visibile"])
    df = pd.DataFrame(stabilimenti, columns=["id", "name", "visible"])
    df.rename(columns={"id": "ID", "name": "Nome", "visible": "Visibile"}, inplace=True)
    df["Visibile"] = df["Visibile"].apply(lambda x: True if x == 1 else False)
    return df


# --- COMBINED PAGE: KPI AND HIERARCHY MANAGEMENT ---
if page == "Gestione KPI e Gerarchia":
    st.header("⚙️ Gestione KPI e Gerarchia")

    # --- Initialize session state for cascading dropdowns in the 'Add Spec' form ---
    if 'add_spec_group_name' not in st.session_state:
        st.session_state.add_spec_group_name = None
    if 'add_spec_subgroup_name' not in st.session_state:
        st.session_state.add_spec_subgroup_name = None

    # --- Callback to reset child dropdowns when a parent changes ---
    def reset_subgroup_selection():
        st.session_state.add_spec_subgroup_name = None

    col_hierarchy, col_specs = st.columns([1, 2], gap="large")

    with col_hierarchy:
        st.subheader("Crea Nuova Gerarchia")

        # Form to add a new group
        with st.form("new_group_form", clear_on_submit=True):
            st.markdown("**1. Aggiungi Gruppo**")
            new_group_name = st.text_input("Nome Nuovo Gruppo")
            if st.form_submit_button("Crea Gruppo", use_container_width=True):
                if new_group_name:
                    try:
                        db.add_kpi_group(new_group_name)
                        st.success(f"Gruppo '{new_group_name}' aggiunto.")
                    except Exception as e:
                        st.error(f"Errore: Il gruppo potrebbe già esistere. ({e})")
                else:
                    st.warning("Inserisci un nome per il gruppo.")
        st.markdown("---")

        # Form to add a new subgroup
        with st.form("new_subgroup_form", clear_on_submit=True):
            st.markdown("**2. Aggiungi Sottogruppo**")
            group_options_sg = db.get_group_options()
            parent_group_name_sg = st.selectbox(
                "Scegli Gruppo di appartenenza", list(group_options_sg.keys()), index=None
            )
            new_subgroup_name = st.text_input("Nome Nuovo Sottogruppo")
            if st.form_submit_button("Crea Sottogruppo", use_container_width=True):
                if new_subgroup_name and parent_group_name_sg:
                    parent_group_id_sg = group_options_sg.get(parent_group_name_sg)
                    try:
                        db.add_kpi_subgroup(new_subgroup_name, parent_group_id_sg)
                        st.success(f"Sottogruppo '{new_subgroup_name}' aggiunto.")
                    except Exception as e:
                        st.error(f"Errore: Il sottogruppo potrebbe già esistere in questo gruppo. ({e})")
                else:
                    st.warning("Scegli un gruppo e inserisci un nome.")
        st.markdown("---")
        
        # Form to add a new indicator
        with st.form("new_indicator_form", clear_on_submit=True):
            st.markdown("**3. Aggiungi Indicatore**")
            group_options_ind = db.get_group_options()
            parent_group_name_ind = st.selectbox(
                "Scegli Gruppo", list(group_options_ind.keys()), index=None, key="ind_group_sel"
            )
            parent_group_id_ind = group_options_ind.get(parent_group_name_ind)
            
            subgroup_options_ind = db.get_subgroup_options(parent_group_id_ind)
            parent_subgroup_name_ind = st.selectbox(
                "Scegli Sottogruppo", list(subgroup_options_ind.keys()), index=None, disabled=not parent_group_id_ind
            )
            new_indicator_name = st.text_input("Nome Nuovo Indicatore")
            
            if st.form_submit_button("Crea Indicatore", use_container_width=True):
                if new_indicator_name and parent_subgroup_name_ind:
                    parent_subgroup_id_ind = subgroup_options_ind.get(parent_subgroup_name_ind)
                    try:
                        db.add_kpi_indicator(new_indicator_name, parent_subgroup_id_ind)
                        st.success(f"Indicatore '{new_indicator_name}' aggiunto.")
                    except Exception as e:
                        st.error(f"Errore: L'indicatore potrebbe già esistere in questo sottogruppo. ({e})")
                else:
                    st.warning("Scegli gruppo, sottogruppo e inserisci un nome.")

    with col_specs:
        st.subheader("Aggiungi e Modifica Specifiche KPI")

        with st.expander("Aggiungi una nuova Specifica KPI", expanded=True):
            with st.form("new_kpi_spec_form", clear_on_submit=True):
                st.write("**Seleziona la gerarchia per il nuovo KPI:**")

                # --- Cascading Dropdowns (FIXED) ---
                groups_dict = db.get_group_options()
                
                selected_group_name = st.selectbox(
                    "Gruppo", list(groups_dict.keys()), index=None,
                    key='add_spec_group_name', on_change=reset_subgroup_selection
                )
                selected_group_id = groups_dict.get(st.session_state.add_spec_group_name)

                subgroups_dict = db.get_subgroup_options(selected_group_id)
                selected_subgroup_name = st.selectbox(
                    "Sottogruppo", list(subgroups_dict.keys()), index=None,
                    key='add_spec_subgroup_name', disabled=not selected_group_id
                )
                selected_subgroup_id = subgroups_dict.get(st.session_state.add_spec_subgroup_name)

                indicators_dict = db.get_indicator_options(selected_subgroup_id)
                # Filter out indicators that already have a KPI spec
                kpis_with_specs = [k['indicator_id'] for k in db.get_kpis()]
                available_indicators = {
                    name: ind_id for name, ind_id in indicators_dict.items() if ind_id not in kpis_with_specs
                }
                selected_indicator_name = st.selectbox(
                    "Indicatore (solo quelli senza specifica)", list(available_indicators.keys()), index=None,
                    disabled=not selected_subgroup_id
                )
                selected_indicator_id = available_indicators.get(selected_indicator_name)

                st.markdown("---")
                st.write("**Dettagli della Specifica:**")
                new_desc = st.text_area("Descrizione")
                new_type = st.selectbox("Tipologia di Calcolo *", ("Incrementale", "Media"), index=None)
                new_unit = st.text_input("Unità di Misura (es. %, €, Unità)")
                new_visible = st.checkbox("Visibile nel data entry", value=True)

                if st.form_submit_button("Aggiungi Specifica KPI", use_container_width=True):
                    if not selected_indicator_id or not new_type:
                        st.error("Seleziona una gerarchia completa e una tipologia di calcolo.")
                    else:
                        try:
                            db.add_kpi(selected_indicator_id, new_desc, new_type, new_unit, new_visible)
                            st.success(f"Specifica KPI per '{selected_indicator_name}' aggiunta!")
                            get_kpi_df_with_hierarchy.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore: Esiste già una specifica per questo indicatore. ({e})")

        st.markdown("---")
        st.subheader("Elenco Specifiche KPI Esistenti")
        if st.button("Ricarica elenco KPI"):
            get_kpi_df_with_hierarchy.clear()
            st.rerun()
        
        try:
            kpi_df = get_kpi_df_with_hierarchy()
            st.data_editor(
                kpi_df, key="kpi_spec_editor",
                column_config={
                    "ID": None, # Hide ID column
                    "Descrizione": st.column_config.TextColumn(width="large"),
                    "Tipo Calcolo": st.column_config.SelectboxColumn(options=["Incrementale", "Media"]),
                    "Visibile": st.column_config.CheckboxColumn(),
                },
                disabled=["ID", "Gruppo", "Sottogruppo", "Indicatore"], hide_index=True, use_container_width=True
            )
            st.caption("Le modifiche a Descrizione, Tipo Calcolo, ecc. non sono ancora salvate. La modifica diretta verrà implementata a breve.")
        except Exception as e:
            st.error(f"Impossibile caricare le specifiche KPI: {e}")


# --- PAGE: STABILIMENTI MANAGEMENT (Locations/Plants) ---
elif page == "Gestione Stabilimenti":
    st.header("🏭 Gestione Stabilimenti")

    with st.expander("Aggiungi nuovo stabilimento", expanded=False):
        with st.form("new_stabilimento_form", clear_on_submit=True):
            new_name = st.text_input("Nome Stabilimento *")
            new_visible = st.checkbox("Visibile", value=True)
            if st.form_submit_button("Aggiungi Stabilimento"):
                if not new_name:
                    st.error("Nome obbligatorio.")
                else:
                    try:
                        db.add_stabilimento(new_name, new_visible)
                        st.success(f"Stabilimento '{new_name}' aggiunto!")
                        get_stabilimenti_df.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore: {e}")

    st.subheader("Elenco Stabilimenti Esistenti")
    if st.button("Ricarica elenco Stabilimenti"):
        get_stabilimenti_df.clear()
        st.rerun()

    try:
        edited_df = st.data_editor(
            get_stabilimenti_df(),
            key="stabilimento_editor",
            column_config={
                "ID": st.column_config.NumberColumn(disabled=True),
                "Nome": st.column_config.TextColumn(),
                "Visibile": st.column_config.CheckboxColumn("Visibile", default=True),
            },
            hide_index=True,
            use_container_width=True,
        )
        # Logic to handle edits could be added here
    except Exception as e:
        st.error(f"Impossibile caricare stabilimenti: {e}")


# --- PAGE: TARGET ENTRY ---
elif page == "Inserimento Target":
    st.header("🎯 Inserimento Target Annuali")

    col1, col2 = st.columns(2)
    current_year = datetime.datetime.now().year
    with col1:
        selected_year = st.number_input(
            "Anno", min_value=2020, max_value=2050, value=current_year
        )
    with col2:
        stabilimenti_visibili = db.get_stabilimenti(only_visible=True)
        if not stabilimenti_visibili:
            st.warning(
                "Nessuno stabilimento visibile. Aggiungine uno in 'Gestione Stabilimenti'."
            )
            st.stop()

        stabilimenti_dict = {s["name"]: s["id"] for s in stabilimenti_visibili}
        selected_stabilimento_name = st.selectbox(
            "Stabilimento",
            options=list(stabilimenti_dict.keys()),
            index=None,
            placeholder="Scegli stabilimento...",
        )

        if not selected_stabilimento_name:
            st.info("Seleziona uno stabilimento per procedere.")
            st.stop()

        selected_stabilimento_id = stabilimenti_dict[selected_stabilimento_name]

    st.markdown("---")
    kpis_list_for_target = db.get_kpis(only_visible=True)

    if not kpis_list_for_target:
        st.warning("Nessun KPI visibile definito. Aggiungine uno in 'Gestione KPI'.")
        st.stop()

    targets_to_save = {}
    all_valid = True
    distribution_profile_options = [
        "annual_progressive",
        "monthly_sinusoidal",
        "legacy_intra_period_progressive",
    ]

    with st.form("targets_form_entry"):
        for kpi_row in kpis_list_for_target:
            kpi_id = kpi_row["id"]
            kpi_display_name = get_kpi_display_name(kpi_row)
            kpi_unit = kpi_row["unit_of_measure"]
            kpi_calc_type = kpi_row["calculation_type"]

            exp_label = f"🎯 Target per: {kpi_display_name}" + (
                f" ({kpi_unit})" if kpi_unit else ""
            )
            with st.expander(exp_label, expanded=True):
                existing_target = db.get_annual_target(
                    selected_year, selected_stabilimento_id, kpi_id
                )

                def_target1 = (
                    float(existing_target["annual_target1"]) if existing_target else 0.0
                )
                def_target2 = (
                    float(existing_target["annual_target2"]) if existing_target else 0.0
                )
                def_logic = (
                    existing_target["repartition_logic"] if existing_target else "Mese"
                )
                def_profile = existing_target.get(
                    "distribution_profile", "annual_progressive"
                )
                def_repart_map = (
                    json.loads(existing_target["repartition_values"])
                    if existing_target and existing_target["repartition_values"]
                    else {}
                )

                t_col1, t_col2, prof_col = st.columns(3)
                with t_col1:
                    annual_target1_val = st.number_input(
                        f"Target 1 ({kpi_unit or 'Valore'})",
                        value=def_target1,
                        key=f"target1_{kpi_id}",
                        min_value=0.0,
                        format="%.2f",
                    )
                with t_col2:
                    annual_target2_val = st.number_input(
                        f"Target 2 ({kpi_unit or 'Valore'})",
                        value=def_target2,
                        key=f"target2_{kpi_id}",
                        min_value=0.0,
                        format="%.2f",
                    )
                with prof_col:
                    sel_profile = st.selectbox(
                        "Profilo Distribuzione",
                        options=distribution_profile_options,
                        index=distribution_profile_options.index(def_profile),
                        key=f"profile_target_{kpi_id}",
                    )

                repart_logic_val = st.radio(
                    "Logica Ripartizione",
                    ["Mese", "Trimestre"],
                    index=["Mese", "Trimestre"].index(def_logic),
                    key=f"logic_target_disp_{kpi_id}",
                    horizontal=True,
                )
                st.markdown(f"**Percentuali di ripartizione per {repart_logic_val}**")

                if repart_logic_val == "Mese":
                    items = [calendar.month_name[i] for i in range(1, 13)]
                    cols_rep = st.columns(6)
                    default_p_float = round(100.0 / 12.0, 2)
                else:  # Trimestre
                    items = ["Q1", "Q2", "Q3", "Q4"]
                    cols_rep = st.columns(4)
                    default_p_float = 25.0

                repart_values_in = {}
                for i, item_name in enumerate(items):
                    with cols_rep[i % len(cols_rep)]:
                        repart_values_in[item_name] = st.number_input(
                            f"% {item_name}",
                            value=float(def_repart_map.get(item_name, default_p_float)),
                            key=f"rep_target_{kpi_id}_{item_name}",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.01,
                            format="%.2f",
                        )

                if annual_target1_val > 0.0 or annual_target2_val > 0.0:
                    total_perc = sum(repart_values_in.values())
                    if not (99.9 <= total_perc <= 100.1):
                        st.error(
                            f"Per '{kpi_display_name}', la somma delle % ({repart_logic_val}) è {total_perc:.2f}%. Deve essere ~100%."
                        )
                        all_valid = False

                targets_to_save[kpi_id] = {
                    "annual_target1": annual_target1_val,
                    "annual_target2": annual_target2_val,
                    "repartition_logic": repart_logic_val,
                    "repartition_values": repart_values_in,
                    "distribution_profile": sel_profile,
                }

        if st.form_submit_button("Salva Tutti i Target", type="primary"):
            if not all_valid:
                st.error(
                    "Correggi gli errori di validazione (somma percentuali) prima di salvare."
                )
            else:
                try:
                    db.save_annual_targets(
                        selected_year, selected_stabilimento_id, targets_to_save
                    )
                    st.success("Target salvati con successo!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Errore durante il salvataggio dei target: {e}")
                    st.exception(e)


# --- PAGE: RESULTS VISUALIZATION ---
elif page == "Visualizzazione Risultati":
    st.header("📈 Visualizzazione Dati Ripartiti")

    fc1, fc2, fc3, fc4, fc5 = st.columns(5)

    with fc1:
        sel_y_vis = st.number_input(
            "Anno",
            min_value=2020,
            max_value=2050,
            value=datetime.datetime.now().year,
            key="vis_y_res",
        )

    with fc2:
        stabilimenti_vis = db.get_stabilimenti()
        s_map_vis = {s["name"]: s["id"] for s in stabilimenti_vis}
        sel_s_name_vis = st.selectbox(
            "Stabilimento",
            options=list(s_map_vis.keys()),
            key="vis_s_name_res_sb",
            index=None,
            placeholder="Scegli stabilimento...",
        )
        sel_s_id = s_map_vis.get(sel_s_name_vis)

    with fc3:
        groups_dict_vis = get_group_options()
        sel_group_name_vis = st.selectbox(
            "Gruppo KPI",
            list(groups_dict_vis.keys()),
            index=None,
            key="vis_group_kpi",
            placeholder="Scegli Gruppo...",
        )
        sel_group_id_vis = groups_dict_vis.get(sel_group_name_vis)

        subgroups_dict_vis = get_subgroup_options(sel_group_id_vis)
        sel_subgroup_name_vis = st.selectbox(
            "Sottogruppo KPI",
            list(subgroups_dict_vis.keys()),
            index=None,
            key="vis_subgroup_kpi",
            disabled=not sel_group_id_vis,
            placeholder="Scegli Sottogruppo...",
        )
        sel_subgroup_id_vis = subgroups_dict_vis.get(sel_subgroup_name_vis)

        indicators_dict_vis = get_indicator_options(sel_subgroup_id_vis)
        sel_indicator_name_vis = st.selectbox(
            "Indicatore KPI",
            list(indicators_dict_vis.keys()),
            index=None,
            key="vis_indicator_kpi",
            disabled=not sel_subgroup_id_vis,
            placeholder="Scegli Indicatore...",
        )
        sel_indicator_id_vis = indicators_dict_vis.get(sel_indicator_name_vis)

    with fc4:
        period_sel_vis = st.selectbox(
            "Periodicità",
            ["Giorno", "Settimana", "Mese", "Trimestre"],
            index=2,
            key="vis_p_res_sel",
        )

    with fc5:
        target_num_sel = st.radio(
            "Seleziona Target", (1, 2), key="vis_target_num_sel", horizontal=True
        )

    # Find the KPI ID from the selected indicator
    sel_k_id_vis = None
    if sel_indicator_id_vis:
        found_kpi = db.get_kpi_by_indicator_id(sel_indicator_id_vis)
        if found_kpi:
            sel_k_id_vis = found_kpi["id"]
            sel_k_name_vis = get_kpi_display_name(found_kpi)
            st.caption(f"Visualizzazione per: {sel_k_name_vis}")
        else:
            st.warning("Specifica KPI non trovata per l'indicatore selezionato.")

    if sel_s_id and sel_k_id_vis:
        try:
            data_rip_vis = db.get_ripartiti_data(
                sel_y_vis, sel_s_id, sel_k_id_vis, period_sel_vis, target_num_sel
            )
            if data_rip_vis:
                st.dataframe(data_rip_vis, use_container_width=True)
            else:
                st.info(
                    "Nessun dato ripartito trovato per la selezione corrente. Hai salvato i target per questo anno/stabilimento/KPI?"
                )
        except Exception as e:
            st.error(f"Errore nel recupero dei dati: {e}")
    else:
        st.info(
            "Seleziona Anno, Stabilimento e una Gerarchia KPI completa per visualizzare i dati."
        )

# --- PAGE: DATA EXPORT ---
elif page == "Esportazione Dati":
    st.header("📤 Esportazione Dati")
    # Placeholder for export functionality
    st.info("Funzionalità di esportazione in costruzione.")
