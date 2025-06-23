import streamlit as st
import pandas as pd
import json
import datetime
import calendar
from pathlib import Path
import sqlite3
import sys
import subprocess
import shutil # For creating zip file
import sys
# Import your existing modules
import database_manager as db_manager
import data_retriever as dr
import export_manager # Assuming this module exists
from app_config import (
    CALC_TYPE_INCREMENTALE,
    CALC_TYPE_MEDIA,
    REPARTITION_LOGIC_ANNO,
    REPARTITION_LOGIC_MESE,
    REPARTITION_LOGIC_TRIMESTRE,
    REPARTITION_LOGIC_SETTIMANA,
    PROFILE_EVEN,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    PROFILE_MONTHLY_SINUSOIDAL,
    PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
    PROFILE_QUARTERLY_PROGRESSIVE,
    PROFILE_QUARTERLY_SINUSOIDAL,
    CSV_EXPORT_BASE_PATH,
    PERIOD_TYPES_RESULTS,
)


# --- Helper Function (from your Tkinter app) ---
def get_kpi_display_name(kpi_data_dict):  # Consistently expect a dictionary
    # Removed: if not kpi_data_dict: (because .get handles None for keys)
    # The .get() method with defaults, and the 'or' checks below,
    # handle cases where data might be missing or empty within the row (Series).
    try:
        # kpi_data_dict is now expected to be a dictionary
        g_name = kpi_data_dict.get("group_name", "N/G (No Group)")
        sg_name = kpi_data_dict.get("subgroup_name", "N/S (No Subgroup)")
        i_name = kpi_data_dict.get("indicator_name", "N/I (No Indicator)")

        # Handle cases where .get() might return None or an empty string from the data
        g_name = g_name or "N/G (Nome Gruppo Vuoto)"
        sg_name = sg_name or "N/S (Nome Sottogruppo Vuoto)"
        i_name = i_name or "N/I (Nome Indicatore Vuoto)"
        return f"{g_name} > {sg_name} > {i_name}"
    except Exception as ex_general:
        # st.error(f"DEBUG: Errore in get_kpi_display_name con dati: {kpi_data_dict}, Errore: {ex_general}") # Debug
        return "N/D (Errore Display Nome Imprevisto)"


# Make sure PERIOD_TYPES_RESULTS is defined, e.g.:
if "PERIOD_TYPES_RESULTS" not in globals():
    PERIOD_TYPES_RESULTS = ["Giorno", "Settimana", "Mese", "Trimestre"]


def get_kpi_display_name_st(kpi_data_row):  # Simplified version for Streamlit if needed
    if not kpi_data_row or not isinstance(kpi_data_row, dict):
        return "N/D (KPI Data Mancante)"
    g_name = kpi_data_row.get("group_name", "N/G")
    sg_name = kpi_data_row.get("subgroup_name", "N/S")
    i_name = kpi_data_row.get("indicator_name", "N/I")
    return f"{g_name} > {sg_name} > {i_name}"


# --- Streamlit Page Configuration ---
st.set_page_config(layout="wide", page_title="Gestione Target KPI", page_icon="🎯")

# --- Initialize Databases ---
try:
    db_manager.setup_databases()
except Exception as e:
    st.error(f"Errore critico durante il setup dei database: {e}")
    st.stop()

# --- Session State Initialization ---
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    # KPI Hierarchy Tab
    st.session_state.selected_group_id_hier = None
    st.session_state.selected_subgroup_id_hier = None
    st.session_state.selected_indicator_id_hier = None

    # KPI Templates Tab
    st.session_state.selected_template_id_tpl = None
    st.session_state.editing_definition_tpl = None # Stores definition dict for edit

    # KPI Specs Tab
    st.session_state.spec_selected_group_id = None
    st.session_state.spec_selected_subgroup_id = None
    st.session_state.spec_selected_indicator_actual_id = None # kpi_indicators.id
    st.session_state.current_editing_kpi_spec_id_specs = None # kpis.id

    # Master/Sub Link Tab
    st.session_state.ms_selected_kpi_spec_id_for_linking = None
    st.session_state.ms_sub_kpi_to_link_id = None
    st.session_state.ms_link_weight = 1.0

    # Stabilimenti Tab
    st.session_state.editing_stabilimento = None

    # Target Entry Tab - For Filter Widgets
    st.session_state.target_year_sb_filters = str(
        datetime.datetime.now().year
    )  # Initialize with default year
    st.session_state.target_stab_sb_filters = (
        None  # Initialize as None, user must select
    )

    st.session_state.kpi_target_inputs = {}
    st.session_state._master_sub_update_active_st = False

    # Results Tab
    st.session_state.results_year = str(datetime.datetime.now().year)
    st.session_state.results_stabilimento_id = None
    st.session_state.results_period_type = "Mese"
    st.session_state.results_target_number = 1
    st.session_state.results_group_id = None
    st.session_state.results_subgroup_id = None
    st.session_state.results_indicator_actual_id = None
    st.session_state.results_kpi_spec_id = None


# --- Constants for UI ---
DISTRIBUTION_PROFILE_OPTIONS = [
    PROFILE_EVEN,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    PROFILE_MONTHLY_SINUSOIDAL,
    PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
    PROFILE_QUARTERLY_PROGRESSIVE,
    PROFILE_QUARTERLY_SINUSOIDAL,
    "event_based_spikes_or_dips",
]
REPARTITION_LOGIC_OPTIONS = [
    REPARTITION_LOGIC_ANNO,
    REPARTITION_LOGIC_MESE,
    REPARTITION_LOGIC_TRIMESTRE,
    REPARTITION_LOGIC_SETTIMANA,
]
KPI_CALC_TYPE_OPTIONS = [CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA]
PERIOD_TYPES_RESULTS = ["Giorno", "Settimana", "Mese", "Trimestre"]

# --- Main Application ---
st.title("🎯 Gestione Target KPI (Streamlit Version)")

tab_titles = [
    "🎯 Inserimento Target",
    "🗂️ Gerarchia KPI",
    "📋 Template Indicatori",
    "⚙️ Specifiche KPI",
    "🔗 Link Master/Sub",
    "🏭 Stabilimenti",
    "📈 Risultati",
    "🌍 Dashboard Globale KPI",
    "📦 Esportazione",
]
(
    tab_target,
    tab_hierarchy,
    tab_templates,
    tab_specs,
    tab_links,
    tab_stabilimenti,
    tab_results,
    tab_global_dashboard,  # Add variable for the new dashboard tab
    tab_export,
) = st.tabs(tab_titles)

# --- 🏭 Gestione Stabilimenti ---
with tab_stabilimenti:
    st.header("Gestione Stabilimenti")

    col1_stab, col2_stab = st.columns([2, 1.5])

    with col1_stab:
        st.subheader("Elenco Stabilimenti")
        stabilimenti_data_raw = dr.get_all_stabilimenti()

        if stabilimenti_data_raw:
            df_stabilimenti = pd.DataFrame([dict(row) for row in stabilimenti_data_raw])
            st.session_state.df_stabilimenti_original_for_selection = (
                df_stabilimenti  # Store for reliable selection
            )

            if not df_stabilimenti.empty:
                df_stabilimenti_display = df_stabilimenti[
                    ["id", "name", "visible"]
                ].copy()
                df_stabilimenti_display["visible"] = df_stabilimenti_display[
                    "visible"
                ].apply(lambda x: "Sì" if bool(x) else "No")
                df_stabilimenti_display.rename(
                    columns={"id": "ID", "name": "Nome", "visible": "Visibile"},
                    inplace=True,
                )

                st.dataframe(
                    df_stabilimenti_display,
                    on_select="rerun",
                    selection_mode="single-row",
                    hide_index=True,
                    key="stabilimenti_df_selection_state",
                )

                selection_info = st.session_state.get("stabilimenti_df_selection_state")

                if selection_info and selection_info["selection"]["rows"]:
                    selected_df_index = selection_info["selection"]["rows"][0]

                    if (
                        "df_stabilimenti_original_for_selection" in st.session_state
                        and 0
                        <= selected_df_index
                        < len(st.session_state.df_stabilimenti_original_for_selection)
                    ):

                        selected_item_data = st.session_state.df_stabilimenti_original_for_selection.iloc[
                            selected_df_index
                        ].to_dict()
                        current_editing_stabilimento_data = st.session_state.get(
                            "editing_stabilimento"
                        )
                        current_editing_id = None  # Default to None
                        if isinstance(
                            current_editing_stabilimento_data, dict
                        ):  # Check if it's actually a dictionary
                            current_editing_id = current_editing_stabilimento_data.get(
                                "id"
                            )
                        if current_editing_id != selected_item_data["id"]:
                            st.session_state.editing_stabilimento = selected_item_data
                            # on_select="rerun" already triggers a rerun.
                    else:
                        if st.session_state.get("editing_stabilimento") is not None:
                            st.session_state.editing_stabilimento = (
                                None  # Rerun will clear form
                            )
                elif selection_info and not selection_info["selection"]["rows"]:
                    if st.session_state.get("editing_stabilimento") is not None:
                        st.session_state.editing_stabilimento = None
            else:
                st.info("Nessun stabilimento definito.")
                if "editing_stabilimento" in st.session_state:
                    st.session_state.editing_stabilimento = None
        else:
            st.info("Nessun stabilimento definito.")
            if "editing_stabilimento" in st.session_state:
                st.session_state.editing_stabilimento = None

    with col2_stab:
        current_editing_data_stab = st.session_state.get("editing_stabilimento")

        if current_editing_data_stab:
            st.subheader(f"Modifica Stabilimento: {current_editing_data_stab['name']}")
            form_key_stab = f"stabilimento_form_edit_{current_editing_data_stab['id']}"
            button_text_stab = "Salva Modifiche"
            initial_name_stab = current_editing_data_stab["name"]
            initial_visible_stab = bool(current_editing_data_stab["visible"])
            editing_id_stab = current_editing_data_stab["id"]
        else:
            st.subheader("Aggiungi Nuovo Stabilimento")
            form_key_stab = "stabilimento_form_new"  # Reset key for new form
            button_text_stab = "Aggiungi Stabilimento"
            initial_name_stab = ""
            initial_visible_stab = True
            editing_id_stab = None

        # Use a consistent key for the form itself, but inputs inside can be dynamic if needed
        with st.form(key="stabilimento_master_form", clear_on_submit=False):
            stab_name_input = st.text_input(
                "Nome Stabilimento",
                value=initial_name_stab,  # This will update when current_editing_data_stab changes
                key="stab_name_input_field",  # Consistent key for the input field
            )
            stab_visible_input = st.checkbox(
                "Visibile per Inserimento Target",
                value=initial_visible_stab,  # This will update
                key="stab_visible_input_field",  # Consistent key for the input field
            )

            submitted_stabilimento_form = st.form_submit_button(button_text_stab)

            if submitted_stabilimento_form:
                # Read current values from input widgets
                actual_stab_name = st.session_state.stab_name_input_field
                actual_stab_visible = st.session_state.stab_visible_input_field

                if not actual_stab_name.strip():
                    st.error("Il nome dello stabilimento è obbligatorio.")
                else:
                    try:
                        if (
                            editing_id_stab is not None
                        ):  # In "Edit" mode (derived from current_editing_data_stab)
                            db_manager.update_stabilimento(
                                editing_id_stab,
                                actual_stab_name.strip(),
                                actual_stab_visible,
                            )
                            st.success(
                                f"Stabilimento '{actual_stab_name.strip()}' aggiornato."
                            )
                        else:  # "Add" mode
                            db_manager.add_stabilimento(
                                actual_stab_name.strip(), actual_stab_visible
                            )
                            st.success(
                                f"Stabilimento '{actual_stab_name.strip()}' aggiunto."
                            )

                        st.session_state.editing_stabilimento = (
                            None  # Reset editing state
                        )
                        # No need to touch stabilimenti_df_selection_state here
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(
                            f"Errore: Uno stabilimento con nome '{actual_stab_name.strip()}' esiste già."
                        )
                    except Exception as e:
                        st.error(f"Errore durante il salvataggio: {e}")
                        import traceback

                        st.error(traceback.format_exc())

        if current_editing_data_stab:  # Only show "Clear" if editing
            if st.button(
                "Pulisci Form / Nuovo Stabilimento", key="clear_stab_form_button"
            ):
                st.session_state.editing_stabilimento = None
                # Clear the dataframe selection state as well
                if "stabilimenti_df_selection_state" in st.session_state:
                    st.session_state.stabilimenti_df_selection_state = {
                        "selection": {"rows": []}
                    }
                st.rerun()

# --- 🗂️ Gestione Gerarchia KPI ---
with tab_hierarchy:
    st.header("Gestione Gerarchia KPI")

    groups = dr.get_kpi_groups()
    groups_map = {g["name"]: g["id"] for g in groups}
    group_names = [""] + list(groups_map.keys())

    col1_hier, col2_hier, col3_hier = st.columns(3)

    with col1_hier:
        st.subheader("Gruppi KPI")
        selected_group_name_hier = st.selectbox(
            "Seleziona Gruppo", group_names, index=0, key="sb_group_hier",
            on_change=lambda: setattr(st.session_state, "selected_subgroup_id_hier", None) or setattr(st.session_state, "selected_indicator_id_hier", None)
        )
        if selected_group_name_hier:
            st.session_state.selected_group_id_hier = groups_map[selected_group_name_hier]
        else:
            st.session_state.selected_group_id_hier = None


        with st.expander("Gestisci Gruppi"):
            with st.form("group_form_hier", clear_on_submit=True):
                new_group_name = st.text_input("Nome Nuovo Gruppo")
                add_group_submitted = st.form_submit_button("Aggiungi Gruppo")
                if add_group_submitted and new_group_name:
                    try:
                        db_manager.add_kpi_group(new_group_name)
                        st.success(f"Gruppo '{new_group_name}' aggiunto.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore aggiunta gruppo: {e}")

            if st.session_state.selected_group_id_hier:
                st.markdown("---")
                st.write(f"**Modifica/Elimina: {selected_group_name_hier}**")
                with st.form(f"edit_group_form_{st.session_state.selected_group_id_hier}"):
                    edited_group_name = st.text_input("Nuovo Nome", value=selected_group_name_hier)
                    update_group_submitted = st.form_submit_button("Modifica Nome")
                    if update_group_submitted and edited_group_name and edited_group_name != selected_group_name_hier:
                        try:
                            db_manager.update_kpi_group(st.session_state.selected_group_id_hier, edited_group_name)
                            st.success(f"Gruppo rinominato in '{edited_group_name}'.")
                            st.session_state.selected_group_id_hier = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore modifica gruppo: {e}")

                if st.button("Elimina Gruppo", type="primary", key=f"del_group_{st.session_state.selected_group_id_hier}"):
                    # Add confirmation dialog here in a real app
                    try:
                        db_manager.delete_kpi_group(st.session_state.selected_group_id_hier)
                        st.success(f"Gruppo '{selected_group_name_hier}' eliminato.")
                        st.session_state.selected_group_id_hier = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore eliminazione gruppo: {e}")
    subgroups = []
    current_subgroup_details_hier = None
    with col2_hier:
        st.subheader("Sottogruppi KPI")
        subgroups_map = {}
        subgroup_display_names = [""]
        if st.session_state.selected_group_id_hier:
            subgroups = dr.get_kpi_subgroups_by_group_revised(st.session_state.selected_group_id_hier)
            for sg in subgroups:
                display_name = sg["name"] + (f" (Tpl: {sg['template_name']})" if sg.get("template_name") else "")
                subgroups_map[display_name] = sg["id"]
                subgroup_display_names.append(display_name)

        selected_subgroup_display_name_hier = st.selectbox(
            "Seleziona Sottogruppo", subgroup_display_names, index=0, key="sb_subgroup_hier",
            disabled=not bool(st.session_state.selected_group_id_hier),
            on_change=lambda: setattr(st.session_state, "selected_indicator_id_hier", None)
        )
        if selected_subgroup_display_name_hier:
            st.session_state.selected_subgroup_id_hier = subgroups_map[selected_subgroup_display_name_hier]
            if subgroups: # Ensure subgroups list is populated
                 current_subgroup_details_hier = next((sg for sg in subgroups if sg["id"] == st.session_state.selected_subgroup_id_hier), None)
        else:
            st.session_state.selected_subgroup_id_hier = None
            current_subgroup_details_hier = None


        with st.expander("Gestisci Sottogruppi"):
            if st.session_state.selected_group_id_hier:
                templates = dr.get_kpi_indicator_templates()
                templates_map_hier = {"(Nessuno)": None}
                templates_map_hier.update({tpl["name"]: tpl["id"] for tpl in templates})

                with st.form("subgroup_form_hier", clear_on_submit=True):
                    new_subgroup_name = st.text_input("Nome Nuovo Sottogruppo")
                    selected_template_name_for_new_sg = st.selectbox("Template", list(templates_map_hier.keys()))
                    add_subgroup_submitted = st.form_submit_button("Aggiungi Sottogruppo")
                    if add_subgroup_submitted and new_subgroup_name:
                        try:
                            template_id_for_new_sg = templates_map_hier[selected_template_name_for_new_sg]
                            db_manager.add_kpi_subgroup(new_subgroup_name, st.session_state.selected_group_id_hier, template_id_for_new_sg)
                            st.success(f"Sottogruppo '{new_subgroup_name}' aggiunto.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore aggiunta sottogruppo: {e}")

                if current_subgroup_details_hier:
                    st.markdown("---")
                    st.write(f"**Modifica/Elimina: {current_subgroup_details_hier['name']}**")
                    with st.form(f"edit_subgroup_form_{current_subgroup_details_hier['id']}"):
                        edited_subgroup_name = st.text_input("Nuovo Nome", value=current_subgroup_details_hier["name"])
                        current_tpl_id = current_subgroup_details_hier.get("indicator_template_id")
                        current_tpl_name_for_edit = next((name for name, id_val in templates_map_hier.items() if id_val == current_tpl_id), "(Nessuno)")
                        edited_template_name_for_sg = st.selectbox("Nuovo Template", list(templates_map_hier.keys()), index=list(templates_map_hier.keys()).index(current_tpl_name_for_edit))
                        update_subgroup_submitted = st.form_submit_button("Modifica Sottogruppo")

                        if update_subgroup_submitted:
                            new_template_id_for_edit = templates_map_hier[edited_template_name_for_sg]
                            if edited_subgroup_name != current_subgroup_details_hier["name"] or new_template_id_for_edit != current_subgroup_details_hier.get("indicator_template_id"):
                                try:
                                    db_manager.update_kpi_subgroup(current_subgroup_details_hier["id"], edited_subgroup_name, st.session_state.selected_group_id_hier, new_template_id_for_edit)
                                    st.success(f"Sottogruppo '{edited_subgroup_name}' aggiornato.")
                                    st.session_state.selected_subgroup_id_hier = None
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Errore modifica sottogruppo: {e}")
                    if st.button("Elimina Sottogruppo", type="primary", key=f"del_subg_{current_subgroup_details_hier['id']}"):
                        try:
                            db_manager.delete_kpi_subgroup(current_subgroup_details_hier["id"])
                            st.success(f"Sottogruppo '{current_subgroup_details_hier['name']}' eliminato.")
                            st.session_state.selected_subgroup_id_hier = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore eliminazione sottogruppo: {e}")
            else:
                st.info("Seleziona un gruppo.")

    with col3_hier:
        st.subheader("Indicatori KPI")
        indicators_map = {}
        indicator_names = [""]
        is_templated_subgroup = False

        if current_subgroup_details_hier:
            is_templated_subgroup = current_subgroup_details_hier.get("indicator_template_id") is not None
            indicators = dr.get_kpi_indicators_by_subgroup(current_subgroup_details_hier["id"])
            for ind in indicators:
                indicators_map[ind["name"]] = ind["id"]
                indicator_names.append(ind["name"])

        selected_indicator_name_hier = st.selectbox(
            "Seleziona Indicatore", indicator_names, index=0, key="sb_indicator_hier",
            disabled=not bool(st.session_state.selected_subgroup_id_hier)
        )
        if selected_indicator_name_hier:
            st.session_state.selected_indicator_id_hier = indicators_map[selected_indicator_name_hier]
        else:
            st.session_state.selected_indicator_id_hier = None

        with st.expander("Gestisci Indicatori"):
            if st.session_state.selected_subgroup_id_hier:
                if is_templated_subgroup:
                    st.info("Indicatori gestiti dal template.")
                else:
                    with st.form("indicator_form_hier", clear_on_submit=True):
                        new_indicator_name = st.text_input("Nome Nuovo Indicatore")
                        add_indicator_submitted = st.form_submit_button("Aggiungi Indicatore")
                        if add_indicator_submitted and new_indicator_name:
                            try:
                                db_manager.add_kpi_indicator(new_indicator_name, st.session_state.selected_subgroup_id_hier)
                                st.success(f"Indicatore '{new_indicator_name}' aggiunto.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore aggiunta indicatore: {e}")

                    if st.session_state.selected_indicator_id_hier:
                        st.markdown("---")
                        st.write(f"**Modifica/Elimina: {selected_indicator_name_hier}**")
                        with st.form(f"edit_indicator_form_{st.session_state.selected_indicator_id_hier}"):
                            edited_indicator_name = st.text_input("Nuovo Nome", value=selected_indicator_name_hier)
                            update_indicator_submitted = st.form_submit_button("Modifica Nome")
                            if update_indicator_submitted and edited_indicator_name and edited_indicator_name != selected_indicator_name_hier:
                                try:
                                    db_manager.update_kpi_indicator(st.session_state.selected_indicator_id_hier, edited_indicator_name, st.session_state.selected_subgroup_id_hier)
                                    st.success(f"Indicatore rinominato in '{edited_indicator_name}'.")
                                    st.session_state.selected_indicator_id_hier = None
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Errore modifica indicatore: {e}")
                        if st.button("Elimina Indicatore", type="primary", key=f"del_ind_{st.session_state.selected_indicator_id_hier}"):
                            try:
                                db_manager.delete_kpi_indicator(st.session_state.selected_indicator_id_hier)
                                st.success(f"Indicatore '{selected_indicator_name_hier}' eliminato.")
                                st.session_state.selected_indicator_id_hier = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore eliminazione indicatore: {e}")
            else:
                st.info("Seleziona un sottogruppo.")


# --- 📋 Gestione Template Indicatori ---
with tab_templates:
    st.header("Gestione Template Indicatori KPI")
    col1_tpl, col2_tpl = st.columns([1, 2])

    templates = dr.get_kpi_indicator_templates()
    templates_map = {tpl["name"]: tpl["id"] for tpl in templates}
    template_names = [""] + list(templates_map.keys())

    with col1_tpl:
        st.subheader("Elenco Template")
        selected_template_name_tpl = st.selectbox(
            "Seleziona Template", template_names, index=0, key="sb_template_tpl"
        )
        if selected_template_name_tpl:
            st.session_state.selected_template_id_tpl = templates_map[selected_template_name_tpl]
            current_template_details = dr.get_kpi_indicator_template_by_id(st.session_state.selected_template_id_tpl)
        else:
            st.session_state.selected_template_id_tpl = None
            current_template_details = None

        with st.expander("Gestisci Template", expanded=True):
            with st.form("template_form_tpl", clear_on_submit=False): # Keep values on resubmit for edit
                tpl_form_key_prefix = f"tpl_form_{st.session_state.selected_template_id_tpl}_" if st.session_state.selected_template_id_tpl else "tpl_form_new_"
                
                tpl_name = st.text_input("Nome Template", value=current_template_details["name"] if current_template_details else "", key=tpl_form_key_prefix+"name")
                tpl_desc = st.text_area("Descrizione", value=current_template_details["description"] if current_template_details else "", height=100, key=tpl_form_key_prefix+"desc")
                
                col_add_tpl, col_save_tpl = st.columns(2)
                with col_add_tpl:
                    add_tpl_submitted = st.form_submit_button("Aggiungi Nuovo Template")
                with col_save_tpl:
                    save_tpl_submitted = st.form_submit_button("Salva Modifiche Template", disabled=not st.session_state.selected_template_id_tpl)

                if add_tpl_submitted and tpl_name:
                    try:
                        db_manager.add_kpi_indicator_template(tpl_name, tpl_desc)
                        st.success(f"Template '{tpl_name}' aggiunto.")
                        st.session_state.selected_template_id_tpl = None # Clear selection to allow reselect
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore aggiunta template: {e}")
                
                if save_tpl_submitted and tpl_name and st.session_state.selected_template_id_tpl:
                    try:
                        db_manager.update_kpi_indicator_template(st.session_state.selected_template_id_tpl, tpl_name, tpl_desc)
                        st.success(f"Template '{tpl_name}' aggiornato.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore modifica template: {e}")
            
            if st.session_state.selected_template_id_tpl:
                if st.button("Elimina Template Selezionato", type="primary", key=f"del_tpl_{st.session_state.selected_template_id_tpl}"):
                    try:
                        db_manager.delete_kpi_indicator_template(st.session_state.selected_template_id_tpl)
                        st.success(f"Template '{selected_template_name_tpl}' eliminato.")
                        st.session_state.selected_template_id_tpl = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore eliminazione template: {e}")
        
        if st.button("Pulisci selezione template", key="clear_tpl_selection"):
            st.session_state.selected_template_id_tpl = None
            st.rerun()


    with col2_tpl:
        st.subheader("Indicatori Definiti nel Template")
        if st.session_state.selected_template_id_tpl:
            definitions = dr.get_template_defined_indicators(st.session_state.selected_template_id_tpl)
            if definitions:
                df_defs = pd.DataFrame([dict(row) for row in definitions])
                st.dataframe(df_defs[["id", "indicator_name_in_template", "default_calculation_type", "default_unit_of_measure", "default_visible"]], hide_index=True)

                selected_def_id_for_action = st.selectbox("Seleziona definizione per Modifica/Elimina", options=[""] + [d["id"] for d in definitions], format_func=lambda x: next((d["indicator_name_in_template"] for d in definitions if d["id"] == x), "Seleziona...") if x else "Seleziona...")
                
                if selected_def_id_for_action:
                    st.session_state.editing_definition_tpl = dr.get_template_indicator_definition_by_id(selected_def_id_for_action)
                    if st.button(f"Elimina Definizione Selezionata ({st.session_state.editing_definition_tpl['indicator_name_in_template']})", type="secondary", key=f"del_def_{selected_def_id_for_action}"):
                        try:
                            db_manager.remove_indicator_definition_from_template(selected_def_id_for_action)
                            st.success("Definizione eliminata.")
                            st.session_state.editing_definition_tpl = None
                            st.rerun()
                        except Exception as e:
                             st.error(f"Errore eliminazione definizione: {e}")
                else:
                    st.session_state.editing_definition_tpl = None


            else:
                st.info("Nessun indicatore definito per questo template.")

            st.markdown("---")
            action_label = "Modifica Definizione Indicatore" if st.session_state.editing_definition_tpl else "Aggiungi Nuova Definizione Indicatore"
            st.subheader(action_label)

            def_data = st.session_state.editing_definition_tpl
            with st.form("definition_form_tpl", clear_on_submit=not bool(def_data) ): # Clear if adding new
                def_form_key_prefix = f"def_form_{def_data['id']}_" if def_data else "def_form_new_"

                def_name = st.text_input("Nome Indicatore nel Template", value=def_data["indicator_name_in_template"] if def_data else "", key=def_form_key_prefix+"name")
                def_desc = st.text_area("Descrizione Default", value=def_data["default_description"] if def_data else "", height=70, key=def_form_key_prefix+"desc")
                def_calc_type = st.selectbox("Tipo Calcolo Default", KPI_CALC_TYPE_OPTIONS, index=KPI_CALC_TYPE_OPTIONS.index(def_data["default_calculation_type"]) if def_data and def_data["default_calculation_type"] in KPI_CALC_TYPE_OPTIONS else 0, key=def_form_key_prefix+"calc")
                def_unit = st.text_input("Unità Misura Default", value=def_data["default_unit_of_measure"] if def_data else "", key=def_form_key_prefix+"unit")
                def_visible = st.checkbox("Visibile Default", value=bool(def_data["default_visible"]) if def_data else True, key=def_form_key_prefix+"vis")

                submit_def_button = st.form_submit_button("Salva Definizione" if def_data else "Aggiungi Definizione")

                if submit_def_button and def_name:
                    try:
                        if def_data: # Editing existing definition
                            db_manager.update_indicator_definition_in_template(def_data["id"], def_name, def_calc_type, def_unit, def_visible, def_desc)
                            st.success(f"Definizione '{def_name}' aggiornata.")
                        else: # Adding new definition
                            db_manager.add_indicator_definition_to_template(st.session_state.selected_template_id_tpl, def_name, def_calc_type, def_unit, def_visible, def_desc)
                            st.success(f"Definizione '{def_name}' aggiunta al template.")
                        st.session_state.editing_definition_tpl = None # Clear editing state
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore salvataggio definizione: {e}")
            if def_data:
                if st.button("Pulisci / Nuova Definizione"):
                    st.session_state.editing_definition_tpl = None
                    st.rerun()
        else:
            st.info("Seleziona un template per visualizzare e gestire le sue definizioni.")


# --- ⚙️ Gestione Specifiche KPI ---
with tab_specs:
    st.header("Gestione Specifiche KPI (Definizione Proprietà)")

    # --- Filters for selecting an Indicator ---
    groups_spec = dr.get_kpi_groups()
    groups_map_spec = {g["name"]: g["id"] for g in groups_spec}
    group_names_spec = [""] + list(groups_map_spec.keys())

    col_g_spec, col_sg_spec, col_i_spec = st.columns(3)
    with col_g_spec:
        selected_group_name_spec = st.selectbox("Gruppo", group_names_spec, key="spec_group_sel", on_change=lambda: setattr(st.session_state, "spec_selected_subgroup_id", None) or setattr(st.session_state, "spec_selected_indicator_actual_id", None))
        if selected_group_name_spec:
            st.session_state.spec_selected_group_id = groups_map_spec[selected_group_name_spec]
        else:
            st.session_state.spec_selected_group_id = None

    subgroups_spec_list = []
    subgroups_map_spec = {}
    subgroup_names_spec = [""]
    if st.session_state.spec_selected_group_id:
        subgroups_spec_list = dr.get_kpi_subgroups_by_group_revised(st.session_state.spec_selected_group_id)
        for sg in subgroups_spec_list:
            subgroups_map_spec[sg["name"]] = sg["id"] # Use raw name for mapping
            subgroup_names_spec.append(sg["name"]) # Display raw name

    with col_sg_spec:
        selected_subgroup_name_spec = st.selectbox("Sottogruppo", subgroup_names_spec, key="spec_subgroup_sel", disabled=not st.session_state.spec_selected_group_id, on_change=lambda: setattr(st.session_state, "spec_selected_indicator_actual_id", None))
        if selected_subgroup_name_spec:
            st.session_state.spec_selected_subgroup_id = subgroups_map_spec[selected_subgroup_name_spec]
        else:
            st.session_state.spec_selected_subgroup_id = None

    indicators_spec_list = []
    indicators_map_spec = {} # Maps indicator name to its actual_indicator_id (kpi_indicators.id)
    indicator_names_spec = [""]
    if st.session_state.spec_selected_subgroup_id:
        indicators_spec_list = dr.get_kpi_indicators_by_subgroup(st.session_state.spec_selected_subgroup_id)
        for ind in indicators_spec_list:
            indicators_map_spec[ind["name"]] = ind["id"]
            indicator_names_spec.append(ind["name"])

    with col_i_spec:
        selected_indicator_name_spec = st.selectbox("Indicatore", indicator_names_spec, key="spec_indicator_sel", disabled=not st.session_state.spec_selected_subgroup_id)
        if selected_indicator_name_spec:
            st.session_state.spec_selected_indicator_actual_id = indicators_map_spec[selected_indicator_name_spec]
        else:
            st.session_state.spec_selected_indicator_actual_id = None

    st.markdown("---")

    # --- Form for KPI Spec ---
    current_kpi_spec_data = None
    kpi_spec_id_for_form = None

    if st.session_state.spec_selected_indicator_actual_id:
        # Check if a kpi_spec (kpis table entry) exists for this kpi_indicator.id
        # This requires a way to get kpis.id from kpi_indicators.id
        # Let's assume we search all kpi_specs for the one matching indicator_id
        all_specs_for_lookup = dr.get_all_kpis_detailed() # Not ideal for performance on large DBs
        found_spec = next((s for s in all_specs_for_lookup if s["actual_indicator_id"] == st.session_state.spec_selected_indicator_actual_id), None)

        if found_spec:
            kpi_spec_id_for_form = found_spec["id"] # This is kpis.id
            current_kpi_spec_data = found_spec # Use the detailed data which includes calc_type etc.
            st.session_state.current_editing_kpi_spec_id_specs = kpi_spec_id_for_form

    # Display indicator name for context
    if selected_indicator_name_spec and selected_subgroup_name_spec and selected_group_name_spec:
        st.subheader(f"Specifica per: {selected_group_name_spec} > {selected_subgroup_name_spec} > {selected_indicator_name_spec}")
    elif st.session_state.current_editing_kpi_spec_id_specs and current_kpi_spec_data: # Loaded from table
        st.subheader(f"Modifica Specifica per: {get_kpi_display_name(current_kpi_spec_data)}")

    with st.form("kpi_spec_form", clear_on_submit=False): # Keep data for edits
        spec_desc = st.text_area("Descrizione Specifica", value=current_kpi_spec_data["description"] if current_kpi_spec_data else "")
        spec_calc_type = st.selectbox("Tipo Calcolo", KPI_CALC_TYPE_OPTIONS, 
                                      index=KPI_CALC_TYPE_OPTIONS.index(current_kpi_spec_data["calculation_type"]) if current_kpi_spec_data and current_kpi_spec_data["calculation_type"] in KPI_CALC_TYPE_OPTIONS else 0)
        spec_unit = st.text_input("Unità di Misura", value=current_kpi_spec_data["unit_of_measure"] if current_kpi_spec_data else "")
        spec_visible = st.checkbox("Visibile per Target/Risultati", value=bool(current_kpi_spec_data["visible"]) if current_kpi_spec_data else True)

        submit_spec_button = st.form_submit_button("Salva Specifiche KPI")

        if submit_spec_button:
            if not st.session_state.spec_selected_indicator_actual_id and not st.session_state.current_editing_kpi_spec_id_specs :
                st.error("Seleziona un indicatore dalla gerarchia prima di salvare le specifiche.")
            else:
                try:
                    indicator_id_to_use = st.session_state.spec_selected_indicator_actual_id
                    if st.session_state.current_editing_kpi_spec_id_specs and current_kpi_spec_data:
                        indicator_id_to_use = current_kpi_spec_data["actual_indicator_id"] # Use the one from loaded spec

                    if kpi_spec_id_for_form or st.session_state.current_editing_kpi_spec_id_specs: # Editing existing
                        spec_id_to_update = kpi_spec_id_for_form or st.session_state.current_editing_kpi_spec_id_specs
                        db_manager.update_kpi_spec(spec_id_to_update, indicator_id_to_use, spec_desc, spec_calc_type, spec_unit, spec_visible)
                        st.success(f"Specifiche KPI aggiornate.")
                    else: # Adding new
                        db_manager.add_kpi_spec(indicator_id_to_use, spec_desc, spec_calc_type, spec_unit, spec_visible)
                        st.success(f"Specifiche KPI aggiunte.")

                    st.session_state.current_editing_kpi_spec_id_specs = None # Clear editing state
                    # st.session_state.spec_selected_indicator_actual_id = None # Optionally clear selection
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore durante il salvataggio delle specifiche: {e}")
                    import traceback
                    st.error(traceback.format_exc())

    if st.session_state.current_editing_kpi_spec_id_specs or st.session_state.spec_selected_indicator_actual_id :
        if st.button("Pulisci selezione / Nuova Specifica", key="clear_spec_form_button"):
            st.session_state.spec_selected_group_id = None
            st.session_state.spec_selected_subgroup_id = None
            st.session_state.spec_selected_indicator_actual_id = None
            st.session_state.current_editing_kpi_spec_id_specs = None
            st.rerun()

    st.markdown("---")
    st.subheader("Elenco Specifiche KPI Esistenti")
    all_kpi_specs_data = dr.get_all_kpis_detailed()
    if all_kpi_specs_data:
        df_all_specs = pd.DataFrame([dict(row) for row in all_kpi_specs_data]) #
        df_all_specs["Nome Completo KPI"] = df_all_specs.apply(
            lambda row_series: get_kpi_display_name(row_series.to_dict()), axis=1
        )

        # Select relevant columns for display
        cols_to_display = ["id", "Nome Completo KPI", "description", "calculation_type", "unit_of_measure", "visible"]
        df_display_specs = df_all_specs[cols_to_display].rename(columns={
            "id": "ID Spec", "description": "Descrizione", "calculation_type": "Tipo Calcolo",
            "unit_of_measure": "Unità", "visible": "Visibile"
        })
        df_display_specs["Visibile"] = df_display_specs["Visibile"].apply(lambda x: "Sì" if x else "No")

        selected_spec_from_table = st.dataframe(df_display_specs, hide_index=True, on_select="rerun", selection_mode="single-row", key="spec_table_selection")

        spec_table_selection_state = st.session_state.get("spec_table_selection")
        if spec_table_selection_state and spec_table_selection_state["selection"]["rows"]:
            selected_idx = spec_table_selection_state["selection"]["rows"][0]
            if 0 <= selected_idx < len(df_all_specs):
                spec_id_from_table = df_all_specs.iloc[selected_idx]["id"]
                st.session_state.current_editing_kpi_spec_id_specs = spec_id_from_table
                # Clear hierarchical selections as we are loading from table
                st.session_state.spec_selected_group_id = None
                st.session_state.spec_selected_subgroup_id = None
                st.session_state.spec_selected_indicator_actual_id = None
                st.rerun() # Rerun to reload the form with this spec's data

    else:
        st.info("Nessuna specifica KPI definita.")


# --- 🔗 Gestione Link Master/Sub ---
with tab_links:
    st.header("Gestione Link Master/Sub KPI")

    # --- Data Loading and Mapping ---
    all_kpis_for_link_raw = dr.get_all_kpis_detailed(only_visible=False)
    kpi_spec_map_link = {} # This will store {kpi_spec_id: display_name}

    # st.write("--- DEBUG: Raw data from get_all_kpis_detailed (Link Tab) ---") # Optional Debug
    if all_kpis_for_link_raw:
        valid_kpis_count = 0
        for i, row_obj in enumerate(all_kpis_for_link_raw):
            # Detailed check for each row
            if row_obj and row_obj.keys() and "id" in row_obj.keys() and row_obj["id"] is not None:
                try:
                    # Ensure all necessary keys for get_kpi_display_name exist
                    kpi_dict_for_display = dict(row_obj)
                    required_keys = ["group_name", "subgroup_name", "indicator_name"]
                    if all(key in kpi_dict_for_display for key in required_keys):
                        display_name = get_kpi_display_name(kpi_dict_for_display)
                        kpi_spec_map_link[row_obj["id"]] = display_name
                        valid_kpis_count += 1
                        # st.write(f"DEBUG: Added to map - ID: {row_obj['id']}, Name: {display_name}") # Optional Debug
                    else:
                        st.warning(f"Skipping KPI (ID: {row_obj.get('id', 'N/A')}) due to missing name components for display (row: {dict(row_obj)}).")
                except Exception as e_display_name:
                    st.warning(f"Skipping KPI (ID: {row_obj.get('id', 'N/A')}) due to error in get_kpi_display_name: {e_display_name} (row: {dict(row_obj)})")
            else:
                # This is where your "Skipping invalid KPI data" warning comes from
                st.warning(f"Skipping invalid KPI data from database (missing/NULL ID or malformed row): {row_obj}")
        # st.write(f"DEBUG: Total valid KPIs mapped for dropdown: {valid_kpis_count}") # Optional Debug
    else:
        st.info("Nessun dato KPI recuperato dal database per la gestione dei link.")

    kpi_spec_ids_link_options = [""] + sorted(list(kpi_spec_map_link.keys()), key=lambda x: kpi_spec_map_link.get(x, str(x)))


    def kpi_spec_display_func_link(kpi_id_val):
        if not kpi_id_val:
            return "Seleziona KPI..."
        return kpi_spec_map_link.get(kpi_id_val, f"ID: {kpi_id_val} (Nome non Disponibile)")

    # --- Session State Initialization for this tab's widgets ---
    if "ms_main_kpi_selectbox_key" not in st.session_state: # Key for the main selectbox widget
        st.session_state.ms_main_kpi_selectbox_key = "" # Default to empty selection to show placeholder

    # --- KPI Selection ---
    st.subheader("Seleziona KPI per Gestire Link")
    
    try:
        # Use the widget's key to get its current value for setting the index
        current_main_kpi_idx = kpi_spec_ids_link_options.index(st.session_state.ms_main_kpi_selectbox_key)
    except ValueError:
        current_main_kpi_idx = 0 # Default to "Seleziona KPI..." if current value not in options

    selected_kpi_id_from_widget = st.selectbox(
        "KPI Principale",
        options=kpi_spec_ids_link_options,
        index=current_main_kpi_idx,
        format_func=kpi_spec_display_func_link,
        key="ms_main_kpi_selectbox_key" # This key stores the selected ID
    )
    # Use selected_kpi_id_from_widget for logic within this run
    # st.session_state.ms_selected_kpi_spec_id_for_linking can still be used if preferred for other logic access.
    st.session_state.ms_selected_kpi_spec_id_for_linking = selected_kpi_id_from_widget


    # --- Display KPI Role and Links ---
    if selected_kpi_id_from_widget: # Use the value directly from the selectbox for the current run
        kpi_id_current = selected_kpi_id_from_widget
        role_details = dr.get_kpi_role_details(kpi_id_current)

        st.write(f"**KPI Selezionato:** {kpi_spec_map_link.get(kpi_id_current)}")
        st.write(f"**Ruolo Attuale:** {role_details['role'].upper() if role_details['role'] else 'Nessuno'}")

        sub_kpi_links_with_weights_display = [] # Define here for broader scope
        if role_details["role"] == "master":
            st.markdown("#### Gestisce i seguenti Sub-KPI:")
            if role_details.get("related_kpis"):
                with sqlite3.connect(db_manager.DB_KPIS) as conn_weights_display:
                    conn_weights_display.row_factory = sqlite3.Row
                    for sub_id_raw_display in role_details["related_kpis"]:
                        link_row_display = conn_weights_display.execute(
                            "SELECT sub_kpi_spec_id, distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?",
                            (kpi_id_current, sub_id_raw_display)
                        ).fetchone()
                        if link_row_display and link_row_display["sub_kpi_spec_id"] is not None: # Ensure sub_id is valid
                            sub_kpi_links_with_weights_display.append({
                                "sub_kpi_spec_id": link_row_display["sub_kpi_spec_id"],
                                "name": kpi_spec_map_link.get(link_row_display["sub_kpi_spec_id"], f"ID: {link_row_display['sub_kpi_spec_id']}"),
                                "weight": link_row_display["distribution_weight"]
                            })
            if sub_kpi_links_with_weights_display:
                df_subs_display = pd.DataFrame(sub_kpi_links_with_weights_display)
                st.dataframe(df_subs_display[["sub_kpi_spec_id", "name", "weight"]].rename(columns={"sub_kpi_spec_id": "ID SubKPI", "name": "Nome SubKPI", "weight": "Peso Distribuzione"}), hide_index=True, use_container_width=True)
            else:
                st.info("Nessun Sub-KPI attualmente collegato a questo Master.")

        elif role_details["role"] == "sub" and role_details.get("master_id"):
            master_id_display = role_details["master_id"]
            weight_display = 1.0
            with sqlite3.connect(db_manager.DB_KPIS) as conn_weights_sub_display:
                conn_weights_sub_display.row_factory = sqlite3.Row
                link_row_sub_display = conn_weights_sub_display.execute("SELECT distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?", (master_id_display, kpi_id_current)).fetchone()
                if link_row_sub_display: weight_display = link_row_sub_display["distribution_weight"]
            st.markdown(f"#### È un Sub-KPI di: **{kpi_spec_map_link.get(master_id_display, f'ID: {master_id_display}')}** (Peso: {weight_display})")

        st.markdown("---")
        st.subheader("Azioni Link")
        link_col1, link_col2, link_col3 = st.columns([1.5, 1.5, 1.5])

        with link_col1:
            with st.form("link_sub_form", clear_on_submit=True):
                st.markdown("**Collega un Sub-KPI a questo KPI (Master):**")
                available_subs_options_map = {
                    sub_id: kpi_spec_map_link.get(sub_id, f"ID: {sub_id}")
                    for sub_id in kpi_spec_map_link.keys() # Iterate over valid, mapped KPIs
                    if sub_id != kpi_id_current and \
                        sub_id not in (s["sub_kpi_spec_id"] for s in sub_kpi_links_with_weights_display) and \
                        dr.get_master_kpi_for_sub(sub_id) is None and \
                        not (dr.get_kpi_role_details(sub_id)['role'] == 'master' and kpi_id_current in dr.get_sub_kpis_for_master(sub_id))
                }
                available_subs_ids_for_selectbox = [""] + list(available_subs_options_map.keys())
                
                selected_sub_to_link_id_widget = st.selectbox(
                    "Sub-KPI da Collegare", 
                    options=available_subs_ids_for_selectbox, 
                    format_func=lambda s_id: available_subs_options_map.get(s_id, "Seleziona Sub-KPI...") if s_id else "Seleziona Sub-KPI...",
                    key="ms_sub_to_link_sb_widget_key" # Unique key
                )
                link_weight_input = st.number_input("Peso Distribuzione", min_value=0.01, value=1.0, step=0.1, key="ms_link_weight_input_widget_key")
                
                submit_link = st.form_submit_button("🔗 Collega Sub-KPI")
                if submit_link and selected_sub_to_link_id_widget and kpi_id_current:
                    try:
                        db_manager.add_master_sub_kpi_link(kpi_id_current, selected_sub_to_link_id_widget, link_weight_input)
                        st.success(f"Sub-KPI '{kpi_spec_map_link.get(selected_sub_to_link_id_widget)}' collegato con peso {link_weight_input}.")
                        st.rerun()
                    except ValueError as ve: st.error(f"Errore di validazione: {ve}")
                    except Exception as e: st.error(f"Errore durante il collegamento: {e}")
        
        with link_col2:
            if role_details["role"] == "master" and sub_kpi_links_with_weights_display:
                with st.form("unlink_sub_form", clear_on_submit=True):
                    st.markdown("**Scollega un Sub-KPI:**")
                    subs_of_current_master_map = {s['sub_kpi_spec_id']: s['name'] for s in sub_kpi_links_with_weights_display}
                    sub_to_unlink_id_widget = st.selectbox(
                        "Sub-KPI da Scollegare", 
                        options=[""] + list(subs_of_current_master_map.keys()), 
                        format_func=lambda s_id: subs_of_current_master_map.get(s_id, "Seleziona...") if s_id else "Seleziona...",
                        key="ms_sub_to_unlink_sb_widget_key" # Unique key
                        )
                    submit_unlink = st.form_submit_button("🗑️ Scollega Sub-KPI")
                    if submit_unlink and sub_to_unlink_id_widget and kpi_id_current:
                        try:
                            db_manager.remove_master_sub_kpi_link(kpi_id_current, sub_to_unlink_id_widget)
                            st.success(f"Sub-KPI '{kpi_spec_map_link.get(sub_to_unlink_id_widget)}' scollegato.")
                            st.rerun()
                        except Exception as e: st.error(f"Errore durante lo scollegamento: {e}")
            elif role_details["role"] == "sub" and role_details.get("master_id"):
                master_id_of_current_sub = role_details["master_id"]
                if st.button(f"🗑️ Scollega da Master ({kpi_spec_map_link.get(master_id_of_current_sub)})", type="secondary", key="ms_unlink_from_master_btn_key"):
                    try:
                        db_manager.remove_master_sub_kpi_link(master_id_of_current_sub, kpi_id_current)
                        st.success(f"KPI '{kpi_spec_map_link.get(kpi_id_current)}' scollegato dal suo master.")
                        st.rerun()
                    except Exception as e: st.error(f"Errore scollegamento da master: {e}")
        
        with link_col3:
            if role_details["role"] == "master" and sub_kpi_links_with_weights_display:
                with st.form("update_weight_form", clear_on_submit=False): # Keep values on submit for editing
                    st.markdown("**Modifica Peso di un Sub-KPI Collegato:**")
                    sub_for_weight_update_options_map = {s['sub_kpi_spec_id']: s['name'] for s in sub_kpi_links_with_weights_display}
                    
                    # Initialize session state for the selectbox if not present
                    if "ms_sub_for_weight_update_sb_widget_key" not in st.session_state:
                        st.session_state.ms_sub_for_weight_update_sb_widget_key = ""

                    sub_for_weight_update_id_widget = st.selectbox(
                        "Sub-KPI per Modifica Peso",
                        options=[""] + list(sub_for_weight_update_options_map.keys()),
                        format_func=lambda s_id: sub_for_weight_update_options_map.get(s_id, "Seleziona...") if s_id else "Seleziona...",
                        key="ms_sub_for_weight_update_sb_widget_key" # Unique key
                    )
                    
                    current_weight_for_selected_sub_val = 1.0 
                    if sub_for_weight_update_id_widget: # If a sub-KPI is selected
                        selected_sub_data = next((s for s in sub_kpi_links_with_weights_display if s['sub_kpi_spec_id'] == sub_for_weight_update_id_widget), None)
                        if selected_sub_data:
                            current_weight_for_selected_sub_val = selected_sub_data['weight']
                    
                    new_weight_input = st.number_input("Nuovo Peso Distribuzione", min_value=0.01, value=float(current_weight_for_selected_sub_val), step=0.1, key=f"ms_new_weight_input_widget_key_{sub_for_weight_update_id_widget}") # Make key dependent on selection
                    submit_update_weight = st.form_submit_button("⚖️ Aggiorna Peso")

                    if submit_update_weight and sub_for_weight_update_id_widget and kpi_id_current:
                        try:
                            db_manager.update_master_sub_kpi_link_weight(kpi_id_current, sub_for_weight_update_id_widget, new_weight_input)
                            st.success(f"Peso per Sub-KPI '{kpi_spec_map_link.get(sub_for_weight_update_id_widget)}' aggiornato a {new_weight_input}.")
                            st.rerun()
                        except ValueError as ve: st.error(f"Errore di validazione peso: {ve}")
                        except Exception as e: st.error(f"Errore durante l'aggiornamento del peso: {e}")
    else:
        st.info("Seleziona un KPI Principale per visualizzare e gestire i suoi link master/sub.")

# --- 🎯 Inserimento Target ---
with tab_target:
    st.header("Inserimento Target Annuali e Ripartizione")

    # --- Define ALL Callbacks and Helper functions for this tab at this top level ---
    def on_master_target_ui_change_st(master_id, target_num_str):
        target_num = int(target_num_str)
        if st.session_state.get("_master_sub_update_active_st", False):
            return
        st.session_state._master_sub_update_active_st = True
        try:
            master_data = st.session_state.kpi_target_inputs.get(master_id)
            if not master_data or not master_data.get("is_master_kpi"):
                return

            master_widget_key_base = f"kpi_entry_{master_id}"
            master_target_val_key_widget = (
                f"{master_widget_key_base}_target{target_num}"
            )
            master_target_val = st.session_state.get(
                master_target_val_key_widget,
                master_data.get(f"target{target_num}", 0.0),
            )

            sum_manual_sub_targets = 0.0
            non_manual_subs_for_dist = []
            total_weight_for_dist = 0.0

            for sub_info in master_data.get("sub_kpis_with_weights", []):
                sub_id = sub_info["sub_kpi_spec_id"]
                sub_weight = sub_info.get("weight", 1.0)
                sub_data_loop = st.session_state.kpi_target_inputs.get(sub_id)

                if sub_data_loop and sub_data_loop.get("is_sub_kpi"):
                    sub_widget_key_base = f"kpi_entry_{sub_id}"
                    sub_is_manual_widget_key = (
                        f"{sub_widget_key_base}_is_manual{target_num}"
                    )
                    sub_target_val_widget_key = (
                        f"{sub_widget_key_base}_target{target_num}"
                    )

                    sub_is_manual_val = st.session_state.get(
                        sub_is_manual_widget_key,
                        sub_data_loop.get(f"is_manual{target_num}", True),
                    )
                    sub_target_val_current = st.session_state.get(
                        sub_target_val_widget_key,
                        sub_data_loop.get(f"target{target_num}", 0.0),
                    )

                    if sub_is_manual_val:
                        sum_manual_sub_targets += float(sub_target_val_current)
                    else:
                        non_manual_subs_for_dist.append(
                            {"id": sub_id, "weight": sub_weight}
                        )
                        total_weight_for_dist += sub_weight

            remaining_target_for_dist = (
                float(master_target_val) - sum_manual_sub_targets
            )

            for sub_to_update in non_manual_subs_for_dist:
                sub_id_update = sub_to_update["id"]
                s_weight = sub_to_update["weight"]
                value_for_this_sub = 0.0
                if total_weight_for_dist > 1e-9:
                    value_for_this_sub = (
                        s_weight / total_weight_for_dist
                    ) * remaining_target_for_dist
                elif (
                    remaining_target_for_dist != 0 and len(non_manual_subs_for_dist) > 0
                ):
                    value_for_this_sub = remaining_target_for_dist / len(
                        non_manual_subs_for_dist
                    )

                sub_target_widget_key_update = (
                    f"kpi_entry_{sub_id_update}_target{target_num}"
                )
                st.session_state[sub_target_widget_key_update] = round(
                    value_for_this_sub, 2
                )  # Update widget state for next render

                if sub_id_update in st.session_state.kpi_target_inputs:
                    st.session_state.kpi_target_inputs[sub_id_update][
                        f"target{target_num}"
                    ] = round(value_for_this_sub, 2)
                    st.session_state.kpi_target_inputs[sub_id_update][
                        f"is_manual{target_num}"
                    ] = False
        finally:
            st.session_state._master_sub_update_active_st = False

    def on_sub_manual_flag_ui_change_st(sub_id, target_num_str):
        target_num = int(target_num_str)
        if st.session_state.get("_master_sub_update_active_st", False):
            return

        sub_data = st.session_state.kpi_target_inputs.get(sub_id)
        if sub_data and sub_data.get("is_sub_kpi") and sub_data.get("master_kpi_id"):
            master_id = sub_data["master_kpi_id"]

            sub_widget_key_base = f"kpi_entry_{sub_id}"
            manual_flag_widget_key = f"{sub_widget_key_base}_is_manual{target_num}"
            if sub_id in st.session_state.kpi_target_inputs:  # Update backing store
                st.session_state.kpi_target_inputs[sub_id][f"is_manual{target_num}"] = (
                    st.session_state.get(manual_flag_widget_key, True)
                )

            on_master_target_ui_change_st(master_id, str(target_num))

    def initial_master_sub_ui_distribution_st():
        if st.session_state.get(
            "_master_sub_update_active_st", False
        ) or not st.session_state.get("kpi_target_inputs"):
            return
        st.session_state._master_sub_update_active_st = True
        try:
            for (
                kpi_id_master_init,
                master_data_init,
            ) in st.session_state.kpi_target_inputs.items():
                if master_data_init.get("is_master_kpi"):
                    on_master_target_ui_change_st(kpi_id_master_init, "1")
                    on_master_target_ui_change_st(kpi_id_master_init, "2")
        finally:
            st.session_state._master_sub_update_active_st = False

    def load_kpi_data_for_target_entry():
        # st.write("--- DEBUG: load_kpi_data_for_target_entry CALLED ---")
        st.session_state.kpi_target_inputs = {}  # Reset the backing store
        year_str = st.session_state.get(
            "target_year_sb_filters", str(datetime.datetime.now().year)
        )
        stab_name = st.session_state.get("target_stab_sb_filters")

        if not year_str or not stab_name:
            return
        try:
            year = int(year_str)
            stabilimento_id = stabilimenti_map_target_ui.get(stab_name)
            if stabilimento_id is None:
                st.warning(f"ID Stabilimento non trovato per '{stab_name}'.")
                return
        except ValueError:
            st.error(f"Anno non valido: {year_str}")
            return
        except Exception as e:
            st.error(f"Errore preparazione caricamento target: {e}")
            return

        kpis_for_entry = dr.get_all_kpis_detailed(only_visible=True)
        if not kpis_for_entry:
            st.warning("Nessun KPI (visibile) trovato.")
            return

        for current_kpi_row in kpis_for_entry:
            kpi_spec_id = current_kpi_row["id"]
            if kpi_spec_id is None:
                continue
            existing_target_db_row = dr.get_annual_target_entry(
                year, stabilimento_id, kpi_spec_id
            )
            kpi_role_details = dr.get_kpi_role_details(kpi_spec_id)
            def_t1, def_t2 = 0.0, 0.0
            def_profile = PROFILE_ANNUAL_PROGRESSIVE
            def_logic = REPARTITION_LOGIC_ANNO
            def_repart_values_from_db = {}
            def_profile_params_from_db = {}
            def_is_manual1, def_is_manual2 = True, True
            if existing_target_db_row:
                try:  # Safely parse data from DB
                    val_t1 = existing_target_db_row["annual_target1"]
                    def_t1 = float(val_t1 if val_t1 is not None else 0.0)
                    val_t2 = existing_target_db_row["annual_target2"]
                    def_t2 = float(val_t2 if val_t2 is not None else 0.0)
                    db_profile_val = existing_target_db_row["distribution_profile"]
                    if (
                        db_profile_val
                        and db_profile_val in DISTRIBUTION_PROFILE_OPTIONS
                    ):
                        def_profile = db_profile_val
                    def_logic = (
                        existing_target_db_row["repartition_logic"]
                        or REPARTITION_LOGIC_ANNO
                    )
                    val_manual1 = existing_target_db_row["is_target1_manual"]
                    def_is_manual1 = (
                        bool(val_manual1) if val_manual1 is not None else True
                    )
                    val_manual2 = existing_target_db_row["is_target2_manual"]
                    def_is_manual2 = (
                        bool(val_manual2) if val_manual2 is not None else True
                    )
                    repart_values_str = (
                        existing_target_db_row["repartition_values"] or "{}"
                    )
                    def_repart_values_from_db = json.loads(repart_values_str)
                    profile_params_str = (
                        existing_target_db_row["profile_params"] or "{}"
                    )
                    def_profile_params_from_db = json.loads(profile_params_str)
                except KeyError as e:
                    st.warning(f"Colonna target mancante per KPI {kpi_spec_id}: {e}.")
                except json.JSONDecodeError as e:
                    st.warning(f"Errore JSON target per KPI {kpi_spec_id}: {e}.")
                except Exception as e_row_access:
                    st.error(
                        f"Errore accesso riga target per KPI {kpi_spec_id}: {e_row_access}"
                    )
            try:  # Safely get KPI details
                calc_type = current_kpi_row["calculation_type"]
                unit_of_measure = (
                    current_kpi_row["unit_of_measure"]
                    if "unit_of_measure" in current_kpi_row.keys()
                    else ""
                )
            except KeyError as e:
                st.error(f"Colonna KPI mancante per {kpi_spec_id}: {e}")
                calc_type = CALC_TYPE_INCREMENTALE
                unit_of_measure = ""

            # Populate the backing data store ONLY.
            st.session_state.kpi_target_inputs[kpi_spec_id] = {
                "target1": def_t1,
                "target2": def_t2,
                "is_manual1": def_is_manual1,
                "is_manual2": def_is_manual2,
                "profile": def_profile,
                "logic": def_logic,
                "repartition_values_raw": def_repart_values_from_db,
                "profile_params_raw": def_profile_params_from_db,
                "calc_type": calc_type,
                "unit_of_measure": unit_of_measure,
                "is_sub_kpi": kpi_role_details["role"] == "sub",
                "master_kpi_id": kpi_role_details.get("master_id"),
                "is_master_kpi": kpi_role_details["role"] == "master",
                "sub_kpis_with_weights": [],
                "display_name": get_kpi_display_name(dict(current_kpi_row)),
            }
            # DO NOT set st.session_state[widget_key] here. That's done by the widget's `value` param during render.
            if st.session_state.kpi_target_inputs[kpi_spec_id]["is_master_kpi"]:
                sub_ids_raw = dr.get_sub_kpis_for_master(kpi_spec_id)
                if sub_ids_raw:
                    with sqlite3.connect(db_manager.DB_KPIS) as conn_weights:
                        conn_weights.row_factory = sqlite3.Row
                        for sub_id_r in sub_ids_raw:
                            link_row = conn_weights.execute(
                                "SELECT sub_kpi_spec_id, distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?",
                                (kpi_spec_id, sub_id_r),
                            ).fetchone()
                            if link_row:
                                st.session_state.kpi_target_inputs[kpi_spec_id][
                                    "sub_kpis_with_weights"
                                ].append(
                                    {
                                        "sub_kpi_spec_id": link_row["sub_kpi_spec_id"],
                                        "weight": link_row["distribution_weight"],
                                    }
                                )

        initial_master_sub_ui_distribution_st()  # This will read from kpi_target_inputs and update widget states if needed.
        # st.write("--- DEBUG: load_kpi_data_for_target_entry FINISHED ---")

    # --- Filters ---
    stabilimenti_all_target_filters = dr.get_all_stabilimenti(only_visible=True)
    stabilimenti_map_target_ui = {
        s["name"]: s["id"] for s in stabilimenti_all_target_filters
    }

    target_filter_cols = st.columns([1, 2, 1])
    with target_filter_cols[0]:
        year_options_filter = list(
            range(datetime.datetime.now().year - 5, datetime.datetime.now().year + 6)
        )
        current_year_filter_val_str = st.session_state.get(
            "target_year_sb_filters", str(datetime.datetime.now().year)
        )
        try:
            default_year_idx_filter = year_options_filter.index(
                int(current_year_filter_val_str)
            )
        except (ValueError, TypeError):
            default_year_idx_filter = year_options_filter.index(
                datetime.datetime.now().year
            )
        st.selectbox(
            "Anno",
            options=year_options_filter,
            index=default_year_idx_filter,
            key="target_year_sb_filters",
            on_change=load_kpi_data_for_target_entry,
        )

    stabilimenti_names_target_filter = [""] + list(stabilimenti_map_target_ui.keys())
    with target_filter_cols[1]:
        current_stab_filter_val = st.session_state.get("target_stab_sb_filters")
        try:
            stab_idx_filter = (
                stabilimenti_names_target_filter.index(current_stab_filter_val)
                if current_stab_filter_val is not None
                else 0
            )
        except ValueError:
            stab_idx_filter = 0
        st.selectbox(
            "Stabilimento",
            stabilimenti_names_target_filter,
            index=stab_idx_filter,
            key="target_stab_sb_filters",
            on_change=load_kpi_data_for_target_entry,
        )

    with target_filter_cols[2]:
        st.button(
            "Ricarica Dati Target",
            on_click=load_kpi_data_for_target_entry,
            use_container_width=True,
            key="reload_target_data_button_filters",
        )

    # --- Display KPI Target Entry Fields ---
    year_str_for_display_check = st.session_state.get("target_year_sb_filters")
    stab_name_for_display_check = st.session_state.get("target_stab_sb_filters")
    kpi_inputs_for_display = st.session_state.get("kpi_target_inputs")

    if (
        year_str_for_display_check
        and stab_name_for_display_check
        and kpi_inputs_for_display
    ):
        year_to_display = year_str_for_display_check
        stabilimento_to_display = stab_name_for_display_check

        st.markdown("---")
        st.subheader(f"Target per {stabilimento_to_display} - Anno {year_to_display}")

        sorted_kpi_ids = sorted(
            kpi_inputs_for_display.keys(),
            key=lambda kpi_id: kpi_inputs_for_display[kpi_id].get(
                "display_name", str(kpi_id)
            ),
        )

        for kpi_spec_id in sorted_kpi_ids:
            kpi_session_data = kpi_inputs_for_display[
                kpi_spec_id
            ]  # Data from backing store
            key_base = f"kpi_entry_{kpi_spec_id}"

            exp_label = f"{kpi_session_data.get('display_name', 'KPI N/D')} (ID Spec: {kpi_spec_id}, Unità: {kpi_session_data.get('unit_of_measure', 'N/D')}, Tipo: {kpi_session_data.get('calc_type', 'N/D')})"
            prefix = ""
            if kpi_session_data.get("is_sub_kpi"):
                is_manual1_ui = st.session_state.get(
                    f"{key_base}_is_manual1", kpi_session_data.get("is_manual1", True)
                )
                is_manual2_ui = st.session_state.get(
                    f"{key_base}_is_manual2", kpi_session_data.get("is_manual2", True)
                )
                if not is_manual1_ui or not is_manual2_ui:
                    prefix = "⚙️ (Derivato) "
                else:
                    prefix = "✏️ (Manuale) "

            with st.expander(prefix + exp_label):
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.number_input(
                        "Target 1",
                        value=float(
                            kpi_session_data.get("target1", 0.0)
                        ),  # Value from backing store
                        key=f"{key_base}_target1",
                        format="%.2f",
                        disabled=kpi_session_data.get("is_sub_kpi")
                        and not kpi_session_data.get(
                            "is_manual1", True
                        ),  # Disable based on backing store initially
                        on_change=(
                            on_master_target_ui_change_st
                            if kpi_session_data.get("is_master_kpi")
                            else None
                        ),
                        args=(
                            (kpi_spec_id, "1")
                            if kpi_session_data.get("is_master_kpi")
                            else None
                        ),
                    )
                    if kpi_session_data.get("is_sub_kpi"):
                        st.checkbox(
                            "Manuale T1",
                            value=kpi_session_data.get(
                                "is_manual1", True
                            ),  # Value from backing store
                            key=f"{key_base}_is_manual1",
                            on_change=on_sub_manual_flag_ui_change_st,
                            args=(kpi_spec_id, "1"),
                        )
                with col_t2:
                    st.number_input(
                        "Target 2",
                        value=float(
                            kpi_session_data.get("target2", 0.0)
                        ),  # Value from backing store
                        key=f"{key_base}_target2",
                        format="%.2f",
                        disabled=kpi_session_data.get("is_sub_kpi")
                        and not kpi_session_data.get(
                            "is_manual2", True
                        ),  # Disable based on backing store
                        on_change=(
                            on_master_target_ui_change_st
                            if kpi_session_data.get("is_master_kpi")
                            else None
                        ),
                        args=(
                            (kpi_spec_id, "2")
                            if kpi_session_data.get("is_master_kpi")
                            else None
                        ),
                    )
                    if kpi_session_data.get("is_sub_kpi"):
                        st.checkbox(
                            "Manuale T2",
                            value=kpi_session_data.get(
                                "is_manual2", True
                            ),  # Value from backing store
                            key=f"{key_base}_is_manual2",
                            on_change=on_sub_manual_flag_ui_change_st,
                            args=(kpi_spec_id, "2"),
                        )

                profile_val_from_backing = kpi_session_data.get(
                    "profile", PROFILE_ANNUAL_PROGRESSIVE
                )
                try:
                    profile_idx = DISTRIBUTION_PROFILE_OPTIONS.index(
                        profile_val_from_backing
                    )
                except ValueError:
                    profile_idx = DISTRIBUTION_PROFILE_OPTIONS.index(
                        PROFILE_ANNUAL_PROGRESSIVE
                    )
                st.selectbox(
                    "Profilo Distribuzione",
                    options=DISTRIBUTION_PROFILE_OPTIONS,
                    index=profile_idx,
                    key=f"{key_base}_profile",
                )

                current_profile_ui = st.session_state.get(
                    f"{key_base}_profile", profile_val_from_backing
                )  # Read widget's current state
                show_logic_radios_ui = True
                if current_profile_ui in [
                    PROFILE_ANNUAL_PROGRESSIVE,
                    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
                    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
                    PROFILE_EVEN,
                    "event_based_spikes_or_dips",
                ]:
                    show_logic_radios_ui = False

                logic_val_from_backing = kpi_session_data.get(
                    "logic", REPARTITION_LOGIC_ANNO
                )
                try:
                    logic_idx = REPARTITION_LOGIC_OPTIONS.index(logic_val_from_backing)
                except ValueError:
                    logic_idx = REPARTITION_LOGIC_OPTIONS.index(REPARTITION_LOGIC_ANNO)
                if show_logic_radios_ui:
                    st.selectbox(
                        "Logica Rip. Valori",
                        options=REPARTITION_LOGIC_OPTIONS,
                        index=logic_idx,
                        key=f"{key_base}_logic",
                    )

                effective_logic_for_display = st.session_state.get(
                    f"{key_base}_logic", logic_val_from_backing
                )  # Read widget state or backing
                if not show_logic_radios_ui:
                    effective_logic_for_display = REPARTITION_LOGIC_ANNO

                raw_repart_db_vals = kpi_session_data.get(
                    "repartition_values_raw", {}
                )  # From backing store
                if (
                    effective_logic_for_display == REPARTITION_LOGIC_MESE
                    and show_logic_radios_ui
                ):
                    st.markdown("###### Valori Mensili (%)")
                    month_cols = st.columns(4)
                    months = [calendar.month_name[i] for i in range(1, 13)]
                    for i, month_name in enumerate(months):
                        with month_cols[i % 4]:
                            # Use raw_repart_db_vals for initial value for these number_inputs
                            default_month_val = raw_repart_db_vals.get(
                                month_name,
                                (
                                    round(100 / 12, 2)
                                    if kpi_session_data.get("calc_type")
                                    == CALC_TYPE_INCREMENTALE
                                    else 100.0
                                ),
                            )
                            st.number_input(
                                month_name[:3],
                                value=float(default_month_val),
                                format="%.2f",
                                key=f"{key_base}_month_{i}",
                            )
                elif (
                    effective_logic_for_display == REPARTITION_LOGIC_TRIMESTRE
                    and show_logic_radios_ui
                ):
                    st.markdown("###### Valori Trimestrali (%)")
                    q_cols = st.columns(4)
                    quarters = ["Q1", "Q2", "Q3", "Q4"]
                    for i, q_name in enumerate(quarters):
                        with q_cols[i % 4]:
                            default_q_val = raw_repart_db_vals.get(
                                q_name,
                                (
                                    round(100 / 4, 2)
                                    if kpi_session_data.get("calc_type")
                                    == CALC_TYPE_INCREMENTALE
                                    else 100.0
                                ),
                            )
                            st.number_input(
                                q_name,
                                value=float(default_q_val),
                                format="%.2f",
                                key=f"{key_base}_q_{i}",
                            )
                elif (
                    effective_logic_for_display == REPARTITION_LOGIC_SETTIMANA
                    and show_logic_radios_ui
                ):
                    st.markdown("###### Valori Settimanali (JSON)")
                    weekly_json_val = (
                        json.dumps(raw_repart_db_vals, indent=2)
                        if isinstance(raw_repart_db_vals, dict)
                        and any(k.count("-W") > 0 for k in raw_repart_db_vals.keys())
                        else json.dumps({"Info": 'Es: {"2024-W01": 2.5}'}, indent=2)
                    )
                    st.text_area(
                        "JSON Settimanale",
                        value=weekly_json_val,
                        height=100,
                        key=f"{key_base}_weekly_json",
                    )

                if current_profile_ui == "event_based_spikes_or_dips":
                    st.markdown("###### Parametri Eventi (JSON)")
                    profile_params_from_backing = kpi_session_data.get(
                        "profile_params_raw", {}
                    )
                    event_json_val = json.dumps(
                        profile_params_from_backing.get(
                            "events",
                            [
                                {
                                    "start_date": "YYYY-MM-DD",
                                    "end_date": "YYYY-MM-DD",
                                    "multiplier": 1.0,
                                    "addition": 0.0,
                                    "comment": "Esempio",
                                }
                            ],
                        ),
                        indent=2,
                    )
                    st.text_area(
                        "JSON Eventi",
                        value=event_json_val,
                        height=120,
                        key=f"{key_base}_event_json",
                    )

        st.markdown("---")
        if st.button(
            "SALVA TUTTI I TARGET",
            type="primary",
            use_container_width=True,
            key="save_all_targets_button_main",
        ):
            year_to_save_val = int(st.session_state.get("target_year_sb_filters"))
            stab_name_to_save_val = st.session_state.get("target_stab_sb_filters")
            stab_id_to_save_val = stabilimenti_map_target_ui.get(stab_name_to_save_val)

            if not year_to_save_val or stab_id_to_save_val is None:
                st.error("Anno o Stabilimento non validi per il salvataggio.")
            else:
                targets_to_save_for_db = {}
                all_inputs_valid_save = True
                for (
                    kpi_id_save,
                    kpi_data_sess_save,
                ) in (
                    st.session_state.kpi_target_inputs.items()
                ):  # Iterate backing store
                    key_base_save = f"kpi_entry_{kpi_id_save}"
                    try:  # Read current values from widgets via session_state
                        t1_val_save = st.session_state[f"{key_base_save}_target1"]
                        t2_val_save = st.session_state[f"{key_base_save}_target2"]
                    except KeyError:
                        st.warning(
                            f"Dati widget UI mancanti per KPI {kpi_id_save} durante salvataggio. Salto."
                        )
                        continue

                    profile_save = st.session_state.get(
                        f"{key_base_save}_profile", kpi_data_sess_save.get("profile")
                    )
                    is_manual1_save = st.session_state.get(
                        f"{key_base_save}_is_manual1",
                        kpi_data_sess_save.get("is_manual1", True),
                    )
                    is_manual2_save = st.session_state.get(
                        f"{key_base_save}_is_manual2",
                        kpi_data_sess_save.get("is_manual2", True),
                    )

                    repart_values_for_db_save, profile_params_for_db_save = {}, {}
                    show_logic_radios_save_check = True
                    if profile_save in [
                        PROFILE_ANNUAL_PROGRESSIVE,
                        PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
                        PROFILE_TRUE_ANNUAL_SINUSOIDAL,
                        PROFILE_EVEN,
                        "event_based_spikes_or_dips",
                    ]:
                        show_logic_radios_save_check = False
                    effective_logic_db_save = REPARTITION_LOGIC_ANNO
                    if show_logic_radios_save_check:
                        effective_logic_db_save = st.session_state.get(
                            f"{key_base_save}_logic", kpi_data_sess_save.get("logic")
                        )

                    if (
                        effective_logic_db_save == REPARTITION_LOGIC_MESE
                        and show_logic_radios_save_check
                    ):
                        months_save = [calendar.month_name[i] for i in range(1, 13)]
                        current_sum_percent = 0
                        for i, month_name_save in enumerate(months_save):
                            val = st.session_state.get(
                                f"{key_base_save}_month_{i}", 0.0
                            )
                            repart_values_for_db_save[month_name_save] = float(val)
                            current_sum_percent += float(val)
                        if (
                            kpi_data_sess_save.get("calc_type")
                            == CALC_TYPE_INCREMENTALE
                            and not (99.9 <= current_sum_percent <= 100.1)
                            and (
                                abs(float(t1_val_save)) > 1e-9
                                or abs(float(t2_val_save)) > 1e-9
                            )
                        ):
                            st.error(
                                f"KPI {kpi_data_sess_save.get('display_name', kpi_id_save)}: Somma MESE {current_sum_percent:.2f}%. Deve essere 100%."
                            )
                            all_inputs_valid_save = False
                            break
                    elif (
                        effective_logic_db_save == REPARTITION_LOGIC_TRIMESTRE
                        and show_logic_radios_save_check
                    ):
                        quarters_save = ["Q1", "Q2", "Q3", "Q4"]
                        current_sum_percent = 0
                        for i, q_name_save in enumerate(quarters_save):
                            val = st.session_state.get(f"{key_base_save}_q_{i}", 0.0)
                            repart_values_for_db_save[q_name_save] = float(val)
                            current_sum_percent += float(val)
                        if (
                            kpi_data_sess_save.get("calc_type")
                            == CALC_TYPE_INCREMENTALE
                            and not (99.9 <= current_sum_percent <= 100.1)
                            and (
                                abs(float(t1_val_save)) > 1e-9
                                or abs(float(t2_val_save)) > 1e-9
                            )
                        ):
                            st.error(
                                f"KPI {kpi_data_sess_save.get('display_name', kpi_id_save)}: Somma TRIMESTRE {current_sum_percent:.2f}%. Deve essere 100%."
                            )
                            all_inputs_valid_save = False
                            break
                    elif (
                        effective_logic_db_save == REPARTITION_LOGIC_SETTIMANA
                        and show_logic_radios_save_check
                    ):
                        json_str_weekly = st.session_state.get(
                            f"{key_base_save}_weekly_json", "{}"
                        )
                        try:
                            repart_values_for_db_save = json.loads(json_str_weekly)
                        except json.JSONDecodeError:
                            st.error(
                                f"KPI {kpi_data_sess_save.get('display_name', kpi_id_save)}: JSON settimanale non valido."
                            )
                            all_inputs_valid_save = False
                            break

                    if profile_save == "event_based_spikes_or_dips":
                        json_str_event = st.session_state.get(
                            f"{key_base_save}_event_json", "[]"
                        )
                        try:
                            profile_params_for_db_save["events"] = json.loads(
                                json_str_event
                            )
                        except json.JSONDecodeError:
                            st.error(
                                f"KPI {kpi_data_sess_save.get('display_name', kpi_id_save)}: JSON eventi non valido."
                            )
                            all_inputs_valid_save = False
                            break

                    if not all_inputs_valid_save:
                        break
                    targets_to_save_for_db[str(kpi_id_save)] = {
                        "annual_target1": float(t1_val_save),
                        "annual_target2": float(t2_val_save),
                        "repartition_logic": effective_logic_db_save,
                        "repartition_values": repart_values_for_db_save,
                        "distribution_profile": profile_save,
                        "profile_params": profile_params_for_db_save,
                        "is_target1_manual": is_manual1_save,
                        "is_target2_manual": is_manual2_save,
                    }

                if all_inputs_valid_save and targets_to_save_for_db:
                    try:
                        db_manager.save_annual_targets(
                            year_to_save_val,
                            stab_id_to_save_val,
                            targets_to_save_for_db,
                        )
                        st.success("Target salvati e CSV (potenzialmente) rigenerati!")
                        load_kpi_data_for_target_entry()
                        st.rerun()
                    except Exception as e_save_db:
                        st.error(
                            f"Errore durante il salvataggio nel database: {e_save_db}"
                        )
                        import traceback

                        st.error(traceback.format_exc())
                elif not targets_to_save_for_db and all_inputs_valid_save:
                    st.warning("Nessun dato target valido da salvare.")
                elif not all_inputs_valid_save:
                    st.error(
                        "Salvataggio annullato a causa di errori nei dati di input."
                    )
    else:
        st.info("Seleziona Anno e Stabilimento per visualizzare o inserire i target.")

    year_filter_value_auto = st.session_state.get("target_year_sb_filters")
    stab_filter_value_auto = st.session_state.get("target_stab_sb_filters")

    if "last_loaded_year_filter" not in st.session_state:
        st.session_state.last_loaded_year_filter = None
    if "last_loaded_stab_filter" not in st.session_state:
        st.session_state.last_loaded_stab_filter = None

    if year_filter_value_auto and stab_filter_value_auto:
        needs_load_auto = not st.session_state.get("kpi_target_inputs") or (
            st.session_state.last_loaded_year_filter != year_filter_value_auto
            or st.session_state.last_loaded_stab_filter != stab_filter_value_auto
        )
        if needs_load_auto:
            load_kpi_data_for_target_entry()
            st.session_state.last_loaded_year_filter = year_filter_value_auto
            st.session_state.last_loaded_stab_filter = stab_filter_value_auto
        elif st.session_state.get("kpi_target_inputs"):
            initial_master_sub_ui_distribution_st()

# --- 📈 Visualizzazione Risultati ---
with tab_results:
    st.header("Visualizzazione Risultati Ripartiti")

    res_col1, res_col2, res_col3, res_col4 = st.columns(4)
    with res_col1:
        if "results_year" not in st.session_state:
            st.session_state.results_year = str(datetime.datetime.now().year)
        current_year_res_val = st.session_state.results_year
        year_options_res = list(
            range(datetime.datetime.now().year - 5, datetime.datetime.now().year + 6)
        )
        try:
            default_year_index_res = year_options_res.index(int(current_year_res_val))
        except (ValueError, TypeError):
            default_year_index_res = year_options_res.index(
                datetime.datetime.now().year
            )
        selected_year_res = st.selectbox(
            "Anno Risultati",
            options=year_options_res,
            index=default_year_index_res,
            key="res_year_sb_widget_v2",
        )  # Unique key
        st.session_state.results_year = str(selected_year_res)

    stabilimenti_all_res = dr.get_all_stabilimenti(only_visible=False)
    stabilimenti_map_res = {s["name"]: s["id"] for s in stabilimenti_all_res}
    stabilimenti_names_res = [""] + list(stabilimenti_map_res.keys())
    with res_col2:
        if "res_stab_sb_widget_v2" not in st.session_state:
            st.session_state.res_stab_sb_widget_v2 = None  # Use unique key
        current_stab_name_res = st.session_state.res_stab_sb_widget_v2
        try:
            stab_idx_res = (
                stabilimenti_names_res.index(current_stab_name_res)
                if current_stab_name_res
                else 0
            )
        except ValueError:
            stab_idx_res = 0
        selected_stab_name_res = st.selectbox(
            "Stabilimento Risultati",
            stabilimenti_names_res,
            index=stab_idx_res,
            key="res_stab_sb_widget_v2",
        )  # Unique key
        if selected_stab_name_res:
            st.session_state.results_stabilimento_id = stabilimenti_map_res[
                selected_stab_name_res
            ]
        else:
            st.session_state.results_stabilimento_id = None

    with res_col3:
        if "results_period_type" not in st.session_state:
            st.session_state.results_period_type = "Mese"
        current_period_type_res = st.session_state.results_period_type
        try:
            period_idx_res = PERIOD_TYPES_RESULTS.index(current_period_type_res)
        except ValueError:
            period_idx_res = PERIOD_TYPES_RESULTS.index("Mese")
        selected_period_res = st.selectbox(
            "Tipo Periodo",
            PERIOD_TYPES_RESULTS,
            index=period_idx_res,
            key="res_period_sb_widget_v2",
        )  # Unique key
        st.session_state.results_period_type = selected_period_res

    with res_col4:
        # Changed from selectbox to multiselect for Target Number
        if "results_target_numbers_ms" not in st.session_state:  # ms for multiselect
            st.session_state.results_target_numbers_ms = [
                1,
                2,
            ]  # Default to both selected

        selected_target_numbers = st.multiselect(
            "Numero/i Target",
            options=[1, 2],
            default=st.session_state.results_target_numbers_ms,  # Use session state for default
            key="res_target_numbers_multiselect_widget",  # Unique key
        )
        st.session_state.results_target_numbers_ms = (
            selected_target_numbers  # Update session state
        )

    st.markdown("##### Seleziona KPI per visualizzare i risultati:")
    groups_res = dr.get_kpi_groups()
    groups_map_res = {g["name"]: g["id"] for g in groups_res}
    group_names_res = [""] + list(groups_map_res.keys())

    res_kpi_col1, res_kpi_col2, res_kpi_col3 = st.columns(3)
    with res_kpi_col1:
        if "res_group_sel_widget_v2" not in st.session_state:
            st.session_state.res_group_sel_widget_v2 = None
        current_group_id_res = st.session_state.get("results_group_id")
        selected_group_name_for_idx = next(
            (
                name
                for name, id_val in groups_map_res.items()
                if id_val == current_group_id_res
            ),
            None,
        )
        try:
            group_idx_res = (
                group_names_res.index(selected_group_name_for_idx)
                if selected_group_name_for_idx
                else 0
            )
        except ValueError:
            group_idx_res = 0
        selected_group_name_res_widget = st.selectbox(
            "Gruppo KPI Ris.",
            group_names_res,
            index=group_idx_res,
            key="res_group_sel_widget_v2",
            on_change=lambda: setattr(st.session_state, "results_subgroup_id", None)
            or setattr(st.session_state, "results_kpi_spec_id", None)
            or setattr(st.session_state, "res_subgroup_sel_widget_v2", None)
            or setattr(st.session_state, "res_indicator_sel_widget_v2", None),
        )
        if selected_group_name_res_widget:
            st.session_state.results_group_id = groups_map_res[
                selected_group_name_res_widget
            ]
        else:
            st.session_state.results_group_id = None

    subgroups_map_res_ui = {}
    subgroup_names_res_ui = [""]
    if st.session_state.results_group_id:
        subgroups_res_list_data = dr.get_kpi_subgroups_by_group_revised(
            st.session_state.results_group_id
        )
        for sg_res in subgroups_res_list_data:
            display_name_res = sg_res["name"] + (
                f" (Tpl: {sg_res['template_name']})"
                if sg_res.get("template_name")
                else ""
            )
            subgroups_map_res_ui[display_name_res] = sg_res["id"]
            subgroup_names_res_ui.append(display_name_res)
    with res_kpi_col2:
        if "res_subgroup_sel_widget_v2" not in st.session_state:
            st.session_state.res_subgroup_sel_widget_v2 = None
        current_subgroup_id_res = st.session_state.get("results_subgroup_id")
        selected_subgroup_name_for_idx = next(
            (
                name
                for name, id_val in subgroups_map_res_ui.items()
                if id_val == current_subgroup_id_res
            ),
            None,
        )
        try:
            subgroup_idx_res = (
                subgroup_names_res_ui.index(selected_subgroup_name_for_idx)
                if selected_subgroup_name_for_idx
                else 0
            )
        except ValueError:
            subgroup_idx_res = 0
        selected_subgroup_display_name_res_widget = st.selectbox(
            "Sottogruppo KPI Ris.",
            subgroup_names_res_ui,
            index=subgroup_idx_res,
            key="res_subgroup_sel_widget_v2",
            disabled=not st.session_state.results_group_id,
            on_change=lambda: setattr(st.session_state, "results_kpi_spec_id", None)
            or setattr(st.session_state, "res_indicator_sel_widget_v2", None),
        )
        if selected_subgroup_display_name_res_widget:
            st.session_state.results_subgroup_id = subgroups_map_res_ui[
                selected_subgroup_display_name_res_widget
            ]
        else:
            st.session_state.results_subgroup_id = None

    kpi_specs_for_res_map = {}
    kpi_specs_names_res = [""]
    if st.session_state.results_subgroup_id:
        all_specs_res_data = dr.get_all_kpis_detailed(only_visible=True)
        for spec_res in all_specs_res_data:
            if spec_res["subgroup_id"] == st.session_state.results_subgroup_id:
                display_name_kpi_res = spec_res["indicator_name"]
                kpi_specs_for_res_map[display_name_kpi_res] = spec_res["id"]
                kpi_specs_names_res.append(display_name_kpi_res)
    with res_kpi_col3:
        if "res_indicator_sel_widget_v2" not in st.session_state:
            st.session_state.res_indicator_sel_widget_v2 = None
        current_kpi_spec_id_res = st.session_state.get("results_kpi_spec_id")
        selected_indicator_name_for_idx = next(
            (
                name
                for name, id_val in kpi_specs_for_res_map.items()
                if id_val == current_kpi_spec_id_res
            ),
            None,
        )
        try:
            indicator_idx_res = (
                kpi_specs_names_res.index(selected_indicator_name_for_idx)
                if selected_indicator_name_for_idx
                else 0
            )
        except ValueError:
            indicator_idx_res = 0
        selected_kpi_spec_name_res_widget = st.selectbox(
            "Indicatore KPI Ris.",
            kpi_specs_names_res,
            index=indicator_idx_res,
            key="res_indicator_sel_widget_v2",
            disabled=not st.session_state.results_subgroup_id,
        )
        if selected_kpi_spec_name_res_widget:
            st.session_state.results_kpi_spec_id = kpi_specs_for_res_map[
                selected_kpi_spec_name_res_widget
            ]
        else:
            st.session_state.results_kpi_spec_id = None

    if st.button(
        "Mostra Risultati Ripartiti", key="show_results_button_key_v2"
    ):  # Unique key
        # Use the centrally stored session_state.results_ variables for fetching data
        # AND the new st.session_state.results_target_numbers_ms
        selected_targets_to_show = st.session_state.results_target_numbers_ms

        if not selected_targets_to_show:
            st.warning("Seleziona almeno un Numero Target (1 o 2).")
        elif (
            st.session_state.results_kpi_spec_id
            and st.session_state.results_year
            and st.session_state.results_stabilimento_id
            and st.session_state.results_period_type
        ):

            all_periodic_data_dfs = []
            try:
                year_val_res = int(st.session_state.results_year)

                for target_num_to_fetch in selected_targets_to_show:
                    periodic_data_single_target = dr.get_periodic_targets_for_kpi(
                        year_val_res,
                        st.session_state.results_stabilimento_id,
                        st.session_state.results_kpi_spec_id,
                        st.session_state.results_period_type,
                        target_num_to_fetch,  # Fetch for current target number in loop
                    )
                    if periodic_data_single_target:
                        df_single_target = pd.DataFrame(
                            [dict(row) for row in periodic_data_single_target]
                        )
                        df_single_target["Target Number"] = (
                            f"Target {target_num_to_fetch}"  # Add column to identify target
                        )
                        all_periodic_data_dfs.append(df_single_target)

                if all_periodic_data_dfs:
                    # Combine DataFrames for table and chart
                    combined_df = pd.concat(all_periodic_data_dfs)
                    combined_df["Target"] = pd.to_numeric(
                        combined_df["Target"], errors="coerce"
                    )
                    combined_df.dropna(subset=["Target"], inplace=True)

                    if not combined_df.empty:
                        # Prepare for table: Pivot if multiple targets selected for side-by-side view
                        if len(selected_targets_to_show) > 1:
                            df_for_table = combined_df.pivot(
                                index="Periodo",
                                columns="Target Number",
                                values="Target",
                            ).reset_index()
                        else:
                            df_for_table = combined_df[
                                ["Periodo", "Target"]
                            ]  # Or rename Target to Target 1 / Target 2

                        # Ensure correct sorting for table and chart
                        period_type_for_sort = st.session_state.results_period_type
                        if period_type_for_sort == "Mese":
                            month_sorter_res = calendar.month_name[1:]
                            df_for_table["Periodo"] = pd.Categorical(
                                df_for_table["Periodo"],
                                categories=month_sorter_res,
                                ordered=True,
                            )
                            combined_df["Periodo"] = pd.Categorical(
                                combined_df["Periodo"],
                                categories=month_sorter_res,
                                ordered=True,
                            )  # For chart
                        elif period_type_for_sort == "Trimestre":
                            q_sorter_res = ["Q1", "Q2", "Q3", "Q4"]
                            df_for_table["Periodo"] = pd.Categorical(
                                df_for_table["Periodo"],
                                categories=q_sorter_res,
                                ordered=True,
                            )
                            combined_df["Periodo"] = pd.Categorical(
                                combined_df["Periodo"],
                                categories=q_sorter_res,
                                ordered=True,
                            )  # For chart

                        df_for_table.sort_values("Periodo", inplace=True)
                        combined_df.sort_values(
                            ["Periodo", "Target Number"], inplace=True
                        )  # Sort chart data too

                        st.dataframe(
                            df_for_table.set_index("Periodo"), use_container_width=True
                        )

                        # For st.line_chart, it expects x, y, and optionally color.
                        # The 'Target Number' column can be used for color.
                        st.line_chart(
                            combined_df, x="Periodo", y="Target", color="Target Number"
                        )
                    else:
                        st.info(
                            "Nessun dato numerico valido trovato per i target selezionati dopo la pulizia."
                        )
                else:
                    st.info(
                        "Nessun dato periodico trovato per i filtri e target selezionati."
                    )
            except Exception as e_results:
                st.error(
                    f"Errore durante il recupero o la visualizzazione dei dati periodici: {e_results}"
                )
                import traceback

                st.error(traceback.format_exc())
        else:
            st.warning(
                "Completa tutti i filtri (Anno, Stabilimento, Tipo Periodo, KPI) e seleziona almeno un Numero Target per visualizzare i risultati."
            )


# --- 📦 Esportazione Dati ---
with tab_export:
    st.header("Esportazione Dati Globali")

    # Ensure necessary modules are imported at the top of your Streamlit script
    # import streamlit as st
    # from pathlib import Path
    # import datetime
    # import sys
    # import subprocess
    # import export_manager # Your module
    # from app_config import CSV_EXPORT_BASE_PATH # Your config
    # import traceback

    if (
        "CSV_EXPORT_BASE_PATH" not in globals()
        and "CSV_EXPORT_BASE_PATH" not in locals()
    ):
        # Attempt to import if not found - this is a fallback, ideally it's imported at script top
        try:
            from app_config import CSV_EXPORT_BASE_PATH

            if (
                "CSV_EXPORT_BASE_PATH" not in globals()
                and "CSV_EXPORT_BASE_PATH" not in locals()
            ):  # Check again after import
                raise ImportError(
                    "CSV_EXPORT_BASE_PATH still not defined after import attempt."
                )
        except ImportError:
            st.error(
                "CRITICO: CSV_EXPORT_BASE_PATH non è definito. Controlla app_config.py e le importazioni."
            )
            st.stop()  # Stop rendering this tab if config is missing

    resolved_path_str = str(Path(CSV_EXPORT_BASE_PATH).resolve())
    st.markdown(
        f"I file CSV globali e l'archivio ZIP saranno generati/aggiornati in:\n`{resolved_path_str}`"
    )
    st.markdown("---")

    st.subheader("Azioni di Esportazione")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🔄 Genera/Aggiorna Tutti i File CSV",
            key="generate_all_csv_files_streamlit",
        ):
            export_base_path = Path(CSV_EXPORT_BASE_PATH)
            export_base_path.mkdir(
                parents=True, exist_ok=True
            )  # Ensure directory exists
            try:
                with st.spinner("Generazione dei file CSV in corso..."):
                    export_manager.export_all_data_to_global_csvs(str(export_base_path))
                st.success(
                    f"Tutti i file CSV sono stati generati/aggiornati in:\n`{export_base_path.resolve()}`"
                )
                st.info(
                    "Puoi ora aprire la cartella esportazioni o creare un archivio ZIP."
                )
            except AttributeError as ae:
                st.error(
                    f"Errore: Funzionalità di esportazione non trovata ({ae}). Controllare 'export_manager.py'."
                )
                st.error(traceback.format_exc())
            except Exception as e:
                st.error(f"Errore critico durante la generazione dei CSV: {e}")
                st.error(traceback.format_exc())

    with col2:
        if st.button(
            "📦 Crea e Scarica Archivio ZIP",
            type="primary",
            key="generate_csv_and_zip_streamlit",
        ):
            export_base_path = Path(CSV_EXPORT_BASE_PATH)
            export_base_path.mkdir(parents=True, exist_ok=True)

            # Step 1: Ensure CSVs are generated or already exist
            try:
                with st.spinner(
                    "Verifica e generazione dei file CSV (se necessario)..."
                ):
                    # Check if any CSVs are missing. If so, regenerate all.
                    # This is a simple check; for more granular, one might list expected files.
                    # A more robust check would be to see if the key files from export_manager.GLOBAL_CSV_FILES exist.
                    expected_files = getattr(export_manager, "GLOBAL_CSV_FILES", None)
                    files_present = False
                    if expected_files:
                        files_present = all(
                            (export_base_path / fname).exists()
                            for fname in expected_files.values()
                        )

                    if not files_present:
                        st.write(
                            "Alcuni file CSV non trovati o cartella vuota. Rigenerazione di tutti i CSV..."
                        )
                        export_manager.export_all_data_to_global_csvs(
                            str(export_base_path)
                        )
                        st.write("Generazione CSV completata.")
                    else:
                        st.write("File CSV trovati.")
                st.success(f"File CSV pronti in `{export_base_path.resolve()}`.")

                # Step 2: Prepare the ZIP for download
                default_zip_name = f"kpi_global_data_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

                with st.spinner("Creazione dell'archivio ZIP..."):
                    success, zip_data_or_msg = export_manager.package_all_csvs_as_zip(
                        str(export_base_path),
                        str(
                            export_base_path / default_zip_name
                        ),  # Provide a path for on-server file saving
                        return_bytes_for_streamlit=True,  # Request bytes for download
                    )

                if success:
                    st.download_button(
                        label=f"Scarica {default_zip_name}",
                        data=zip_data_or_msg,  # This will be the bytes
                        file_name=default_zip_name,
                        mime="application/zip",
                    )
                    st.success(
                        f"Archivio '{default_zip_name}' pronto per il download. "
                        f"È stato salvato anche in `{export_base_path / default_zip_name}`."
                    )
                else:
                    st.error(
                        f"Errore durante la creazione dell'archivio ZIP: {zip_data_or_msg}"
                    )

            except AttributeError as ae:
                st.error(
                    f"Errore: Funzionalità di esportazione non trovata ({ae}). Controllare 'export_manager.py'."
                )
                st.error(traceback.format_exc())
            except Exception as e:
                st.error(f"Errore critico durante l'esportazione ZIP: {e}")
                st.error(traceback.format_exc())

    st.markdown("---")
    st.subheader("Accesso alla Cartella")
    if st.button(
        "📂 Apri Cartella Esportazioni Locale", key="open_export_folder_streamlit"
    ):
        # This button will only work effectively if Streamlit is running on the same machine
        # as the user's desktop environment, or if the path is a shared/network path
        # accessible by the user and the server.
        export_path_obj = Path(CSV_EXPORT_BASE_PATH).resolve()
        if not export_path_obj.exists():
            try:
                export_path_obj.mkdir(parents=True, exist_ok=True)
                st.info(
                    f"Cartella creata: `{export_path_obj}`. Genera i file CSV per popolarla."
                )
            except Exception as e_mkdir:
                st.error(
                    f"Impossibile creare la cartella `{export_path_obj}`: {e_mkdir}"
                )
                st.stop()  # Stop if we can't even create the directory

        st.markdown(
            f"Tentativo di aprire la cartella: `{export_path_obj}`."
            " Questa operazione potrebbe non funzionare a seconda di come è ospitata l'app Streamlit "
            "e delle autorizzazioni del browser."
        )
        try:
            if sys.platform == "win32":
                # os.startfile is for files, explorer is better for folders
                subprocess.Popen(f'explorer "{export_path_obj}"')
            elif sys.platform == "darwin":  # macOS
                subprocess.Popen(["open", str(export_path_obj)])
            else:  # Linux
                subprocess.Popen(["xdg-open", str(export_path_obj)])
            # Note: Streamlit cannot directly trigger a folder open dialog in the user's browser
            # due to security restrictions. This subprocess call works on the server side.
            # If running locally, it will open the folder on the local machine.
            # If running on a remote server, it attempts to open it on the server.
            st.success(
                f"Comando per aprire la cartella `{export_path_obj}` eseguito sul server."
            )
        except Exception as e:
            st.error(
                f"Impossibile eseguire il comando per aprire la cartella: {e}. Percorso: `{export_path_obj}`"
            )
# --- 🌍 Dashboard Globale KPI ---
with tab_global_dashboard:
    # We will implement this section below
    st.header("🌍 Dashboard Globale Target KPI")
    st.markdown(
        "Visualizza l'andamento dei target per tutti i KPI e stabilimenti, filtrato per anno e tipo di periodo."
    )

    # --- Filters ---
    dash_filter_col1, dash_filter_col2 = st.columns(2)

    with dash_filter_col1:
        if "dashboard_year" not in st.session_state:
            st.session_state.dashboard_year = str(datetime.datetime.now().year)

        year_options_dash = [
            str(y)
            for y in range(
                datetime.datetime.now().year - 5, datetime.datetime.now().year + 6
            )
        ]
        # Ensure current session state value is in options, or reset
        if st.session_state.dashboard_year not in year_options_dash:
            st.session_state.dashboard_year = str(datetime.datetime.now().year)

        try:
            default_year_index_dash = year_options_dash.index(
                st.session_state.dashboard_year
            )
        except (
            ValueError
        ):  # Fallback if current year somehow not in list (should not happen)
            default_year_index_dash = year_options_dash.index(
                str(datetime.datetime.now().year)
            )

        selected_year_dash = st.selectbox(
            "Seleziona Anno",
            options=year_options_dash,
            index=default_year_index_dash,
            key="dashboard_year_sb",  # session_state will be updated automatically by Streamlit
        )
        # st.session_state.dashboard_year = selected_year_dash # No need to set it again here, key does it

    with dash_filter_col2:
        if "dashboard_period_type" not in st.session_state:
            st.session_state.dashboard_period_type = "Mese"

        # Ensure current session state value is in options, or reset
        if st.session_state.dashboard_period_type not in PERIOD_TYPES_RESULTS:
            st.session_state.dashboard_period_type = "Mese"

        try:
            period_idx_dash = PERIOD_TYPES_RESULTS.index(
                st.session_state.dashboard_period_type
            )
        except ValueError:
            period_idx_dash = PERIOD_TYPES_RESULTS.index("Mese")  # Fallback

        selected_period_dash = st.selectbox(
            "Tipo Periodo di Visualizzazione",
            PERIOD_TYPES_RESULTS,
            index=period_idx_dash,
            key="dashboard_period_sb",  # session_state will be updated automatically
        )
        # st.session_state.dashboard_period_type = selected_period_dash # No need to set it again

    st.markdown("---")

    # --- Data Fetching and Chart Display based on current session state values ---
    try:
        year_to_fetch = int(st.session_state.dashboard_year)
        period_type_to_fetch = st.session_state.dashboard_period_type
    except ValueError:
        st.error("Anno selezionato non valido.")
        st.stop()
    except AttributeError:  # Handles if session_state keys are not set
        st.error(
            "Errore: Filtri non inizializzati correttamente. Ricarica la pagina o seleziona i filtri."
        )
        st.stop()

    with st.spinner(
        f"Caricamento dati dashboard per l'anno {year_to_fetch}, periodo {period_type_to_fetch}..."
    ):
        all_stabilimenti_dash = dr.get_all_stabilimenti(only_visible=True)
        all_kpis_dash = dr.get_all_kpis_detailed(only_visible=True)

        if not all_stabilimenti_dash:
            st.warning("Nessun stabilimento trovato (o visibile).")
            st.stop()
        if not all_kpis_dash:
            st.warning("Nessun KPI (con specifiche) trovato (o visibile).")
            st.stop()

        charts_rendered_count = 0
        for stab_row in all_stabilimenti_dash:
            stabilimento_id = stab_row["id"]
            stabilimento_name = stab_row["name"]

            with st.expander(f"🏢 Stabilimento: {stabilimento_name}", expanded=False):
                stab_has_charts = False
                for (
                    kpi_spec_row_sqlite
                ) in all_kpis_dash:  # kpi_spec_row_sqlite is sqlite3.Row
                    kpi_spec_row = dict(
                        kpi_spec_row_sqlite
                    )  # Convert to dict for easier/safer access

                    kpi_spec_id = kpi_spec_row.get("id")
                    if kpi_spec_id is None:
                        continue  # Should not happen if data is clean

                    kpi_display_name = get_kpi_display_name_st(kpi_spec_row)
                    kpi_unit_val = kpi_spec_row.get("unit_of_measure", "")

                    data_t1_dash = dr.get_periodic_targets_for_kpi(
                        year_to_fetch,
                        stabilimento_id,
                        kpi_spec_id,
                        period_type_to_fetch,
                        1,
                    )
                    data_t2_dash = dr.get_periodic_targets_for_kpi(
                        year_to_fetch,
                        stabilimento_id,
                        kpi_spec_id,
                        period_type_to_fetch,
                        2,
                    )

                    if not data_t1_dash and not data_t2_dash:
                        continue

                    stab_has_charts = True
                    charts_rendered_count += 1

                    chart_data_list = []
                    if data_t1_dash:
                        for row_t1 in data_t1_dash:
                            chart_data_list.append(
                                {
                                    "Periodo": row_t1["Periodo"],
                                    "Target": row_t1["Target"],
                                    "Target Number": "Target 1",
                                }
                            )
                    if data_t2_dash:
                        for row_t2 in data_t2_dash:
                            chart_data_list.append(
                                {
                                    "Periodo": row_t2["Periodo"],
                                    "Target": row_t2["Target"],
                                    "Target Number": "Target 2",
                                }
                            )

                    if not chart_data_list:
                        continue

                    df_chart = pd.DataFrame(chart_data_list)
                    df_chart["Target"] = pd.to_numeric(
                        df_chart["Target"], errors="coerce"
                    )
                    df_chart.dropna(subset=["Target"], inplace=True)

                    if df_chart.empty:
                        continue

                    if period_type_to_fetch == "Mese":
                        month_sorter = calendar.month_name[1:]
                        df_chart["Periodo"] = pd.Categorical(
                            df_chart["Periodo"], categories=month_sorter, ordered=True
                        )
                    elif period_type_to_fetch == "Trimestre":
                        q_sorter = ["Q1", "Q2", "Q3", "Q4"]
                        df_chart["Periodo"] = pd.Categorical(
                            df_chart["Periodo"], categories=q_sorter, ordered=True
                        )

                    df_chart.sort_values(["Periodo", "Target Number"], inplace=True)

                    st.markdown(
                        f"<h6>{kpi_display_name} ({kpi_unit_val if kpi_unit_val else 'N/D Unità'})</h6>",
                        unsafe_allow_html=True,
                    )
                    try:
                        st.line_chart(
                            df_chart,
                            x="Periodo",
                            y="Target",
                            color="Target Number",
                            height=250,
                        )
                    except (
                        Exception
                    ) as e_chart:  # Catch errors specific to charting this df
                        st.error(
                            f"Errore durante la creazione del grafico per {kpi_display_name}: {e_chart}"
                        )
                        print(
                            f"Plotting error for {kpi_display_name} (Stab: {stabilimento_name}, KPI ID: {kpi_spec_id}): {e_chart}"
                        )
                        # st.dataframe(df_chart) # Debug: show data if chart fails

                if not stab_has_charts:
                    st.caption(
                        f"Nessun dato target trovato per questo stabilimento per i filtri selezionati."
                    )

        if charts_rendered_count == 0:
            st.info(
                f"Nessun dato target trovato per l'anno {year_to_fetch} e periodo {period_type_to_fetch} per nessun KPI/Stabilimento."
            )
