import streamlit as st
import data_retriever
from kpi_management import specs as kpi_specs_manager
from kpi_management import indicators as kpi_indicators_manager
from kpi_management import visibility as kpi_visibility
from gui.shared.constants import KPI_CALC_TYPE_OPTIONS

def app():
    st.title("⚙️ Gestione Specifiche KPI")

    # State management for selected KPI
    if 'selected_kpi_spec_id' not in st.session_state:
        st.session_state.selected_kpi_spec_id = None
    if 'kpi_edit_mode' not in st.session_state:
        st.session_state.kpi_edit_mode = False

    # Fetch all stabilimenti for visibility controls
    all_stabilimenti = data_retriever.get_all_stabilimenti()
    stabilimento_options = {s['name']: s['id'] for s in all_stabilimenti}

    # --- Add/Edit KPI Specification ---
    st.header("Aggiungi/Modifica Specifica KPI")

    with st.form(key='kpi_spec_form'):
        # Hierarchy selection (simplified for now, assuming pre-existing groups/subgroups/indicators)
        # In a real app, these would be dynamic dropdowns based on selections
        st.subheader("Selezione Gerarchia KPI")
        groups = data_retriever.get_kpi_groups()
        group_names = [g['name'] for g in groups]
        selected_group_name = st.selectbox("Gruppo:", group_names, key='kpi_spec_group')

        selected_group_id = next((g['id'] for g in groups if g['name'] == selected_group_name), None)
        subgroups = []
        if selected_group_id:
            subgroups = data_retriever.get_kpi_subgroups_by_group_revised(selected_group_id)
        subgroup_display_names = []
        subgroup_raw_to_display_map = {}
        for sg_dict in subgroups:
            raw_name = sg_dict['name']
            display_name = raw_name + (f" (Tpl: {sg_dict['template_name']})" if sg_dict.get("template_name") else "")
            subgroup_display_names.append(display_name)
            subgroup_raw_to_display_map[raw_name] = display_name

        selected_subgroup_display_name = st.selectbox("Sottogruppo:", subgroup_display_names, key='kpi_spec_subgroup')
        selected_subgroup_raw_name = next((raw for raw, display in subgroup_raw_to_display_map.items() if display == selected_subgroup_display_name), None)

        selected_subgroup_id = next((sg['id'] for sg in subgroups if sg['name'] == selected_subgroup_raw_name), None)
        indicators = []
        if selected_subgroup_id:
            indicators = data_retriever.get_kpi_indicators_by_subgroup(selected_subgroup_id)
        indicator_names = [ind['name'] for ind in indicators]
        selected_indicator_name = st.selectbox("Indicatore:", indicator_names, key='kpi_spec_indicator')
        selected_indicator_id = next((ind['id'] for ind in indicators if ind['name'] == selected_indicator_name), None)

        st.subheader("Dettagli Specifica")
        description = st.text_area("Descrizione:", key='kpi_spec_desc')
        calculation_type = st.selectbox("Tipo Calcolo:", KPI_CALC_TYPE_OPTIONS, key='kpi_spec_calc_type')
        unit_of_measure = st.text_input("Unità Misura:", key='kpi_spec_unit')
        visible_global = st.checkbox("Visibile per Target (Globale)", value=True, key='kpi_spec_visible_global')

        # --- KPI-Stabilimento Visibility Controls ---
        st.subheader("Visibilità per Stabilimento")
        # Use a dictionary to store the state of each checkbox
        stabilimento_checkbox_states = {}
        for stab_name, stab_id in stabilimento_options.items():
            # Default to True if no specific setting is found
            default_enabled = True
            if st.session_state.selected_kpi_spec_id:
                # If editing, try to load existing setting
                current_kpi_stab_visibility = kpi_visibility.get_kpi_stabilimento_visibility(st.session_state.selected_kpi_spec_id, stab_id)
                default_enabled = current_kpi_stab_visibility
            
            stabilimento_checkbox_states[stab_id] = st.checkbox(
                f"Abilita per {stab_name}", 
                value=default_enabled, 
                key=f"stab_chk_{stab_id}"
            )

        col1, col2 = st.columns(2)
        with col1:
            save_button = st.form_submit_button("Salva Specifica KPI")
        with col2:
            clear_button = st.form_submit_button("Pulisci Campi")

        if save_button:
            if selected_indicator_id:
                try:
                    if st.session_state.kpi_edit_mode and st.session_state.selected_kpi_spec_id:
                        kpi_specs_manager.update_kpi_spec(
                            st.session_state.selected_kpi_spec_id,
                            selected_indicator_id,
                            description,
                            calculation_type,
                            unit_of_measure,
                            visible_global,
                        )
                        st.success("Specifica KPI aggiornata!")
                        kpi_id_to_save_visibility = st.session_state.selected_kpi_spec_id
                    else:
                        # Add new KPI spec
                        new_kpi_id = kpi_specs_manager.add_kpi_spec(
                            selected_indicator_id, description, calculation_type, unit_of_measure, visible_global
                        )
                        st.success("Nuova specifica KPI aggiunta!")
                        kpi_id_to_save_visibility = new_kpi_id
                    
                    # Save per-stabilimento visibility settings
                    for stab_id, is_enabled in stabilimento_checkbox_states.items():
                        kpi_visibility.set_kpi_stabilimento_visibility(kpi_id_to_save_visibility, stab_id, is_enabled)

                    st.session_state.kpi_edit_mode = False
                    st.session_state.selected_kpi_spec_id = None
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Errore nel salvare la specifica KPI: {e}")
            else:
                st.warning("Seleziona un indicatore valido per la specifica KPI.")

        if clear_button:
            st.session_state.selected_kpi_spec_id = None
            st.session_state.kpi_edit_mode = False
            st.experimental_rerun()

    # --- Display Existing KPI Specifications ---
    st.header("Specifiche KPI Esistenti")
    
    # Filter by Stabilimento for display
    selected_stab_for_filter_name = st.selectbox(
        "Filtra per Stabilimento:", 
        ["Tutti"] + list(stabilimento_options.keys()), 
        key='filter_stab_kpi_specs'
    )
    filter_stabilimento_id = None
    if selected_stab_for_filter_name != "Tutti":
        filter_stabilimento_id = stabilimento_options[selected_stab_for_filter_name]

    all_kpis_data = data_retriever.get_all_kpis_detailed(stabilimento_id=filter_stabilimento_id)

    if all_kpis_data:
        # Prepare data for display, including template name
        display_data = []
        for kpi_row_dict in all_kpis_data:
            # Fetch template name (similar logic to Tkinter)
            template_name_display = ""
            if kpi_row_dict.get("subgroup_id"):
                subgroup_details = data_retriever.get_kpi_subgroup_by_id_with_template_name(kpi_row_dict["subgroup_id"])
                if subgroup_details and subgroup_details.get("template_name"):
                    template_name_display = subgroup_details["template_name"]

            display_data.append({
                "ID": kpi_row_dict["id"],
                "Gruppo": kpi_row_dict["group_name"],
                "Sottogruppo": kpi_row_dict["subgroup_name"],
                "Indicatore": kpi_row_dict["indicator_name"],
                "Descrizione": kpi_row_dict["description"],
                "Tipo Calcolo": kpi_row_dict["calculation_type"],
                "Unità": kpi_row_dict["unit_of_measure"] or "",
                "Visibile (Globale)": "Sì" if kpi_row_dict["visible"] else "No",
                "Template SG": template_name_display,
            })
        
        st.dataframe(display_data, use_container_width=True)

        # --- Edit/Delete Actions ---
        st.subheader("Azioni")
        col_edit, col_delete = st.columns(2)
        with col_edit:
            edit_kpi_id = st.number_input("ID KPI da Modificare:", min_value=1, format="%d", key='edit_kpi_id_input')
            if st.button("Carica per Modifica"):
                kpi_data_full_dict = data_retriever.get_kpi_detailed_by_id(edit_kpi_id)
                if kpi_data_full_dict:
                    st.session_state.selected_kpi_spec_id = edit_kpi_id
                    st.session_state.kpi_edit_mode = True
                    # Populate form fields for editing
                    st.session_state.kpi_spec_group = kpi_data_full_dict['group_name']
                    # Need to reconstruct subgroup display name
                    subgroup_raw_name = kpi_data_full_dict['subgroup_name']
                    subgroup_details_for_template = data_retriever.get_kpi_subgroup_by_id_with_template_name(kpi_data_full_dict['subgroup_id'])
                    subgroup_display_name_for_edit = subgroup_raw_name
                    if subgroup_details_for_template and subgroup_details_for_template.get('template_name'):
                        subgroup_display_name_for_edit += f" (Tpl: {subgroup_details_for_template['template_name']})"
                    st.session_state.kpi_spec_subgroup = subgroup_display_name_for_edit
                    st.session_state.kpi_spec_indicator = kpi_data_full_dict['indicator_name']
                    st.session_state.kpi_spec_desc = kpi_data_full_dict['description']
                    st.session_state.kpi_spec_calc_type = kpi_data_full_dict['calculation_type']
                    st.session_state.kpi_spec_unit = kpi_data_full_dict['unit_of_measure']
                    st.session_state.kpi_spec_visible_global = kpi_data_full_dict['visible']

                    # Load stabilimento-specific visibility for editing
                    for stab_name, stab_id in stabilimento_options.items():
                        current_kpi_stab_visibility = kpi_visibility.get_kpi_stabilimento_visibility(edit_kpi_id, stab_id)
                        st.session_state[f"stab_chk_{stab_id}"] = current_kpi_stab_visibility

                    st.experimental_rerun()
                else:
                    st.error(f"KPI con ID {edit_kpi_id} non trovato.")

        with col_delete:
            delete_kpi_id = st.number_input("ID KPI da Eliminare:", min_value=1, format="%d", key='delete_kpi_id_input')
            if st.button("Elimina Specifica KPI"):
                if delete_kpi_id:
                    try:
                        # Fetch full details to get actual_indicator_id
                        kpi_spec_details = data_retriever.get_kpi_detailed_by_id(delete_kpi_id)
                        if kpi_spec_details and "actual_indicator_id" in kpi_spec_details:
                            actual_indicator_id_to_delete = kpi_spec_details["actual_indicator_id"]
                            kpi_indicators_manager.delete_kpi_indicator(actual_indicator_id_to_delete)
                            st.success(f"Specifica KPI con ID {delete_kpi_id} eliminata con successo!")
                            st.experimental_rerun()
                        else:
                            st.error(f"KPI con ID {delete_kpi_id} non trovato o dati incompleti.")
                    except Exception as e:
                        st.error(f"Errore nell'eliminare la specifica KPI: {e}")
                else:
                    st.warning("Inserisci un ID KPI valido per l'eliminazione.")

    else:
        st.info("Nessuna specifica KPI configurata.")
