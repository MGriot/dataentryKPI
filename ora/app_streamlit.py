import streamlit as st
import pandas as pd
import json
import datetime
import calendar
from pathlib import Path
import sqlite3
import sys  # For opening folders, similar to Tkinter's os.startfile
import subprocess  # For opening folders

# Import your existing modules
import database_manager as db_manager
import data_retriever as dr
import export_manager  # Assuming this module exists as per your Tkinter app
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
)


# --- Helper Function (from your Tkinter app) ---
def get_kpi_display_name(kpi_data_row):
    if not kpi_data_row:
        return "N/D (KPI Data Mancante)"
    try:
        # Assuming kpi_data_row is a dictionary or an object with dictionary-like access
        g_name = kpi_data_row.get("group_name", "N/G (No Group)")
        sg_name = kpi_data_row.get("subgroup_name", "N/S (No Subgroup)")
        i_name = kpi_data_row.get("indicator_name", "N/I (No Indicator)")
        g_name = g_name or "N/G (Nome Gruppo Vuoto)"
        sg_name = sg_name or "N/S (Nome Sottogruppo Vuoto)"
        i_name = i_name or "N/I (Nome Indicatore Vuoto)"
        return f"{g_name} > {sg_name} > {i_name}"
    except Exception as ex_general:
        st.error(f"Errore imprevisto in get_kpi_display_name: {ex_general}")
        return "N/D (Errore Display Nome Imprevisto)"


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
    st.session_state.editing_group_hier = None
    st.session_state.editing_subgroup_hier = None
    st.session_state.editing_indicator_hier = None

    # KPI Templates Tab
    st.session_state.selected_template_id_tpl = None
    st.session_state.editing_template_tpl = None
    st.session_state.selected_definition_id_tpl = None
    st.session_state.editing_definition_tpl = None

    # KPI Specs Tab
    st.session_state.spec_selected_group_name = ""
    st.session_state.spec_selected_subgroup_display_name = (
        ""  # Store display name as it appears in CB
    )
    st.session_state.spec_selected_indicator_name = ""
    st.session_state.current_editing_kpi_spec_id = None
    st.session_state.selected_indicator_id_for_spec = None  # actual_indicator_id

    # Master/Sub Link Tab
    st.session_state.ms_selected_kpi_spec_id = None
    st.session_state.ms_selected_sub_link_info = (
        None  # To store {sub_id, weight, display_text}
    )

    # Stabilimenti Tab
    st.session_state.editing_stabilimento = (
        None  # To store stabilimento data for editing
    )

    # Target Entry Tab
    st.session_state.target_year = str(datetime.datetime.now().year)
    st.session_state.target_stabilimento_id = None
    st.session_state.kpi_target_inputs = {}  # To store dynamic input values

    # Results Tab
    st.session_state.results_year = str(datetime.datetime.now().year)
    st.session_state.results_stabilimento_id = None
    st.session_state.results_period_type = "Mese"
    st.session_state.results_group_id = None
    st.session_state.results_subgroup_id = None
    st.session_state.results_indicator_actual_id = None  # Store actual_indicator_id

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
    "event_based_spikes_or_dips",  # Placeholder, needs custom handling for params
]
REPARTITION_LOGIC_OPTIONS = [
    REPARTITION_LOGIC_ANNO,
    REPARTITION_LOGIC_MESE,
    REPARTITION_LOGIC_TRIMESTRE,
    REPARTITION_LOGIC_SETTIMANA,
]
KPI_CALC_TYPE_OPTIONS = [CALC_TYPE_INCREMENTALE, CALC_TYPE_MEDIA]

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
    tab_export,
) = st.tabs(tab_titles)

# --- 🏭 Gestione Stabilimenti ---
with tab_stabilimenti:
    st.header("Gestione Stabilimenti")

    col1_stab, col2_stab = st.columns([2, 1.5])

    with col1_stab:
        st.subheader("Elenco Stabilimenti")
        stabilimenti_data = dr.get_all_stabilimenti()
        if stabilimenti_data:
            df_stabilimenti = pd.DataFrame([dict(row) for row in stabilimenti_data])
            df_stabilimenti_display = df_stabilimenti[["id", "name", "visible"]].copy()
            df_stabilimenti_display["visible"] = df_stabilimenti_display[
                "visible"
            ].apply(lambda x: "Sì" if x else "No")
            df_stabilimenti_display.rename(
                columns={"id": "ID", "name": "Nome", "visible": "Visibile"},
                inplace=True,
            )

            # st.dataframe returns None here, selection is in session_state via key
            st.dataframe(
                df_stabilimenti_display,
                on_select="rerun",  # Triggers a rerun, selection state is updated
                selection_mode="single-row",
                hide_index=True,
                key="stabilimenti_df_selection_state",  # Key to access selection state
            )

            # Access selection state from st.session_state
            selection_state = st.session_state.get("stabilimenti_df_selection_state")

            # Check if selection_state exists and has a non-empty "rows" list
            if selection_state and selection_state["selection"]["rows"]:
                selected_idx = selection_state["selection"]["rows"][0]
                # Check if selected_idx is within bounds of the original df_stabilimenti
                if 0 <= selected_idx < len(df_stabilimenti):
                    st.session_state.editing_stabilimento = df_stabilimenti.iloc[
                        selected_idx
                    ].to_dict()
                else:
                    # This case might happen if data changes and selection is stale, clear it
                    st.session_state.editing_stabilimento = None
            # If no selection is made after an interaction, "rows" will be empty.
            # We don't want to clear editing_stabilimento if it was set by a previous valid selection
            # and the current interaction didn't change the selection.
            # However, if the user explicitly deselects (if that were possible) or data changes,
            # then editing_stabilimento might need to be cleared or re-validated.
            # For single-row, 'rerun' will update this block. If rows is empty, editing_stabilimento won't be set/updated.

        else:
            st.info("Nessun stabilimento definito.")
            st.session_state.editing_stabilimento = (
                None  # Ensure it's cleared if no data
            )

    with col2_stab:
        st.subheader("Aggiungi/Modifica Stabilimento")

        form_key_stabilimento = "stabilimento_form_new"
        button_text_stabilimento = "Aggiungi Stabilimento"
        initial_name_stabilimento = ""
        initial_visible_stabilimento = True
        editing_id_stabilimento = None

        # Use the st.session_state.editing_stabilimento to populate the form
        current_editing_data = st.session_state.get("editing_stabilimento")
        if current_editing_data:
            form_key_stabilimento = (
                f"stabilimento_form_edit_{current_editing_data['id']}"
            )
            button_text_stabilimento = "Salva Modifiche"
            initial_name_stabilimento = current_editing_data["name"]
            initial_visible_stabilimento = bool(current_editing_data["visible"])
            editing_id_stabilimento = current_editing_data["id"]

        with st.form(key=form_key_stabilimento):
            stab_name = st.text_input(
                "Nome Stabilimento",
                value=initial_name_stabilimento,
                key=f"name_{form_key_stabilimento}",
            )
            stab_visible = st.checkbox(
                "Visibile per Inserimento Target",
                value=initial_visible_stabilimento,
                key=f"vis_{form_key_stabilimento}",
            )

            submitted_stabilimento = st.form_submit_button(button_text_stabilimento)

            if submitted_stabilimento:
                if not stab_name.strip():
                    st.error("Il nome dello stabilimento è obbligatorio.")
                else:
                    try:
                        if editing_id_stabilimento is not None:
                            db_manager.update_stabilimento(
                                editing_id_stabilimento, stab_name.strip(), stab_visible
                            )
                            st.success(
                                f"Stabilimento '{stab_name.strip()}' aggiornato."
                            )
                        else:
                            db_manager.add_stabilimento(stab_name.strip(), stab_visible)
                            st.success(f"Stabilimento '{stab_name.strip()}' aggiunto.")
                        st.session_state.editing_stabilimento = (
                            None  # Clear editing state
                        )
                        st.session_state.stabilimenti_df_selection_state = {
                            "selection": {"rows": []}
                        }  # Clear selection in dataframe
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(
                            f"Errore: Stabilimento '{stab_name.strip()}' esiste già."
                        )
                    except Exception as e:
                        st.error(f"Errore durante il salvataggio: {e}")

        if current_editing_data:  # Check if we are in edit mode
            if st.button("Pulisci / Nuovo Stabilimento"):
                st.session_state.editing_stabilimento = None
                st.session_state.stabilimenti_df_selection_state = {
                    "selection": {"rows": []}
                }  # Clear selection in dataframe
                st.rerun()

# --- 🗂️ Gestione Gerarchia KPI ---
with tab_hierarchy:
    st.header("Gestione Gerarchia KPI")

    # Fetch data
    groups = dr.get_kpi_groups()
    groups_map = {g["name"]: g["id"] for g in groups}
    group_names = [""] + list(groups_map.keys())  # Add a blank option

    col1_hier, col2_hier, col3_hier = st.columns(3)

    # --- Groups Column ---
    with col1_hier:
        st.subheader("Gruppi KPI")
        selected_group_name_hier = st.selectbox(
            "Seleziona Gruppo",
            group_names,
            index=0,
            key="sb_group_hier",
            on_change=lambda: setattr(
                st.session_state, "selected_subgroup_id_hier", None
            )
            or setattr(st.session_state, "selected_indicator_id_hier", None),
        )
        st.session_state.selected_group_id_hier = groups_map.get(
            selected_group_name_hier
        )

        # CRUD for Groups
        with st.expander("Gestisci Gruppi"):
            with st.form("group_form", clear_on_submit=True):
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
                st.write(f"**Modifica/Elimina Gruppo: {selected_group_name_hier}**")

                with st.form(
                    f"edit_group_form_{st.session_state.selected_group_id_hier}"
                ):
                    edited_group_name = st.text_input(
                        "Nuovo Nome Gruppo", value=selected_group_name_hier
                    )
                    update_group_submitted = st.form_submit_button(
                        "Modifica Nome Gruppo"
                    )
                    if (
                        update_group_submitted
                        and edited_group_name
                        and edited_group_name != selected_group_name_hier
                    ):
                        try:
                            db_manager.update_kpi_group(
                                st.session_state.selected_group_id_hier,
                                edited_group_name,
                            )
                            st.success(f"Gruppo rinominato in '{edited_group_name}'.")
                            st.session_state.selected_group_id_hier = (
                                None  # Force re-selection
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore modifica gruppo: {e}")

                if st.button(
                    "Elimina Gruppo Selezionato",
                    type="primary",
                    key=f"del_group_{st.session_state.selected_group_id_hier}",
                ):
                    if st.session_state.selected_group_id_hier:
                        try:
                            # Confirmation could be added here
                            db_manager.delete_kpi_group(
                                st.session_state.selected_group_id_hier
                            )
                            st.success(
                                f"Gruppo '{selected_group_name_hier}' eliminato."
                            )
                            st.session_state.selected_group_id_hier = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore eliminazione gruppo: {e}")

    # --- Subgroups Column ---
    with col2_hier:
        st.subheader("Sottogruppi KPI")
        subgroups_map = {}
        subgroup_display_names = [""]
        if st.session_state.selected_group_id_hier:
            subgroups = dr.get_kpi_subgroups_by_group_revised(
                st.session_state.selected_group_id_hier
            )
            for sg in subgroups:
                display_name = sg["name"] + (
                    f" (Tpl: {sg['template_name']})" if sg.get("template_name") else ""
                )
                subgroups_map[display_name] = sg["id"]
                subgroup_display_names.append(display_name)

        selected_subgroup_display_name_hier = st.selectbox(
            "Seleziona Sottogruppo",
            subgroup_display_names,
            index=0,
            key="sb_subgroup_hier",
            disabled=not bool(st.session_state.selected_group_id_hier),
            on_change=lambda: setattr(
                st.session_state, "selected_indicator_id_hier", None
            ),
        )
        st.session_state.selected_subgroup_id_hier = subgroups_map.get(
            selected_subgroup_display_name_hier
        )

        # Helper to get raw subgroup name and template details
        current_subgroup_details_hier = None
        if (
            st.session_state.selected_subgroup_id_hier and subgroups
        ):  # Ensure subgroups list is populated
            current_subgroup_details_hier = next(
                (
                    sg
                    for sg in subgroups
                    if sg["id"] == st.session_state.selected_subgroup_id_hier
                ),
                None,
            )

        # CRUD for Subgroups
        with st.expander("Gestisci Sottogruppi"):
            if st.session_state.selected_group_id_hier:
                templates = dr.get_kpi_indicator_templates()
                templates_map_hier = {"(Nessuno)": None}
                templates_map_hier.update({tpl["name"]: tpl["id"] for tpl in templates})

                with st.form("subgroup_form", clear_on_submit=True):
                    new_subgroup_name = st.text_input("Nome Nuovo Sottogruppo")
                    selected_template_name_for_new_sg = st.selectbox(
                        "Template per Nuovo Sottogruppo",
                        list(templates_map_hier.keys()),
                    )
                    add_subgroup_submitted = st.form_submit_button(
                        "Aggiungi Sottogruppo"
                    )

                    if add_subgroup_submitted and new_subgroup_name:
                        try:
                            template_id_for_new_sg = templates_map_hier[
                                selected_template_name_for_new_sg
                            ]
                            db_manager.add_kpi_subgroup(
                                new_subgroup_name,
                                st.session_state.selected_group_id_hier,
                                template_id_for_new_sg,
                            )
                            st.success(f"Sottogruppo '{new_subgroup_name}' aggiunto.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore aggiunta sottogruppo: {e}")

                if current_subgroup_details_hier:
                    st.markdown("---")
                    st.write(
                        f"**Modifica/Elimina Sottogruppo: {current_subgroup_details_hier['name']}**"
                    )

                    with st.form(
                        f"edit_subgroup_form_{current_subgroup_details_hier['id']}"
                    ):
                        edited_subgroup_name = st.text_input(
                            "Nuovo Nome Sottogruppo",
                            value=current_subgroup_details_hier["name"],
                        )

                        current_tpl_id = current_subgroup_details_hier.get(
                            "indicator_template_id"
                        )
                        current_tpl_name_for_edit = next(
                            (
                                name
                                for name, id_val in templates_map_hier.items()
                                if id_val == current_tpl_id
                            ),
                            "(Nessuno)",
                        )

                        edited_template_name_for_sg = st.selectbox(
                            "Nuovo Template per Sottogruppo",
                            list(templates_map_hier.keys()),
                            index=list(templates_map_hier.keys()).index(
                                current_tpl_name_for_edit
                            ),
                        )

                        update_subgroup_submitted = st.form_submit_button(
                            "Modifica Sottogruppo"
                        )
                        if update_subgroup_submitted:
                            new_template_id_for_edit = templates_map_hier[
                                edited_template_name_for_sg
                            ]
                            if edited_subgroup_name != current_subgroup_details_hier[
                                "name"
                            ] or new_template_id_for_edit != current_subgroup_details_hier.get(
                                "indicator_template_id"
                            ):
                                try:
                                    db_manager.update_kpi_subgroup(
                                        current_subgroup_details_hier["id"],
                                        edited_subgroup_name,
                                        st.session_state.selected_group_id_hier,
                                        new_template_id_for_edit,
                                    )
                                    st.success(
                                        f"Sottogruppo '{edited_subgroup_name}' aggiornato."
                                    )
                                    st.session_state.selected_subgroup_id_hier = (
                                        None  # Force re-selection
                                    )
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Errore modifica sottogruppo: {e}")

                    if st.button(
                        "Elimina Sottogruppo Selezionato",
                        type="primary",
                        key=f"del_subg_{current_subgroup_details_hier['id']}",
                    ):
                        try:
                            db_manager.delete_kpi_subgroup(
                                current_subgroup_details_hier["id"]
                            )
                            st.success(
                                f"Sottogruppo '{current_subgroup_details_hier['name']}' eliminato."
                            )
                            st.session_state.selected_subgroup_id_hier = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore eliminazione sottogruppo: {e}")
            else:
                st.info("Seleziona un gruppo per gestire i sottogruppi.")

    # --- Indicators Column ---
    with col3_hier:
        st.subheader("Indicatori KPI")
        indicators_map = {}
        indicator_names = [""]
        is_templated_subgroup = False

        if current_subgroup_details_hier:  # Use the fetched details
            is_templated_subgroup = (
                current_subgroup_details_hier.get("indicator_template_id") is not None
            )
            indicators = dr.get_kpi_indicators_by_subgroup(
                current_subgroup_details_hier["id"]
            )
            for ind in indicators:
                indicators_map[ind["name"]] = ind["id"]
                indicator_names.append(ind["name"])

        selected_indicator_name_hier = st.selectbox(
            "Seleziona Indicatore",
            indicator_names,
            index=0,
            key="sb_indicator_hier",
            disabled=not bool(st.session_state.selected_subgroup_id_hier),
        )
        st.session_state.selected_indicator_id_hier = indicators_map.get(
            selected_indicator_name_hier
        )

        # CRUD for Indicators
        with st.expander("Gestisci Indicatori"):
            if st.session_state.selected_subgroup_id_hier:
                if is_templated_subgroup:
                    st.info(
                        "Gli indicatori per questo sottogruppo sono gestiti dal template associato."
                    )
                else:  # Only allow direct add/edit/delete if not templated
                    with st.form("indicator_form", clear_on_submit=True):
                        new_indicator_name = st.text_input("Nome Nuovo Indicatore")
                        add_indicator_submitted = st.form_submit_button(
                            "Aggiungi Indicatore"
                        )
                        if add_indicator_submitted and new_indicator_name:
                            try:
                                db_manager.add_kpi_indicator(
                                    new_indicator_name,
                                    st.session_state.selected_subgroup_id_hier,
                                )
                                st.success(
                                    f"Indicatore '{new_indicator_name}' aggiunto."
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore aggiunta indicatore: {e}")

                    if st.session_state.selected_indicator_id_hier:
                        st.markdown("---")
                        st.write(
                            f"**Modifica/Elimina Indicatore: {selected_indicator_name_hier}**"
                        )

                        with st.form(
                            f"edit_indicator_form_{st.session_state.selected_indicator_id_hier}"
                        ):
                            edited_indicator_name = st.text_input(
                                "Nuovo Nome Indicatore",
                                value=selected_indicator_name_hier,
                            )
                            update_indicator_submitted = st.form_submit_button(
                                "Modifica Nome Indicatore"
                            )
                            if (
                                update_indicator_submitted
                                and edited_indicator_name
                                and edited_indicator_name
                                != selected_indicator_name_hier
                            ):
                                try:
                                    db_manager.update_kpi_indicator(
                                        st.session_state.selected_indicator_id_hier,
                                        edited_indicator_name,
                                        st.session_state.selected_subgroup_id_hier,
                                    )
                                    st.success(
                                        f"Indicatore rinominato in '{edited_indicator_name}'."
                                    )
                                    st.session_state.selected_indicator_id_hier = (
                                        None  # Force re-selection
                                    )
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Errore modifica indicatore: {e}")

                        if st.button(
                            "Elimina Indicatore Selezionato",
                            type="primary",
                            key=f"del_ind_{st.session_state.selected_indicator_id_hier}",
                        ):
                            try:
                                db_manager.delete_kpi_indicator(
                                    st.session_state.selected_indicator_id_hier
                                )
                                st.success(
                                    f"Indicatore '{selected_indicator_name_hier}' eliminato."
                                )
                                st.session_state.selected_indicator_id_hier = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore eliminazione indicatore: {e}")
            else:
                st.info("Seleziona un sottogruppo per gestire gli indicatori.")

# --- 📋 Gestione Template Indicatori ---
with tab_templates:
    st.header("Gestione Template Indicatori KPI")
    # This tab would follow a similar pattern to Stabilimenti and KPI Hierarchy:
    # - Display templates in a list/selectbox.
    # - On selection, display its defined indicators in a table (st.dataframe).
    # - Forms for CRUD operations on templates and their definitions.
    # - Dialogs (implemented as forms or st.popover) for adding/editing.
    st.info("Implementazione per 'Gestione Template Indicatori' in corso.")
    # Example structure:
    # col1_tpl, col2_tpl = st.columns([1,2])
    # with col1_tpl:
    #     display templates
    # with col2_tpl:
    #     display definitions of selected template
    #     forms for CRUD


# --- ⚙️ Gestione Specifiche KPI ---
with tab_specs:
    st.header("Gestione Specifiche KPI")
    st.info("Implementazione per 'Gestione Specifiche KPI' in corso.")
    # - Comboboxes for Group > Subgroup > Indicator selection.
    # - Input fields for Description, Calc Type, Unit, Visible.
    # - On Indicator selection, load existing spec or prepare for new.
    # - A table (st.dataframe) to show all existing KPI specs.
    # - Double-click/selection on table row loads spec for editing.


# --- 🔗 Gestione Link Master/Sub ---
with tab_links:
    st.header("Gestione Link Master/Sub KPI")
    st.info("Implementazione per 'Gestione Link Master/Sub' in corso.")
    # - Display all KPI specs in a table with their current role.
    # - On selection, show:
    #   - If master: list of sub-KPIs it manages (with weights). Buttons to link new sub, edit weight, unlink.
    #   - If sub: the master KPI it's managed by (with its weight).
    # - Dialogs (forms/popovers) for linking sub-KPIs and setting/editing weights.

# --- 🎯 Inserimento Target ---
with tab_target:
    st.header("Inserimento Target Annuali e Ripartizione")

    # --- Callback to load/reset KPI target inputs when filters change ---
    def load_kpi_data_for_target_entry():
        st.session_state.kpi_target_inputs = {}  # Reset previous inputs
        year_str = st.session_state.get(
            "target_year_sb", str(datetime.datetime.now().year)
        )
        stab_name = st.session_state.get("target_stab_sb")

        if not year_str or not stab_name:
            return

        try:
            year = int(year_str)
            stabilimento_id = stabilimenti_map_target_ui.get(stab_name)
            if stabilimento_id is None:
                return
        except ValueError:
            return

        kpis_for_entry = dr.get_all_kpis_detailed(only_visible=True)
        if not kpis_for_entry:
            return

        for kpi_data_dict in kpis_for_entry:
            kpi_spec_id = kpi_data_dict["id"]
            if kpi_spec_id is None:
                continue

            existing_target_db_row = dr.get_annual_target_entry(
                year, stabilimento_id, kpi_spec_id
            )
            kpi_role_details = dr.get_kpi_role_details(kpi_spec_id)

            # Default values
            def_t1, def_t2 = 0.0, 0.0
            def_profile = PROFILE_ANNUAL_PROGRESSIVE
            def_logic = REPARTITION_LOGIC_ANNO
            def_repart_values_from_db = (
                {}
            )  # Raw from DB, might include weekly_json/event_json
            def_profile_params_from_db = {}
            def_is_manual1, def_is_manual2 = True, True  # Default to manual

            if existing_target_db_row:
                def_t1 = float(existing_target_db_row.get("annual_target1", 0.0) or 0.0)
                def_t2 = float(existing_target_db_row.get("annual_target2", 0.0) or 0.0)
                db_profile_val = existing_target_db_row.get("distribution_profile")
                if db_profile_val and db_profile_val in DISTRIBUTION_PROFILE_OPTIONS:
                    def_profile = db_profile_val
                def_logic = (
                    existing_target_db_row.get(
                        "repartition_logic", REPARTITION_LOGIC_ANNO
                    )
                    or REPARTITION_LOGIC_ANNO
                )
                def_is_manual1 = bool(
                    existing_target_db_row.get("is_target1_manual", True)
                )
                def_is_manual2 = bool(
                    existing_target_db_row.get("is_target2_manual", True)
                )
                try:
                    def_repart_values_from_db = json.loads(
                        existing_target_db_row.get("repartition_values", "{}") or "{}"
                    )
                except json.JSONDecodeError:
                    st.warning(
                        f"JSON repartition_values non valido per KPI {kpi_spec_id} (ID Spec). Uso default."
                    )
                try:
                    def_profile_params_from_db = json.loads(
                        existing_target_db_row.get("profile_params", "{}") or "{}"
                    )
                except json.JSONDecodeError:
                    st.warning(
                        f"JSON profile_params non valido per KPI {kpi_spec_id} (ID Spec). Uso default."
                    )

            # Store in session state for UI binding
            st.session_state.kpi_target_inputs[kpi_spec_id] = {
                "target1": def_t1,
                "target2": def_t2,
                "is_manual1": def_is_manual1,
                "is_manual2": def_is_manual2,
                "profile": def_profile,
                "logic": def_logic,
                "repartition_values_raw": def_repart_values_from_db,  # Store raw values from DB
                "profile_params_raw": def_profile_params_from_db,  # Store raw profile params from DB
                # UI specific or helper values
                "calc_type": kpi_data_dict["calculation_type"],
                "unit_of_measure": kpi_data_dict.get("unit_of_measure", ""),
                "is_sub_kpi": kpi_role_details["role"] == "sub",
                "master_kpi_id": kpi_role_details.get("master_id"),
                "is_master_kpi": kpi_role_details["role"] == "master",
                "sub_kpis_with_weights": [],  # Will be populated for masters later
                "display_name": get_kpi_display_name(
                    kpi_data_dict
                ),  # For easier reference
            }
            # If it's a master, fetch its subs and their weights for UI logic
            if st.session_state.kpi_target_inputs[kpi_spec_id]["is_master_kpi"]:
                sub_ids_raw = dr.get_sub_kpis_for_master(kpi_spec_id)
                if sub_ids_raw:
                    with sqlite3.connect(
                        db_manager.DB_KPIS
                    ) as conn_weights:  # Use db_manager.DB_KPIS
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
        # After loading all, trigger initial distribution for masters
        initial_master_sub_ui_distribution_st()

    # --- Filters ---
    target_filter_cols = st.columns([1, 2, 1])  # Adjusted column ratios
    with target_filter_cols[0]:
        current_year = int(
            st.session_state.get("target_year_sb", datetime.datetime.now().year)
        )
        year_options = list(
            range(datetime.datetime.now().year - 5, datetime.datetime.now().year + 6)
        )
        try:
            default_year_index = year_options.index(current_year)
        except ValueError:
            default_year_index = (
                5  # Fallback to current year if saved year is out of new range
            )

        st.selectbox(
            "Anno",
            options=year_options,
            index=default_year_index,
            key="target_year_sb",
            on_change=load_kpi_data_for_target_entry,  # Load data when year changes
        )

    stabilimenti_all_target = dr.get_all_stabilimenti(only_visible=True)
    stabilimenti_map_target_ui = {s["name"]: s["id"] for s in stabilimenti_all_target}
    stabilimenti_names_target = [""] + list(stabilimenti_map_target_ui.keys())

    with target_filter_cols[1]:
        st.selectbox(
            "Stabilimento",
            stabilimenti_names_target,
            key="target_stab_sb",
            on_change=load_kpi_data_for_target_entry,  # Load data when stabilimento changes
        )

    with target_filter_cols[2]:
        st.button(
            "Ricarica Dati Target",
            on_click=load_kpi_data_for_target_entry,
            use_container_width=True,
            key="reload_target_data_button",
        )

    # --- Display KPI Target Entry Fields ---
    year_str_for_display = st.session_state.get("target_year_sb")
    stab_name_for_display = st.session_state.get("target_stab_sb")

    if (
        year_str_for_display
        and stab_name_for_display
        and st.session_state.get("kpi_target_inputs")
    ):
        st.markdown("---")
        st.subheader(
            f"Target per {stab_name_for_display} - Anno {year_str_for_display}"
        )

        # Ensure kpi_target_inputs is populated if it's empty but should have data
        if not st.session_state.kpi_target_inputs and dr.get_all_kpis_detailed(
            only_visible=True
        ):
            load_kpi_data_for_target_entry()  # Attempt to load if empty

        # Sort KPIs for consistent display order (e.g., by display name)
        sorted_kpi_ids = sorted(
            st.session_state.kpi_target_inputs.keys(),
            key=lambda kpi_id: st.session_state.kpi_target_inputs[kpi_id].get(
                "display_name", str(kpi_id)
            ),
        )

        for kpi_spec_id in sorted_kpi_ids:
            kpi_session_data = st.session_state.kpi_target_inputs[kpi_spec_id]
            exp_label = f"{kpi_session_data.get('display_name', 'KPI N/D')} (ID Spec: {kpi_spec_id}, Unità: {kpi_session_data.get('unit_of_measure', 'N/D')}, Tipo: {kpi_session_data.get('calc_type', 'N/D')})"

            # Determine expander border color based on manual/derived status (conceptual)
            # Streamlit doesn't directly support border colors for expanders in the same way.
            # We can use emojis or text prefixes in the label instead.
            prefix = ""
            if kpi_session_data.get("is_sub_kpi"):
                if not kpi_session_data.get(
                    "is_manual1", True
                ) or not kpi_session_data.get("is_manual2", True):
                    prefix = "⚙️ (Derivato) "  # Indicates at least one target is derived
                else:
                    prefix = "✏️ (Manuale) "

            with st.expander(prefix + exp_label):
                # Unique keys for all widgets inside the loop are crucial
                key_base = f"kpi_{kpi_spec_id}"

                # --- Callbacks for Master/Sub UI updates ---
                def on_master_target_ui_change(master_id, target_num):
                    # This function will be more complex, similar to Tkinter's _distribute_master_target_to_subs_ui
                    # It needs to iterate through st.session_state.kpi_target_inputs, find subs of master_id,
                    # and update their target1/target2 values if not manual.
                    # Crucially, it must NOT call st.rerun() directly if it's an on_change callback.
                    # Changes to session_state will automatically trigger a rerun.
                    if st.session_state.get("_master_sub_update_active_st", False):
                        return

                    st.session_state._master_sub_update_active_st = True
                    try:
                        master_data = st.session_state.kpi_target_inputs.get(master_id)
                        if not master_data or not master_data.get("is_master_kpi"):
                            return

                        master_target_val_key = f"target{target_num}"
                        master_target_val = master_data.get(master_target_val_key, 0.0)

                        sum_manual_sub_targets = 0.0
                        non_manual_subs_for_dist = []
                        total_weight_for_dist = 0.0

                        for sub_info in master_data.get("sub_kpis_with_weights", []):
                            sub_id = sub_info["sub_kpi_spec_id"]
                            sub_weight = sub_info.get("weight", 1.0)
                            sub_data = st.session_state.kpi_target_inputs.get(sub_id)

                            if sub_data and sub_data.get("is_sub_kpi"):
                                sub_is_manual_key = f"is_manual{target_num}"
                                sub_target_val_key = f"target{target_num}"
                                if sub_data.get(
                                    sub_is_manual_key, True
                                ):  # Default to manual if key missing
                                    sum_manual_sub_targets += sub_data.get(
                                        sub_target_val_key, 0.0
                                    )
                                else:
                                    non_manual_subs_for_dist.append(
                                        {"id": sub_id, "weight": sub_weight}
                                    )
                                    total_weight_for_dist += sub_weight

                        remaining_target_for_dist = (
                            master_target_val - sum_manual_sub_targets
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
                                remaining_target_for_dist != 0
                                and len(non_manual_subs_for_dist) > 0
                            ):
                                value_for_this_sub = remaining_target_for_dist / len(
                                    non_manual_subs_for_dist
                                )

                            if sub_id_update in st.session_state.kpi_target_inputs:
                                st.session_state.kpi_target_inputs[sub_id_update][
                                    f"target{target_num}"
                                ] = round(value_for_this_sub, 2)
                    finally:
                        st.session_state._master_sub_update_active_st = False

                def on_sub_manual_flag_ui_change(sub_id, target_num):
                    if st.session_state.get("_master_sub_update_active_st", False):
                        return

                    sub_data = st.session_state.kpi_target_inputs.get(sub_id)
                    if (
                        sub_data
                        and sub_data.get("is_sub_kpi")
                        and sub_data.get("master_kpi_id")
                    ):
                        master_id = sub_data["master_kpi_id"]
                        # Call the master target change handler to re-evaluate distribution for that master
                        # This will effectively rerun the distribution logic based on the new manual state
                        on_master_target_ui_change(master_id, target_num)

                # --- Target Value Inputs & Manual Flags ---
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    st.number_input(
                        "Target 1",
                        value=float(
                            kpi_session_data.get("target1", 0.0)
                        ),  # Ensure float for number_input
                        key=f"{key_base}_target1",
                        format="%.2f",
                        disabled=kpi_session_data.get("is_sub_kpi")
                        and not kpi_session_data.get("is_manual1", True),
                        on_change=(
                            on_master_target_ui_change
                            if kpi_session_data.get("is_master_kpi")
                            else None
                        ),
                        args=(
                            (kpi_spec_id, 1)
                            if kpi_session_data.get("is_master_kpi")
                            else None
                        ),
                    )
                    if kpi_session_data.get("is_sub_kpi"):
                        st.checkbox(
                            "Manuale T1",
                            value=kpi_session_data.get("is_manual1", True),
                            key=f"{key_base}_is_manual1",
                            on_change=on_sub_manual_flag_ui_change,
                            args=(kpi_spec_id, 1),
                        )
                with col_t2:
                    st.number_input(
                        "Target 2",
                        value=float(
                            kpi_session_data.get("target2", 0.0)
                        ),  # Ensure float
                        key=f"{key_base}_target2",
                        format="%.2f",
                        disabled=kpi_session_data.get("is_sub_kpi")
                        and not kpi_session_data.get("is_manual2", True),
                        on_change=(
                            on_master_target_ui_change
                            if kpi_session_data.get("is_master_kpi")
                            else None
                        ),
                        args=(
                            (kpi_spec_id, 2)
                            if kpi_session_data.get("is_master_kpi")
                            else None
                        ),
                    )
                    if kpi_session_data.get("is_sub_kpi"):
                        st.checkbox(
                            "Manuale T2",
                            value=kpi_session_data.get("is_manual2", True),
                            key=f"{key_base}_is_manual2",
                            on_change=on_sub_manual_flag_ui_change,
                            args=(kpi_spec_id, 2),
                        )

                # --- Distribution Profile & Repartition Logic ---
                st.selectbox(
                    "Profilo Distribuzione",
                    options=DISTRIBUTION_PROFILE_OPTIONS,
                    index=DISTRIBUTION_PROFILE_OPTIONS.index(
                        kpi_session_data.get("profile", PROFILE_ANNUAL_PROGRESSIVE)
                    ),
                    key=f"{key_base}_profile",
                    # on_change will trigger re-render of repartition inputs
                )

                # --- Conditional Repartition Inputs ---
                # This needs to mirror the logic from _update_repartition_input_area_tk
                current_profile = st.session_state.get(
                    f"{key_base}_profile", kpi_session_data.get("profile")
                )
                show_logic_radios_st = True
                effective_logic_for_db_st = st.session_state.get(
                    f"{key_base}_logic", kpi_session_data.get("logic")
                )

                if current_profile in [
                    PROFILE_ANNUAL_PROGRESSIVE,
                    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
                    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
                    PROFILE_EVEN,
                    "event_based_spikes_or_dips",
                ]:
                    show_logic_radios_st = False
                    # effective_logic_for_db_st = REPARTITION_LOGIC_ANNO # This will be set if logic widget is hidden
                # Add other profile-specific logic adjustments here if needed, similar to Tkinter version

                if show_logic_radios_st:
                    st.selectbox(  # Using selectbox instead of radio for compactness
                        "Logica Rip. Valori",
                        options=REPARTITION_LOGIC_OPTIONS,
                        index=REPARTITION_LOGIC_OPTIONS.index(
                            effective_logic_for_db_st
                        ),
                        key=f"{key_base}_logic",
                    )

                # Update effective_logic_for_db_st based on current selections
                effective_logic_for_db_st = st.session_state.get(
                    f"{key_base}_logic", kpi_session_data.get("logic")
                )
                if not show_logic_radios_st:  # If logic is hidden, it's ANNO
                    effective_logic_for_db_st = REPARTITION_LOGIC_ANNO

                # --- Repartition Value Inputs ---
                repart_values_ui = {}  # To hold values for current UI render
                raw_repart_db_vals = kpi_session_data.get("repartition_values_raw", {})

                if (
                    effective_logic_for_db_st == REPARTITION_LOGIC_MESE
                    and show_logic_radios_st
                ):
                    st.markdown("###### Valori Mensili (%)")
                    month_cols = st.columns(4)
                    months = [calendar.month_name[i] for i in range(1, 13)]
                    for i, month_name in enumerate(months):
                        with month_cols[i % 4]:
                            default_month_val = raw_repart_db_vals.get(
                                month_name,
                                (
                                    round(100 / 12, 2)
                                    if kpi_session_data.get("calc_type")
                                    == CALC_TYPE_INCREMENTALE
                                    else 100.0
                                ),
                            )
                            repart_values_ui[month_name] = st.number_input(
                                month_name[:3],
                                value=float(default_month_val),
                                format="%.2f",
                                key=f"{key_base}_month_{i}",
                            )
                elif (
                    effective_logic_for_db_st == REPARTITION_LOGIC_TRIMESTRE
                    and show_logic_radios_st
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
                            repart_values_ui[q_name] = st.number_input(
                                q_name,
                                value=float(default_q_val),
                                format="%.2f",
                                key=f"{key_base}_q_{i}",
                            )
                elif (
                    effective_logic_for_db_st == REPARTITION_LOGIC_SETTIMANA
                    and show_logic_radios_st
                ):
                    st.markdown("###### Valori Settimanali (JSON)")
                    default_weekly_json = (
                        json.dumps(raw_repart_db_vals, indent=2)
                        if isinstance(raw_repart_db_vals, dict)
                        and any(k.count("-W") > 0 for k in raw_repart_db_vals.keys())
                        else json.dumps({"Info": 'Es: {"2024-W01": 2.5}'}, indent=2)
                    )
                    repart_values_ui["weekly_json"] = st.text_area(
                        "JSON Settimanale",
                        value=default_weekly_json,
                        height=100,
                        key=f"{key_base}_weekly_json",
                    )

                # Event-based spikes (always potentially show if profile selected, regardless of logic_radios)
                if current_profile == "event_based_spikes_or_dips":
                    st.markdown("###### Parametri Eventi (JSON)")
                    raw_profile_params = kpi_session_data.get("profile_params_raw", {})
                    default_event_json = json.dumps(
                        raw_profile_params.get(
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
                    repart_values_ui["event_json"] = st.text_area(
                        "JSON Eventi",
                        value=default_event_json,
                        height=120,
                        key=f"{key_base}_event_json",
                    )

                # Update session state with current UI inputs for repartition_values
                # This ensures that when save is clicked, these current UI values are captured
                # This needs to be done carefully to avoid overwriting unrelated parts of kpi_target_inputs
                # For simplicity in this step, we'll assume save function will read directly from st.session_state widget keys.
                # A more robust way would be to have an on_change for each repartition input that updates
                # a structured dict in st.session_state.kpi_target_inputs[kpi_spec_id]['repartition_values_ui_capture']

        # --- Save All Button ---
        st.markdown("---")
        if st.button("SALVA TUTTI I TARGET", type="primary", use_container_width=True):
            year_to_save = int(st.session_state.get("target_year_sb"))
            stab_name_to_save = st.session_state.get("target_stab_sb")
            stab_id_to_save = stabilimenti_map_target_ui.get(stab_name_to_save)

            if not year_to_save or stab_id_to_save is None:
                st.error("Anno o Stabilimento non validi per il salvataggio.")
            else:
                targets_to_save_for_db = {}
                all_inputs_valid_save = True

                for (
                    kpi_id_save,
                    kpi_data_sess_save,
                ) in st.session_state.kpi_target_inputs.items():
                    key_base_save = f"kpi_{kpi_id_save}"
                    try:
                        t1_val_save = st.session_state[f"{key_base_save}_target1"]
                        t2_val_save = st.session_state[f"{key_base_save}_target2"]
                    except (
                        KeyError
                    ):  # Widget might not have rendered if conditions not met
                        st.warning(
                            f"Dati target mancanti per KPI ID {kpi_id_save} nella UI. Salto."
                        )
                        continue  # Skip this KPI if its primary target inputs aren't in session_state
                    except Exception as e_val:
                        st.error(
                            f"Errore lettura target per KPI {kpi_data_sess_save.get('display_name', kpi_id_save)}: {e_val}"
                        )
                        all_inputs_valid_save = False
                        break

                    profile_save = st.session_state.get(
                        f"{key_base_save}_profile", kpi_data_sess_save.get("profile")
                    )

                    is_manual1_save = True
                    is_manual2_save = True
                    if kpi_data_sess_save.get("is_sub_kpi"):
                        is_manual1_save = st.session_state.get(
                            f"{key_base_save}_is_manual1", True
                        )
                        is_manual2_save = st.session_state.get(
                            f"{key_base_save}_is_manual2", True
                        )

                    # Determine effective logic and repartition values for DB
                    repart_values_for_db_save = {}
                    profile_params_for_db_save = {}

                    show_logic_radios_save = True
                    if profile_save in [
                        PROFILE_ANNUAL_PROGRESSIVE,
                        PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
                        PROFILE_TRUE_ANNUAL_SINUSOIDAL,
                        PROFILE_EVEN,
                        "event_based_spikes_or_dips",
                    ]:
                        show_logic_radios_save = False

                    effective_logic_db_save = REPARTITION_LOGIC_ANNO  # Default
                    if show_logic_radios_save:
                        effective_logic_db_save = st.session_state.get(
                            f"{key_base_save}_logic", kpi_data_sess_save.get("logic")
                        )

                    # Collect repartition values based on effective_logic_db_save
                    if (
                        effective_logic_db_save == REPARTITION_LOGIC_MESE
                        and show_logic_radios_save
                    ):
                        months_save = [calendar.month_name[i] for i in range(1, 13)]
                        current_sum_percent = 0
                        for i, month_name_save in enumerate(months_save):
                            val = st.session_state.get(
                                f"{key_base_save}_month_{i}", 0.0
                            )
                            repart_values_for_db_save[month_name_save] = val
                            current_sum_percent += val
                        if (
                            kpi_data_sess_save.get("calc_type")
                            == CALC_TYPE_INCREMENTALE
                            and not (99.9 <= current_sum_percent <= 100.1)
                            and (abs(t1_val_save) > 1e-9 or abs(t2_val_save) > 1e-9)
                        ):
                            st.error(
                                f"KPI {kpi_data_sess_save.get('display_name', kpi_id_save)} ({CALC_TYPE_INCREMENTALE}): Somma ripartizioni MESE è {current_sum_percent:.2f}%. Deve essere 100%."
                            )
                            all_inputs_valid_save = False
                            break

                    elif (
                        effective_logic_db_save == REPARTITION_LOGIC_TRIMESTRE
                        and show_logic_radios_save
                    ):
                        quarters_save = ["Q1", "Q2", "Q3", "Q4"]
                        current_sum_percent = 0
                        for i, q_name_save in enumerate(quarters_save):
                            val = st.session_state.get(f"{key_base_save}_q_{i}", 0.0)
                            repart_values_for_db_save[q_name_save] = val
                            current_sum_percent += val
                        if (
                            kpi_data_sess_save.get("calc_type")
                            == CALC_TYPE_INCREMENTALE
                            and not (99.9 <= current_sum_percent <= 100.1)
                            and (abs(t1_val_save) > 1e-9 or abs(t2_val_save) > 1e-9)
                        ):
                            st.error(
                                f"KPI {kpi_data_sess_save.get('display_name', kpi_id_save)} ({CALC_TYPE_INCREMENTALE}): Somma ripartizioni TRIMESTRE è {current_sum_percent:.2f}%. Deve essere 100%."
                            )
                            all_inputs_valid_save = False
                            break

                    elif (
                        effective_logic_db_save == REPARTITION_LOGIC_SETTIMANA
                        and show_logic_radios_save
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

                    # Collect event params if profile is event_based
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
                        "annual_target1": t1_val_save,
                        "annual_target2": t2_val_save,
                        "repartition_logic": effective_logic_db_save,
                        "repartition_values": repart_values_for_db_save,
                        "distribution_profile": profile_save,
                        "profile_params": profile_params_for_db_save,
                        "is_target1_manual": is_manual1_save,
                        "is_target2_manual": is_manual2_save,
                    }

                if all_inputs_valid_save and targets_to_save_for_db:
                    try:
                        # For master/sub, save_annual_targets needs an initiator to correctly cascade.
                        # This part is tricky in Streamlit as we don't have a single "initiator" from the UI save button.
                        # The save_annual_targets function in database_manager.py should be robust enough
                        # to re-evaluate all master-sub relationships based on the provided map.
                        # If a specific initiator is strictly needed, we might need to rethink.
                        # For now, let's assume it can process the whole map.
                        db_manager.save_annual_targets(
                            year_to_save,
                            stab_id_to_save,
                            targets_to_save_for_db,
                            # initiator_kpi_spec_id might be omitted or set to a sensible default/None
                            # if save_annual_targets can handle a full refresh.
                        )
                        st.success("Target salvati e CSV (potenzialmente) rigenerati!")
                        load_kpi_data_for_target_entry()  # Refresh UI with saved data
                        st.rerun()
                    except Exception as e_save_db:
                        st.error(
                            f"Errore durante il salvataggio nel database: {e_save_db}"
                        )
                        import traceback

                        st.error(traceback.format_exc())
                elif not targets_to_save_for_db:
                    st.warning("Nessun dato target valido da salvare.")

    else:
        st.info("Seleziona Anno e Stabilimento per visualizzare o inserire i target.")

    # --- Helper function to be called after data loading ---
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
                    # Trigger distribution for both targets
                    on_master_target_ui_change(kpi_id_master_init, 1)
                    on_master_target_ui_change(kpi_id_master_init, 2)
        finally:
            st.session_state._master_sub_update_active_st = False

    # Call load_kpi_data_for_target_entry if inputs are not yet initialized for the current selection
    # This ensures that when the tab is first visited with valid filters, data is loaded.
    if (
        st.session_state.get("target_year_sb")
        and st.session_state.get("target_stab_sb")
        and not st.session_state.get("kpi_target_inputs")
    ):
        load_kpi_data_for_target_entry()
    elif (
        st.session_state.get("target_year_sb")
        and st.session_state.get("target_stab_sb")
        and st.session_state.get("kpi_target_inputs")
    ):
        # If inputs exist, still might need to refresh master-sub distribution if page was reloaded without filter change
        initial_master_sub_ui_distribution_st()


# --- 📈 Visualizzazione Risultati ---
with tab_results:
    st.header("Visualizzazione Risultati Ripartiti")
    st.info("Implementazione per 'Visualizzazione Risultati' in corso.")
    # - Filters for Year, Stabilimento, Period Type, KPI (Group > Subgroup > Indicator).
    # - Fetch and display repartited data in a table (st.dataframe).
    # - Show summary statistics.

# --- 📦 Esportazione Dati ---
with tab_export:
    st.header("Esportazione Dati Globali")

    resolved_path_str = str(Path(CSV_EXPORT_BASE_PATH).resolve())
    st.markdown(
        f"""
    I file CSV globali sono generati/sovrascritti automaticamente quando i target annuali vengono salvati.
    I file vengono salvati nella seguente cartella:
    `{resolved_path_str}`
    """
    )

    if st.button("Apri Cartella Esportazioni CSV"):
        export_path_obj = Path(CSV_EXPORT_BASE_PATH).resolve()
        if not export_path_obj.exists():
            export_path_obj.mkdir(parents=True, exist_ok=True)
            st.info(
                f"Cartella esportazioni creata: {export_path_obj}. Sarà popolata al salvataggio dei target."
            )
        else:
            try:
                if sys.platform == "win32":
                    subprocess.Popen(
                        f'explorer "{export_path_obj}"'
                    )  # More robust for paths with spaces
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(export_path_obj)])
                else:  # linux
                    subprocess.Popen(["xdg-open", str(export_path_obj)])
                st.success(f"Tentativo di aprire la cartella: {export_path_obj}")
            except Exception as e:
                st.error(
                    f"Impossibile aprire la cartella automaticamente: {e}. Percorso: {export_path_obj}"
                )

    st.markdown("---")
    st.subheader("Esporta CSV Globali in Archivio ZIP")

    if st.button("Crea e Scarica Archivio ZIP", type="primary"):
        export_base_path = Path(CSV_EXPORT_BASE_PATH)
        # Check if there's anything to zip
        if not export_base_path.exists() or not any(export_base_path.iterdir()):
            st.warning(
                f"La cartella di esportazione {export_base_path.resolve()} è vuota o non esiste. Salva prima qualche target."
            )
        else:
            default_zip_name = f"kpi_global_data_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            # In Streamlit, direct save dialog is not typical for server-side zipping.
            # We create the zip on the server and then offer it for download.

            # Define a temporary path for the zip file on the server
            temp_zip_path = Path(CSV_EXPORT_BASE_PATH) / default_zip_name

            try:
                success, message_or_zip_bytes = export_manager.package_all_csvs_as_zip(
                    str(CSV_EXPORT_BASE_PATH),
                    str(temp_zip_path),
                    return_bytes_for_streamlit=True,
                )
                if success:
                    with open(temp_zip_path, "rb") as fp:
                        st.download_button(
                            label="Scarica ZIP",
                            data=fp,  # Pass bytes directly if package_all_csvs_as_zip returns them
                            file_name=default_zip_name,
                            mime="application/zip",
                        )
                    st.success(f"Archivio '{default_zip_name}' pronto per il download.")
                    # Optionally, clean up the server-side temp zip file after some time or next run
                    # For simplicity, we might leave it in CSV_EXPORT_BASE_PATH or use a proper temp dir
                else:
                    st.error(
                        f"Errore durante la creazione dello ZIP: {message_or_zip_bytes}"
                    )
            except AttributeError:
                st.error(
                    "'package_all_csvs_as_zip' in export_manager.py non è configurato per 'return_bytes_for_streamlit=True' o la funzione non esiste."
                )
            except Exception as e:
                st.error(
                    f"Errore critico durante la creazione o il download dello ZIP: {e}"
                )
