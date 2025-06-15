# app_streamlit.py
import streamlit as st
import pandas as pd
import database_manager as db  # Your database manager
import export_manager  # Your export manager
import json
import datetime
import calendar
from pathlib import Path
import sqlite3  # For type hinting and error catching if needed

# --- Database Setup ---
try:
    db.setup_databases()
except Exception as e:
    st.error(f"Failed to setup databases: {e}")
    st.stop()

# --- Page Configuration ---
st.set_page_config(layout="wide", page_title="Gestione Target KPI")
st.title("Gestione Target KPI - Web")


# --- Helper Function (from Tkinter, slightly adapted if needed) ---
def get_kpi_display_name(kpi_data):
    if not kpi_data:
        return "N/D (KPI Data Mancante)"
    try:
        # kpi_data will now be a dict, so .get() is appropriate
        g_name = kpi_data.get("group_name") or "N/G (Gruppo non specificato)"
        sg_name = kpi_data.get("subgroup_name") or "N/S (Sottogruppo non specificato)"
        i_name = kpi_data.get("indicator_name") or "N/I (Indicatore non specificato)"
        return f"{g_name} > {sg_name} > {i_name}"
    except KeyError as e:  # Should be less likely with dicts if keys are consistent
        st.error(
            f"KeyError in get_kpi_display_name: La colonna '{e}' è mancante nei dati KPI."
        )
        return "N/D (Struttura Dati KPI Incompleta)"
    except Exception as ex:
        st.error(f"Errore imprevisto in get_kpi_display_name: {ex}")
        return "N/D (Errore Display Nome)"


# --- Cached Data Fetching Functions (MODIFIED FOR PICKLING) ---
@st.cache_data
def load_kpi_groups():
    groups = db.get_kpi_groups()
    if not groups:
        return []
    return [dict(g) for g in groups]  # Convert sqlite3.Row to dict


@st.cache_data
def load_kpi_subgroups_by_group(group_id):
    if not group_id:
        return []
    subgroups = db.get_kpi_subgroups_by_group(group_id)
    if not subgroups:
        return []
    return [dict(sg) for sg in subgroups]  # Convert sqlite3.Row to dict


@st.cache_data
def load_kpi_indicators_by_subgroup(subgroup_id):
    if not subgroup_id:
        return []
    indicators = db.get_kpi_indicators_by_subgroup(subgroup_id)
    if not indicators:
        return []
    return [dict(ind) for ind in indicators]  # Convert sqlite3.Row to dict


@st.cache_data
def load_all_kpis_with_hierarchy():
    kpis = db.get_kpis()
    if not kpis:
        return []
    return [dict(kpi) for kpi in kpis]  # Convert sqlite3.Row to dict


@st.cache_data
def load_kpi_by_id(kpi_id):
    kpi = db.get_kpi_by_id(kpi_id)
    if not kpi:
        return None
    return dict(kpi)  # Convert single sqlite3.Row to dict


@st.cache_data
def load_stabilimenti(only_visible=False):
    stabilimenti = db.get_stabilimenti(only_visible=only_visible)
    if not stabilimenti:
        return []
    return [dict(s) for s in stabilimenti]  # Convert sqlite3.Row to dict


@st.cache_data
def load_annual_target(year, stabilimento_id, kpi_id):
    target = db.get_annual_target(year, stabilimento_id, kpi_id)
    if not target:
        return None
    return dict(target)  # Convert single sqlite3.Row to dict


@st.cache_data
def load_ripartiti_data(year, stabilimento_id, kpi_id, period_type, target_num):
    data = db.get_ripartiti_data(year, stabilimento_id, kpi_id, period_type, target_num)
    if not data:
        return []
    # If db.get_ripartiti_data itself constructs dicts, this might not be needed
    # But to be safe, convert if it could return sqlite3.Row objects
    return [dict(row) for row in data]


# --- Distribution Profile Options ---
DISTRIBUTION_PROFILE_OPTIONS = [
    "annual_progressive",
    "monthly_sinusoidal",
    "legacy_intra_period_progressive",
]

# --- Initialize Session State ---
# For KPI Hierarchy tab
if "hr_selected_group_id" not in st.session_state:
    st.session_state.hr_selected_group_id = None
if "hr_selected_subgroup_id" not in st.session_state:
    st.session_state.hr_selected_subgroup_id = None
if "hr_selected_indicator_id" not in st.session_state:
    st.session_state.hr_selected_indicator_id = None
if "hr_editing_item_type" not in st.session_state:
    st.session_state.hr_editing_item_type = None
if "hr_editing_item_id" not in st.session_state:
    st.session_state.hr_editing_item_id = None
if "hr_editing_item_name" not in st.session_state:
    st.session_state.hr_editing_item_name = ""

# For KPI Spec tab
if "spec_selected_group_id" not in st.session_state:
    st.session_state.spec_selected_group_id = None
if "spec_selected_subgroup_id" not in st.session_state:
    st.session_state.spec_selected_subgroup_id = None
if "spec_selected_indicator_id" not in st.session_state:
    st.session_state.spec_selected_indicator_id = None
if "spec_editing_kpi_id" not in st.session_state:
    st.session_state.spec_editing_kpi_id = None
if "spec_form_data" not in st.session_state:
    st.session_state.spec_form_data = {
        "description": "",
        "calculation_type": "Incrementale",
        "unit_of_measure": "",
        "visible": True,
    }
if "spec_group_sel" not in st.session_state:
    st.session_state.spec_group_sel = ""  # For selectbox persistence
if "spec_subgroup_sel" not in st.session_state:
    st.session_state.spec_subgroup_sel = ""
if "spec_indicator_sel" not in st.session_state:
    st.session_state.spec_indicator_sel = ""


# For Stabilimenti tab
if "stbl_editing_stabilimento_id" not in st.session_state:
    st.session_state.stbl_editing_stabilimento_id = None
if "stbl_form_data" not in st.session_state:
    st.session_state.stbl_form_data = {"name": "", "visible": True}


# --- UI Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    [
        "🎯 Inserimento Target",
        "🗂️ Gestione Gerarchia KPI",
        "⚙️ Gestione Specifiche KPI",
        "🏭 Gestione Stabilimenti",
        "📈 Visualizzazione Risultati",
        "📦 Esportazione Dati",
    ]
)


# --- Functions to clear relevant caches ---
def clear_hierarchy_caches():
    load_kpi_groups.clear()
    load_kpi_subgroups_by_group.clear()
    load_kpi_indicators_by_subgroup.clear()
    load_all_kpis_with_hierarchy.clear()
    load_kpi_by_id.clear()


def clear_spec_caches():
    load_all_kpis_with_hierarchy.clear()
    load_kpi_by_id.clear()


def clear_stabilimenti_caches():
    load_stabilimenti.clear()


def clear_target_caches():
    load_annual_target.clear()
    load_ripartiti_data.clear()


with tab2:  # Gestione Gerarchia KPI
    st.header("🗂️ Gestione Gerarchia KPI")

    def reset_hr_edit_state():
        st.session_state.hr_editing_item_type = None
        st.session_state.hr_editing_item_id = None
        st.session_state.hr_editing_item_name = ""

    with st.container(border=True):
        st.subheader("Gruppi KPI")
        groups = load_kpi_groups()
        groups_map = {g["name"]: g["id"] for g in groups}

        selected_group_name_hr = st.selectbox(
            "Seleziona Gruppo",
            options=[""] + list(groups_map.keys()),
            key="hr_group_selector_sb",  # Changed key to avoid conflict if 'hr_group_selector' is used elsewhere
            index=0,
            on_change=lambda: setattr(st.session_state, "hr_selected_subgroup_id", None)
            or setattr(st.session_state, "hr_selected_indicator_id", None)
            or setattr(st.session_state, "hr_subgroup_selector_sb", "")
            or setattr(st.session_state, "hr_indicator_selector_sb", ""),
        )
        st.session_state.hr_selected_group_id = groups_map.get(selected_group_name_hr)

        col_g1, col_g2, col_g3 = st.columns(3)
        if col_g1.button("Nuovo Gruppo", key="hr_new_group_btn"):
            reset_hr_edit_state()
            st.session_state.hr_editing_item_type = "group_new"

        if st.session_state.hr_selected_group_id:
            if col_g2.button("Modifica Gruppo Selezionato", key="hr_edit_group_btn"):
                reset_hr_edit_state()
                st.session_state.hr_editing_item_type = "group_edit"
                st.session_state.hr_editing_item_id = (
                    st.session_state.hr_selected_group_id
                )
                st.session_state.hr_editing_item_name = selected_group_name_hr
            if col_g3.button("🗑️ Elimina Gruppo Selezionato", key="hr_delete_group_btn"):
                try:
                    if st.session_state.hr_selected_group_id:
                        group_to_delete_name = selected_group_name_hr
                        db.delete_kpi_group(st.session_state.hr_selected_group_id)
                        st.success(f"Gruppo '{group_to_delete_name}' eliminato.")
                        clear_hierarchy_caches()
                        clear_spec_caches()
                        st.session_state.hr_selected_group_id = None
                        st.session_state.hr_group_selector_sb = ""  # Reset selectbox
                        st.rerun()
                except Exception as e:
                    st.error(f"Errore eliminazione gruppo: {e}")

        if st.session_state.hr_editing_item_type in ["group_new", "group_edit"]:
            form_title = (
                "Nuovo Gruppo"
                if st.session_state.hr_editing_item_type == "group_new"
                else f"Modifica Gruppo: {st.session_state.hr_editing_item_name}"
            )
            with st.form(key="hr_group_form"):
                st.markdown(f"**{form_title}**")
                new_group_name_input = st.text_input(
                    "Nome Gruppo",
                    value=(
                        st.session_state.hr_editing_item_name
                        if st.session_state.hr_editing_item_type == "group_edit"
                        else ""
                    ),
                )
                submitted = st.form_submit_button("Salva")
                if submitted:
                    if not new_group_name_input.strip():
                        st.error("Il nome del gruppo non può essere vuoto.")
                    else:
                        try:
                            if st.session_state.hr_editing_item_type == "group_new":
                                db.add_kpi_group(new_group_name_input)
                                st.success(f"Gruppo '{new_group_name_input}' aggiunto.")
                            else:
                                db.update_kpi_group(
                                    st.session_state.hr_editing_item_id,
                                    new_group_name_input,
                                )
                                st.success(
                                    f"Gruppo aggiornato a '{new_group_name_input}'."
                                )
                            clear_hierarchy_caches()
                            reset_hr_edit_state()
                            st.session_state.hr_group_selector_sb = new_group_name_input
                            st.rerun()
                        except Exception as e:
                            st.error(f"Errore salvataggio gruppo: {e}")

    with st.container(border=True):
        st.subheader("Sottogruppi KPI (del gruppo selezionato)")
        if st.session_state.hr_selected_group_id:
            subgroups = load_kpi_subgroups_by_group(
                st.session_state.hr_selected_group_id
            )
            subgroups_map = {sg["name"]: sg["id"] for sg in subgroups}

            selected_subgroup_name_hr = st.selectbox(
                "Seleziona Sottogruppo",
                options=[""] + list(subgroups_map.keys()),
                key="hr_subgroup_selector_sb",  # Changed key
                index=0,
                on_change=lambda: setattr(
                    st.session_state, "hr_selected_indicator_id", None
                )
                or setattr(st.session_state, "hr_indicator_selector_sb", ""),
            )
            st.session_state.hr_selected_subgroup_id = subgroups_map.get(
                selected_subgroup_name_hr
            )

            col_sg1, col_sg2, col_sg3 = st.columns(3)
            if col_sg1.button("Nuovo Sottogruppo", key="hr_new_subgroup_btn"):
                reset_hr_edit_state()
                st.session_state.hr_editing_item_type = "subgroup_new"

            if st.session_state.hr_selected_subgroup_id:
                if col_sg2.button(
                    "Modifica Sottogruppo Selezionato", key="hr_edit_subgroup_btn"
                ):
                    reset_hr_edit_state()
                    st.session_state.hr_editing_item_type = "subgroup_edit"
                    st.session_state.hr_editing_item_id = (
                        st.session_state.hr_selected_subgroup_id
                    )
                    st.session_state.hr_editing_item_name = selected_subgroup_name_hr
                if col_sg3.button(
                    "🗑️ Elimina Sottogruppo Selezionato", key="hr_delete_subgroup_btn"
                ):
                    try:
                        db.delete_kpi_subgroup(st.session_state.hr_selected_subgroup_id)
                        st.success(
                            f"Sottogruppo '{selected_subgroup_name_hr}' eliminato."
                        )
                        clear_hierarchy_caches()
                        clear_spec_caches()
                        st.session_state.hr_selected_subgroup_id = None
                        st.session_state.hr_subgroup_selector_sb = ""
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore eliminazione sottogruppo: {e}")

            if st.session_state.hr_editing_item_type in [
                "subgroup_new",
                "subgroup_edit",
            ]:
                form_title_sg = (
                    "Nuovo Sottogruppo"
                    if st.session_state.hr_editing_item_type == "subgroup_new"
                    else f"Modifica Sottogruppo: {st.session_state.hr_editing_item_name}"
                )
                with st.form(key="hr_subgroup_form"):
                    st.markdown(
                        f"**{form_title_sg}** (per Gruppo: {selected_group_name_hr})"
                    )
                    new_subgroup_name_input = st.text_input(
                        "Nome Sottogruppo",
                        value=(
                            st.session_state.hr_editing_item_name
                            if st.session_state.hr_editing_item_type == "subgroup_edit"
                            else ""
                        ),
                    )
                    submitted_sg = st.form_submit_button("Salva")
                    if submitted_sg:
                        if not new_subgroup_name_input.strip():
                            st.error("Nome sottogruppo non può essere vuoto.")
                        else:
                            try:
                                if (
                                    st.session_state.hr_editing_item_type
                                    == "subgroup_new"
                                ):
                                    db.add_kpi_subgroup(
                                        new_subgroup_name_input,
                                        st.session_state.hr_selected_group_id,
                                    )
                                    st.success(
                                        f"Sottogruppo '{new_subgroup_name_input}' aggiunto."
                                    )
                                else:
                                    db.update_kpi_subgroup(
                                        st.session_state.hr_editing_item_id,
                                        new_subgroup_name_input,
                                        st.session_state.hr_selected_group_id,
                                    )
                                    st.success(
                                        f"Sottogruppo aggiornato a '{new_subgroup_name_input}'."
                                    )
                                clear_hierarchy_caches()
                                reset_hr_edit_state()
                                st.session_state.hr_subgroup_selector_sb = (
                                    new_subgroup_name_input
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore salvataggio sottogruppo: {e}")
        else:
            st.info("Seleziona un Gruppo KPI.")

    with st.container(border=True):
        st.subheader("Indicatori KPI (del sottogruppo selezionato)")
        if st.session_state.hr_selected_subgroup_id:
            indicators = load_kpi_indicators_by_subgroup(
                st.session_state.hr_selected_subgroup_id
            )
            indicators_map = {ind["name"]: ind["id"] for ind in indicators}

            selected_indicator_name_hr = st.selectbox(
                "Seleziona Indicatore",
                options=[""] + list(indicators_map.keys()),
                key="hr_indicator_selector_sb",  # Changed key
                index=0,
            )
            st.session_state.hr_selected_indicator_id = indicators_map.get(
                selected_indicator_name_hr
            )

            col_i1, col_i2, col_i3 = st.columns(3)
            if col_i1.button("Nuovo Indicatore", key="hr_new_indicator_btn"):
                reset_hr_edit_state()
                st.session_state.hr_editing_item_type = "indicator_new"

            if st.session_state.hr_selected_indicator_id:
                if col_i2.button(
                    "Modifica Indicatore Selezionato", key="hr_edit_indicator_btn"
                ):
                    reset_hr_edit_state()
                    st.session_state.hr_editing_item_type = "indicator_edit"
                    st.session_state.hr_editing_item_id = (
                        st.session_state.hr_selected_indicator_id
                    )
                    st.session_state.hr_editing_item_name = selected_indicator_name_hr
                if col_i3.button(
                    "🗑️ Elimina Indicatore Selezionato", key="hr_delete_indicator_btn"
                ):
                    try:
                        db.delete_kpi_indicator(
                            st.session_state.hr_selected_indicator_id
                        )
                        st.success(
                            f"Indicatore '{selected_indicator_name_hr}' eliminato."
                        )
                        clear_hierarchy_caches()
                        clear_spec_caches()
                        st.session_state.hr_selected_indicator_id = None
                        st.session_state.hr_indicator_selector_sb = ""
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore eliminazione indicatore: {e}")

            if st.session_state.hr_editing_item_type in [
                "indicator_new",
                "indicator_edit",
            ]:
                form_title_ind = (
                    "Nuovo Indicatore"
                    if st.session_state.hr_editing_item_type == "indicator_new"
                    else f"Modifica Indicatore: {st.session_state.hr_editing_item_name}"
                )
                with st.form(key="hr_indicator_form"):
                    st.markdown(
                        f"**{form_title_ind}** (per Sottogruppo: {selected_subgroup_name_hr})"
                    )
                    new_indicator_name_input = st.text_input(
                        "Nome Indicatore",
                        value=(
                            st.session_state.hr_editing_item_name
                            if st.session_state.hr_editing_item_type == "indicator_edit"
                            else ""
                        ),
                    )
                    submitted_ind = st.form_submit_button("Salva")
                    if submitted_ind:
                        if not new_indicator_name_input.strip():
                            st.error("Nome indicatore non può essere vuoto.")
                        else:
                            try:
                                if (
                                    st.session_state.hr_editing_item_type
                                    == "indicator_new"
                                ):
                                    db.add_kpi_indicator(
                                        new_indicator_name_input,
                                        st.session_state.hr_selected_subgroup_id,
                                    )
                                    st.success(
                                        f"Indicatore '{new_indicator_name_input}' aggiunto."
                                    )
                                else:
                                    db.update_kpi_indicator(
                                        st.session_state.hr_editing_item_id,
                                        new_indicator_name_input,
                                        st.session_state.hr_selected_subgroup_id,
                                    )
                                    st.success(
                                        f"Indicatore aggiornato a '{new_indicator_name_input}'."
                                    )
                                clear_hierarchy_caches()
                                reset_hr_edit_state()
                                st.session_state.hr_indicator_selector_sb = (
                                    new_indicator_name_input
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore salvataggio indicatore: {e}")
        else:
            st.info("Seleziona un Sottogruppo KPI.")


with tab3:  # Gestione Specifiche KPI
    st.header("⚙️ Gestione Specifiche KPI")

    with st.expander("Aggiungi/Modifica Specifica KPI", expanded=True):

        def spec_group_changed():
            st.session_state.spec_subgroup_sel = ""  # Reset subgroup selection for UI
            st.session_state.spec_indicator_sel = ""  # Reset indicator selection for UI
            st.session_state.spec_selected_subgroup_id = None
            st.session_state.spec_selected_indicator_id = None
            st.session_state.spec_editing_kpi_id = None
            if (
                "spec_manual_selection" in st.session_state
                and st.session_state.spec_manual_selection
            ):
                st.session_state.spec_form_data = {
                    "description": "",
                    "calculation_type": "Incrementale",
                    "unit_of_measure": "",
                    "visible": True,
                }

        def spec_subgroup_changed():
            st.session_state.spec_indicator_sel = ""  # Reset indicator selection for UI
            st.session_state.spec_selected_indicator_id = None
            st.session_state.spec_editing_kpi_id = None
            if (
                "spec_manual_selection" in st.session_state
                and st.session_state.spec_manual_selection
            ):
                st.session_state.spec_form_data = {
                    "description": "",
                    "calculation_type": "Incrementale",
                    "unit_of_measure": "",
                    "visible": True,
                }

        def spec_indicator_changed():
            st.session_state.spec_editing_kpi_id = None
            st.session_state.spec_form_data = {
                "description": "",
                "calculation_type": "Incrementale",
                "unit_of_measure": "",
                "visible": True,
            }

            # Find the actual indicator ID from the selected name in st.session_state.spec_indicator_sel
            # This requires the map to be accessible or re-created here.
            # For simplicity, we assume st.session_state.spec_selected_indicator_id is correctly set by the selectbox logic below.

            if st.session_state.spec_selected_indicator_id:
                all_kpis = load_all_kpis_with_hierarchy()
                existing_kpi_spec = next(
                    (
                        kpi
                        for kpi in all_kpis
                        if kpi["indicator_id"]
                        == st.session_state.spec_selected_indicator_id
                    ),
                    None,
                )
                if existing_kpi_spec:
                    st.session_state.spec_editing_kpi_id = existing_kpi_spec["id"]
                    st.session_state.spec_form_data = {
                        "description": existing_kpi_spec["description"] or "",
                        "calculation_type": existing_kpi_spec["calculation_type"]
                        or "Incrementale",
                        "unit_of_measure": existing_kpi_spec["unit_of_measure"] or "",
                        "visible": bool(existing_kpi_spec["visible"]),
                    }
            st.session_state.spec_manual_selection = True

        s_col1, s_col2, s_col3 = st.columns(3)
        groups_spec = load_kpi_groups()
        groups_spec_map = {g["name"]: g["id"] for g in groups_spec}

        with s_col1:
            st.session_state.spec_group_sel = (
                st.selectbox(  # Bind to session state for persistence
                    "Gruppo",
                    [""] + list(groups_spec_map.keys()),
                    key="spec_group_sel_key",  # Unique key for widget
                    index=(
                        ([""] + list(groups_spec_map.keys())).index(
                            st.session_state.spec_group_sel
                        )
                        if st.session_state.spec_group_sel
                        in ([""] + list(groups_spec_map.keys()))
                        else 0
                    ),
                    on_change=spec_group_changed,
                )
            )
            st.session_state.spec_selected_group_id = groups_spec_map.get(
                st.session_state.spec_group_sel
            )

        with s_col2:
            subgroups_spec = load_kpi_subgroups_by_group(
                st.session_state.spec_selected_group_id
            )
            subgroups_spec_map = {sg["name"]: sg["id"] for sg in subgroups_spec}
            st.session_state.spec_subgroup_sel = st.selectbox(
                "Sottogruppo",
                [""] + list(subgroups_spec_map.keys()),
                key="spec_subgroup_sel_key",
                index=(
                    ([""] + list(subgroups_spec_map.keys())).index(
                        st.session_state.spec_subgroup_sel
                    )
                    if st.session_state.spec_subgroup_sel
                    in ([""] + list(subgroups_spec_map.keys()))
                    else 0
                ),
                disabled=not st.session_state.spec_selected_group_id,
                on_change=spec_subgroup_changed,
            )
            st.session_state.spec_selected_subgroup_id = subgroups_spec_map.get(
                st.session_state.spec_subgroup_sel
            )

        with s_col3:
            indicators_spec = load_kpi_indicators_by_subgroup(
                st.session_state.spec_selected_subgroup_id
            )
            all_kpis_for_filter = load_all_kpis_with_hierarchy()
            indicator_ids_with_spec = {
                kpi["indicator_id"] for kpi in all_kpis_for_filter
            }

            available_indicators_spec_map = {}
            for ind in indicators_spec:
                is_editing_this_indicator = False
                if st.session_state.spec_editing_kpi_id:
                    editing_spec = next(
                        (
                            k
                            for k in all_kpis_for_filter
                            if k["id"] == st.session_state.spec_editing_kpi_id
                        ),
                        None,
                    )
                    if editing_spec and editing_spec["indicator_id"] == ind["id"]:
                        is_editing_this_indicator = True
                if (
                    is_editing_this_indicator
                    or ind["id"] not in indicator_ids_with_spec
                ):
                    available_indicators_spec_map[ind["name"]] = ind["id"]

            st.session_state.spec_indicator_sel = st.selectbox(
                "Indicatore",
                [""] + list(available_indicators_spec_map.keys()),
                key="spec_indicator_sel_key",
                index=(
                    ([""] + list(available_indicators_spec_map.keys())).index(
                        st.session_state.spec_indicator_sel
                    )
                    if st.session_state.spec_indicator_sel
                    in ([""] + list(available_indicators_spec_map.keys()))
                    else 0
                ),
                disabled=not st.session_state.spec_selected_subgroup_id,
                on_change=lambda: setattr(
                    st.session_state,
                    "spec_selected_indicator_id",
                    available_indicators_spec_map.get(
                        st.session_state.spec_indicator_sel_key
                    ),
                )
                or spec_indicator_changed(),
            )
            # Ensure spec_selected_indicator_id is updated when selectbox changes
            if st.session_state.spec_indicator_sel:  # If a name is selected
                st.session_state.spec_selected_indicator_id = (
                    available_indicators_spec_map.get(
                        st.session_state.spec_indicator_sel
                    )
                )
            else:  # If "" (no selection) is chosen
                st.session_state.spec_selected_indicator_id = None

        with st.form("kpi_spec_form"):
            st.session_state.spec_form_data["description"] = st.text_area(
                "Descrizione", value=st.session_state.spec_form_data["description"]
            )
            st.session_state.spec_form_data["calculation_type"] = st.selectbox(
                "Tipo Calcolo",
                ["Incrementale", "Media"],
                index=["Incrementale", "Media"].index(
                    st.session_state.spec_form_data["calculation_type"]
                ),
            )
            st.session_state.spec_form_data["unit_of_measure"] = st.text_input(
                "Unità Misura", value=st.session_state.spec_form_data["unit_of_measure"]
            )
            st.session_state.spec_form_data["visible"] = st.checkbox(
                "Visibile per Inserimento Target",
                value=st.session_state.spec_form_data["visible"],
            )

            form_action_button_text = (
                "Modifica Specifica KPI"
                if st.session_state.spec_editing_kpi_id
                else "Aggiungi Specifica KPI"
            )
            submitted_spec = st.form_submit_button(form_action_button_text)

            if submitted_spec:
                if not st.session_state.spec_selected_indicator_id:
                    st.error("Seleziona un Gruppo > Sottogruppo > Indicatore completo.")
                elif not st.session_state.spec_form_data["description"].strip():
                    st.error("La descrizione è obbligatoria.")
                else:
                    try:
                        if st.session_state.spec_editing_kpi_id:
                            db.update_kpi(
                                st.session_state.spec_editing_kpi_id,
                                st.session_state.spec_selected_indicator_id,
                                st.session_state.spec_form_data["description"],
                                st.session_state.spec_form_data["calculation_type"],
                                st.session_state.spec_form_data["unit_of_measure"],
                                st.session_state.spec_form_data["visible"],
                            )
                            st.success("Specifica KPI aggiornata!")
                        else:
                            db.add_kpi(
                                st.session_state.spec_selected_indicator_id,
                                st.session_state.spec_form_data["description"],
                                st.session_state.spec_form_data["calculation_type"],
                                st.session_state.spec_form_data["unit_of_measure"],
                                st.session_state.spec_form_data["visible"],
                            )
                            st.success("Nuova specifica KPI aggiunta!")
                        clear_spec_caches()
                        st.session_state.spec_editing_kpi_id = None
                        st.session_state.spec_form_data = {
                            "description": "",
                            "calculation_type": "Incrementale",
                            "unit_of_measure": "",
                            "visible": True,
                        }
                        st.session_state.spec_group_sel = ""
                        st.session_state.spec_subgroup_sel = ""
                        st.session_state.spec_indicator_sel = ""
                        st.rerun()
                    except sqlite3.IntegrityError as ie:
                        if (
                            "UNIQUE constraint failed: kpis.indicator_id" in str(ie)
                            and not st.session_state.spec_editing_kpi_id
                        ):
                            st.error(
                                f"Una specifica KPI per l'indicatore selezionato esiste già."
                            )
                        else:
                            st.error(f"Errore di integrità del database: {ie}")
                    except Exception as e:
                        st.error(f"Salvataggio fallito: {e}")

        if st.button("Pulisci Campi Form Specifica"):
            st.session_state.spec_selected_group_id = None
            st.session_state.spec_selected_subgroup_id = None
            st.session_state.spec_selected_indicator_id = None
            st.session_state.spec_editing_kpi_id = None
            st.session_state.spec_form_data = {
                "description": "",
                "calculation_type": "Incrementale",
                "unit_of_measure": "",
                "visible": True,
            }
            st.session_state.spec_group_sel = ""
            st.session_state.spec_subgroup_sel = ""
            st.session_state.spec_indicator_sel = ""
            st.rerun()

    st.subheader("Elenco Specifiche KPI Esistenti")
    all_kpis = load_all_kpis_with_hierarchy()
    if all_kpis:
        df_kpis = pd.DataFrame(all_kpis)
        df_kpis_display = df_kpis[
            [
                "id",
                "group_name",
                "subgroup_name",
                "indicator_name",
                "description",
                "calculation_type",
                "unit_of_measure",
                "visible",
            ]
        ].copy()
        df_kpis_display.rename(
            columns={
                "id": "Spec ID",
                "group_name": "Gruppo",
                "subgroup_name": "Sottogruppo",
                "indicator_name": "Indicatore",
                "description": "Descrizione",
                "calculation_type": "Tipo Calcolo",
                "unit_of_measure": "Unità Misura",
                "visible": "Visibile",
            },
            inplace=True,
        )
        df_kpis_display["Visibile"] = df_kpis_display["Visibile"].apply(
            lambda x: "Sì" if x else "No"
        )

        st.dataframe(df_kpis_display, use_container_width=True, hide_index=True)

        kpi_spec_ids_for_selection = {
            f"{get_kpi_display_name(kpi)} (ID: {kpi['id']})": kpi["id"]
            for kpi in all_kpis
        }
        selected_kpi_spec_to_manage_key = st.selectbox(
            "Seleziona Specifica KPI per Azioni",
            [""] + list(kpi_spec_ids_for_selection.keys()),
            index=0,
            key="spec_manage_select",
        )
        selected_kpi_spec_id_to_manage = kpi_spec_ids_for_selection.get(
            selected_kpi_spec_to_manage_key
        )

        if selected_kpi_spec_id_to_manage:
            kpi_data_full = load_kpi_by_id(selected_kpi_spec_id_to_manage)

            col_spec_act1, col_spec_act2 = st.columns([1, 3])
            with col_spec_act1:
                if st.button("Carica per Modifica", key="load_spec_for_edit"):
                    if kpi_data_full:
                        st.session_state.spec_editing_kpi_id = kpi_data_full["id"]
                        st.session_state.spec_selected_indicator_id = kpi_data_full[
                            "indicator_id"
                        ]
                        st.session_state.spec_group_sel = kpi_data_full["group_name"]
                        st.session_state.spec_subgroup_sel = kpi_data_full[
                            "subgroup_name"
                        ]
                        st.session_state.spec_indicator_sel = kpi_data_full[
                            "indicator_name"
                        ]
                        st.session_state.spec_form_data = {
                            "description": kpi_data_full["description"] or "",
                            "calculation_type": kpi_data_full["calculation_type"]
                            or "Incrementale",
                            "unit_of_measure": kpi_data_full["unit_of_measure"] or "",
                            "visible": bool(kpi_data_full["visible"]),
                        }
                        st.session_state.spec_manual_selection = False
                        st.rerun()

            with col_spec_act2:
                if st.button(
                    f"🗑️ Elimina Specifica: {selected_kpi_spec_to_manage_key.split(' (ID:')[0]}",
                    type="primary",
                    key="delete_spec_btn_confirm_init",
                ):
                    if (
                        "confirm_delete_spec_id" not in st.session_state
                        or st.session_state.confirm_delete_spec_id
                        != selected_kpi_spec_id_to_manage
                    ):
                        st.session_state.confirm_delete_spec_id = (
                            selected_kpi_spec_id_to_manage
                        )
                        st.session_state.confirm_delete_spec_name = (
                            selected_kpi_spec_to_manage_key
                        )
                        st.rerun()

            if (
                "confirm_delete_spec_id" in st.session_state
                and st.session_state.confirm_delete_spec_id
                == selected_kpi_spec_id_to_manage
            ):
                st.error(
                    f"Sicuro di eliminare: {st.session_state.confirm_delete_spec_name} e tutti i target associati?"
                )
                c_del_spec1, c_del_spec2, _ = st.columns([1, 1, 5])
                if c_del_spec1.button(
                    "Sì, Elimina", type="primary", key="confirm_del_spec_yes_final"
                ):
                    try:
                        kpi_id_to_delete = st.session_state.confirm_delete_spec_id
                        # Assuming db.DB_TARGETS etc. are accessible paths
                        with sqlite3.connect(db.DB_TARGETS) as conn_targets:
                            conn_targets.execute(
                                "DELETE FROM annual_targets WHERE kpi_id = ?",
                                (kpi_id_to_delete,),
                            )
                        periodic_dbs_info = [
                            (db.DB_KPI_DAYS, "daily_targets"),
                            (db.DB_KPI_WEEKS, "weekly_targets"),
                            (db.DB_KPI_MONTHS, "monthly_targets"),
                            (db.DB_KPI_QUARTERS, "quarterly_targets"),
                        ]
                        for db_path, table_name in periodic_dbs_info:
                            with sqlite3.connect(db_path) as conn_periodic:
                                conn_periodic.execute(
                                    f"DELETE FROM {table_name} WHERE kpi_id = ?",
                                    (kpi_id_to_delete,),
                                )
                        with sqlite3.connect(
                            db.DB_KPIS
                        ) as conn_kpis:  # Assuming DB_KPIS path
                            conn_kpis.execute(
                                "DELETE FROM kpis WHERE id = ?", (kpi_id_to_delete,)
                            )

                        st.success("Specifica KPI e target associati eliminati.")
                        clear_spec_caches()
                        clear_target_caches()
                        del (
                            st.session_state.confirm_delete_spec_id
                        )  # Clear confirmation state
                        st.session_state.spec_manage_select = ""  # Reset selectbox
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore eliminazione: {e}")
                if c_del_spec2.button("No, Annulla", key="confirm_del_spec_no_final"):
                    del st.session_state.confirm_delete_spec_id
                    st.rerun()
    else:
        st.info("Nessuna specifica KPI definita.")


with tab4:  # Gestione Stabilimenti
    st.header("🏭 Gestione Stabilimenti")

    mode = (
        "Aggiungi"
        if st.session_state.stbl_editing_stabilimento_id is None
        else "Modifica"
    )
    with st.expander(
        f"{mode} Stabilimento",
        expanded=st.session_state.stbl_editing_stabilimento_id is not None
        or "stbl_show_add_form" in st.session_state,
    ):
        if "stbl_show_add_form" in st.session_state:
            del st.session_state.stbl_show_add_form

        with st.form("stabilimento_form"):
            st.session_state.stbl_form_data["name"] = st.text_input(
                "Nome Stabilimento", value=st.session_state.stbl_form_data["name"]
            )
            st.session_state.stbl_form_data["visible"] = st.checkbox(
                "Visibile per Inserimento Target",
                value=st.session_state.stbl_form_data["visible"],
            )
            submitted_stbl = st.form_submit_button("Salva Stabilimento")

            if submitted_stbl:
                name_val = st.session_state.stbl_form_data["name"].strip()
                visible_val = st.session_state.stbl_form_data["visible"]
                if not name_val:
                    st.error("Nome stabilimento obbligatorio.")
                else:
                    try:
                        if st.session_state.stbl_editing_stabilimento_id is not None:
                            db.update_stabilimento(
                                st.session_state.stbl_editing_stabilimento_id,
                                name_val,
                                visible_val,
                            )
                            st.success(f"Stabilimento '{name_val}' aggiornato.")
                        else:
                            db.add_stabilimento(name_val, visible_val)
                            st.success(f"Stabilimento '{name_val}' aggiunto.")
                        clear_stabilimenti_caches()
                        st.session_state.stbl_editing_stabilimento_id = None
                        st.session_state.stbl_form_data = {"name": "", "visible": True}
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(f"Uno stabilimento con nome '{name_val}' esiste già.")
                    except Exception as e:
                        st.error(f"Salvataggio fallito: {e}")
        if st.session_state.stbl_editing_stabilimento_id is not None and st.button(
            "Annulla Modifica"
        ):
            st.session_state.stbl_editing_stabilimento_id = None
            st.session_state.stbl_form_data = {"name": "", "visible": True}
            st.rerun()

    st.subheader("Elenco Stabilimenti Esistenti")
    if st.button("Aggiungi Nuovo Stabilimento"):
        st.session_state.stbl_editing_stabilimento_id = None
        st.session_state.stbl_form_data = {"name": "", "visible": True}
        st.session_state.stbl_show_add_form = True
        st.rerun()

    stabilimenti = load_stabilimenti()
    if stabilimenti:
        df_stabilimenti = pd.DataFrame(stabilimenti)
        df_stabilimenti_display = df_stabilimenti[["id", "name", "visible"]].copy()
        df_stabilimenti_display.rename(
            columns={"id": "ID", "name": "Nome", "visible": "Visibile"}, inplace=True
        )
        df_stabilimenti_display["Visibile"] = df_stabilimenti_display["Visibile"].apply(
            lambda x: "Sì" if x else "No"
        )

        st.dataframe(df_stabilimenti_display, use_container_width=True, hide_index=True)

        stbl_names_for_selection = {s["name"]: s["id"] for s in stabilimenti}
        selected_stbl_name_to_edit = st.selectbox(
            "Seleziona Stabilimento da Modificare",
            [""] + list(stbl_names_for_selection.keys()),
            key="stbl_edit_sel",
        )
        if selected_stbl_name_to_edit and st.button(
            "Carica Stabilimento per Modifica", key="stbl_load_edit_btn"
        ):  # Added button
            stbl_id_to_edit = stbl_names_for_selection[selected_stbl_name_to_edit]
            selected_stbl_data = next(
                (s for s in stabilimenti if s["id"] == stbl_id_to_edit), None
            )
            if selected_stbl_data:
                st.session_state.stbl_editing_stabilimento_id = stbl_id_to_edit
                st.session_state.stbl_form_data = {
                    "name": selected_stbl_data["name"],
                    "visible": bool(selected_stbl_data["visible"]),
                }
                st.rerun()
    else:
        st.info("Nessuno stabilimento definito.")


with tab1:  # Inserimento Target
    st.header("🎯 Inserimento Target Annuali")

    filt_col1, filt_col2 = st.columns(2)
    with filt_col1:
        current_year_dt = datetime.datetime.now().year
        selected_year_target = st.number_input(
            "Anno",
            min_value=2020,
            max_value=2050,
            value=current_year_dt,
            key="target_year_sel",
        )
    with filt_col2:
        stabilimenti_vis_target = load_stabilimenti(only_visible=True)
        if not stabilimenti_vis_target:
            st.warning("Nessuno stabilimento (visibile) definito.")
            st.stop()
        stabilimenti_map_target = {s["name"]: s["id"] for s in stabilimenti_vis_target}
        selected_stabilimento_name_target = st.selectbox(
            "Stabilimento",
            options=[""] + list(stabilimenti_map_target.keys()),
            key="target_stabilimento_sel",
        )
        selected_stabilimento_id_target = stabilimenti_map_target.get(
            selected_stabilimento_name_target
        )

    if not selected_stabilimento_id_target:
        st.info("Seleziona Anno e Stabilimento.")
        st.stop()

    st.markdown("---")

    kpis_for_target_entry = [
        kpi for kpi in load_all_kpis_with_hierarchy() if kpi.get("visible", False)
    ]  # Ensure 'visible' key exists

    if not kpis_for_target_entry:
        st.warning("Nessun KPI (visibile) definito.")
        st.stop()

    kpis_for_target_entry.sort(
        key=lambda k: (
            k.get("group_name", ""),
            k.get("subgroup_name", ""),
            k.get("indicator_name", ""),
        )
    )

    targets_data_to_save = {}
    all_inputs_valid = True

    with st.form("all_targets_form"):
        for kpi_row_data in kpis_for_target_entry:
            kpi_id = kpi_row_data["id"]
            kpi_display_name_str = get_kpi_display_name(kpi_row_data)
            kpi_unit = kpi_row_data.get("unit_of_measure") or ""
            frame_label_text = kpi_display_name_str + (
                f" (Unità: {kpi_unit})" if kpi_unit else " (Unità: N/D)"
            )

            with st.expander(frame_label_text, expanded=True):
                existing_target_db = load_annual_target(
                    selected_year_target, selected_stabilimento_id_target, kpi_id
                )
                def_t1, def_t2 = 0.0, 0.0
                def_logic, def_profile = "Mese", "annual_progressive"
                def_repart_map = {}

                if existing_target_db:  # existing_target_db is now a dict
                    def_t1 = float(existing_target_db.get("annual_target1", 0.0) or 0.0)
                    def_t2 = float(existing_target_db.get("annual_target2", 0.0) or 0.0)
                    def_logic = existing_target_db.get("repartition_logic") or "Mese"
                    db_profile = existing_target_db.get("distribution_profile")
                    def_profile = (
                        db_profile
                        if db_profile in DISTRIBUTION_PROFILE_OPTIONS
                        else "annual_progressive"
                    )
                    repart_values_str = existing_target_db.get("repartition_values")
                    if repart_values_str:
                        try:
                            loaded_map = json.loads(repart_values_str)
                            if isinstance(loaded_map, dict):
                                def_repart_map = loaded_map
                        except json.JSONDecodeError:
                            pass

                in_col1, in_col2, in_col3 = st.columns(3)
                with in_col1:
                    annual_target1 = st.number_input(
                        f"Target 1",
                        value=def_t1,
                        key=f"t1_{kpi_id}_{selected_year_target}_{selected_stabilimento_id_target}",
                        format="%.2f",
                        step=0.01,
                    )
                with in_col2:
                    annual_target2 = st.number_input(
                        f"Target 2",
                        value=def_t2,
                        key=f"t2_{kpi_id}_{selected_year_target}_{selected_stabilimento_id_target}",
                        format="%.2f",
                        step=0.01,
                    )
                with in_col3:
                    profile_val = st.selectbox(
                        "Profilo Distribuzione",
                        DISTRIBUTION_PROFILE_OPTIONS,
                        index=DISTRIBUTION_PROFILE_OPTIONS.index(def_profile),
                        key=f"prof_{kpi_id}_{selected_year_target}_{selected_stabilimento_id_target}",
                    )

                current_kpi_target_data = {
                    "annual_target1": annual_target1,
                    "annual_target2": annual_target2,
                    "distribution_profile": profile_val,
                    "repartition_values": {},
                }

                if profile_val in [
                    "monthly_sinusoidal",
                    "legacy_intra_period_progressive",
                ]:
                    repart_logic = st.radio(
                        "Logica Ripartizione % Annuale",
                        ["Mese", "Trimestre"],
                        index=["Mese", "Trimestre"].index(def_logic),
                        horizontal=True,
                        key=f"logic_{kpi_id}_{selected_year_target}_{selected_stabilimento_id_target}",
                    )
                    current_kpi_target_data["repartition_logic"] = repart_logic
                    periods = (
                        [calendar.month_name[i] for i in range(1, 13)]
                        if repart_logic == "Mese"
                        else ["Q1", "Q2", "Q3", "Q4"]
                    )
                    num_cols_repart = 4
                    st.markdown(
                        f"**Percentuali di Ripartizione per {repart_logic} (%):**"
                    )
                    period_cols = st.columns(num_cols_repart)
                    total_perc = 0.0

                    for i, period_name in enumerate(periods):
                        with period_cols[i % num_cols_repart]:
                            default_perc = def_repart_map.get(
                                period_name, (100.0 / len(periods))
                            )
                            perc_val = st.number_input(
                                period_name,
                                value=round(float(default_perc), 2),
                                min_value=0.0,
                                max_value=100.0,
                                format="%.2f",
                                step=0.01,
                                key=f"repart_{period_name}_{kpi_id}_{selected_year_target}_{selected_stabilimento_id_target}",
                            )
                            current_kpi_target_data["repartition_values"][
                                period_name
                            ] = perc_val
                            total_perc += perc_val

                    if (annual_target1 > 1e-9 or annual_target2 > 1e-9) and not (
                        99.9 <= total_perc <= 100.1
                    ):
                        st.error(
                            f"KPI '{kpi_display_name_str}': Somma % ({repart_logic}) = {total_perc:.2f}%. Deve essere ~100%."
                        )
                        all_inputs_valid = False
                else:
                    current_kpi_target_data["repartition_logic"] = "Mese"
                    current_kpi_target_data["repartition_values"] = {
                        calendar.month_name[i]: round(100.0 / 12.0, 5)
                        for i in range(1, 13)
                    }
                targets_data_to_save[kpi_id] = current_kpi_target_data

        st.markdown("---")
        if st.form_submit_button(
            "SALVA TUTTI I TARGET", type="primary", use_container_width=True
        ):
            if not all_inputs_valid:
                st.error("Correggi errori validazione.")
            elif not targets_data_to_save:
                st.warning("Nessun target definito.")
            else:
                try:
                    db.save_annual_targets(
                        selected_year_target,
                        selected_stabilimento_id_target,
                        targets_data_to_save,
                    )
                    st.success("Target salvati e ripartizioni ricalcolate!")
                    clear_target_caches()
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore salvataggio: {e}")

with tab5:  # Visualizzazione Risultati
    st.header("📈 Visualizzazione Risultati Ripartiti")

    vis_filt_cols = st.columns([1, 2, 2, 1, 1])
    with vis_filt_cols[0]:
        res_year = st.number_input(
            "Anno",
            min_value=2020,
            max_value=2050,
            value=datetime.datetime.now().year,
            key="res_year_s",
        )
    with vis_filt_cols[1]:
        stabilimenti_res = load_stabilimenti()
        stabilimenti_map_res = {s["name"]: s["id"] for s in stabilimenti_res}
        res_stabilimento_name = st.selectbox(
            "Stabilimento",
            [""] + list(stabilimenti_map_res.keys()),
            key="res_stabilimento_s",
        )
        res_stabilimento_id = stabilimenti_map_res.get(res_stabilimento_name)

    with vis_filt_cols[2]:
        groups_res = load_kpi_groups()
        groups_map_res = {g["name"]: g["id"] for g in groups_res}
        res_group_name = st.selectbox(
            "Gruppo KPI", [""] + list(groups_map_res.keys()), key="res_group_s"
        )
        res_group_id = groups_map_res.get(res_group_name)
        subgroups_res = load_kpi_subgroups_by_group(res_group_id)
        subgroups_map_res = {sg["name"]: sg["id"] for sg in subgroups_res}
        res_subgroup_name = st.selectbox(
            "Sottogruppo KPI",
            [""] + list(subgroups_map_res.keys()),
            disabled=not res_group_id,
            key="res_subgroup_s",
        )
        res_subgroup_id = subgroups_map_res.get(res_subgroup_name)

        indicators_all_res = load_kpi_indicators_by_subgroup(res_subgroup_id)
        kpis_with_specs_res = load_all_kpis_with_hierarchy()
        indicator_ids_with_spec_res = {k["indicator_id"] for k in kpis_with_specs_res}
        indicators_map_res = {
            ind["name"]: ind["id"]
            for ind in indicators_all_res
            if ind["id"] in indicator_ids_with_spec_res
        }
        res_indicator_name = st.selectbox(
            "Indicatore KPI",
            [""] + list(indicators_map_res.keys()),
            disabled=not res_subgroup_id,
            key="res_indicator_s",
        )
        res_indicator_id = indicators_map_res.get(res_indicator_name)

        res_kpi_id = None
        res_kpi_data_obj = None
        if res_indicator_id:
            res_kpi_data_obj = next(
                (
                    kpi
                    for kpi in kpis_with_specs_res
                    if kpi["indicator_id"] == res_indicator_id
                ),
                None,
            )
            if res_kpi_data_obj:
                res_kpi_id = res_kpi_data_obj["id"]

    with vis_filt_cols[3]:
        res_period_type = st.selectbox(
            "Periodo",
            ["Giorno", "Settimana", "Mese", "Trimestre"],
            index=2,
            key="res_period_s",
        )
    with vis_filt_cols[4]:
        res_target_num = st.radio(
            "Target", [1, 2], index=0, horizontal=True, key="res_targetnum_s"
        )

    st.markdown("---")

    if not all([res_stabilimento_id, res_kpi_id, res_period_type]):
        st.info("Seleziona Anno, Stabilimento, Gerarchia KPI e Periodo.")
    else:
        try:
            ripartiti_data = load_ripartiti_data(
                res_year,
                res_stabilimento_id,
                res_kpi_id,
                res_period_type,
                res_target_num,
            )
            if not ripartiti_data:
                kpi_disp_name = (
                    get_kpi_display_name(res_kpi_data_obj)
                    if res_kpi_data_obj
                    else "N/D"
                )
                target_ann_info = load_annual_target(
                    res_year, res_stabilimento_id, res_kpi_id
                )
                prof_disp = (
                    target_ann_info.get("distribution_profile", "annual_progressive")
                    if target_ann_info
                    else "N/D"
                )
                st.info(
                    f"Nessun dato per {kpi_disp_name}, Target {res_target_num} (Profilo: {prof_disp})."
                )
            else:
                df_ripartiti = pd.DataFrame(ripartiti_data)
                df_ripartiti["Target"] = pd.to_numeric(
                    df_ripartiti["Target"], errors="coerce"
                ).round(2)
                st.dataframe(df_ripartiti, use_container_width=True, hide_index=True)

                total_sum, count = 0.0, 0
                calc_type = (
                    res_kpi_data_obj.get("calculation_type", "Incrementale")
                    if res_kpi_data_obj
                    else "Incrementale"
                )
                unit = (
                    res_kpi_data_obj.get("unit_of_measure", "")
                    if res_kpi_data_obj
                    else ""
                )
                kpi_disp_name_sum = (
                    get_kpi_display_name(res_kpi_data_obj)
                    if res_kpi_data_obj
                    else "N/D"
                )
                target_ann_info_sum = load_annual_target(
                    res_year, res_stabilimento_id, res_kpi_id
                )
                prof_disp_sum = (
                    target_ann_info_sum.get(
                        "distribution_profile", "annual_progressive"
                    )
                    if target_ann_info_sum
                    else "N/D"
                )

                for val in df_ripartiti["Target"]:
                    if pd.notna(val):
                        total_sum += val
                        count += 1

                summary = f"KPI: {kpi_disp_name_sum} | Profilo: {prof_disp_sum} | Target: {res_target_num} | "
                if count > 0:
                    summary += (
                        f"Totale ({res_period_type}): {total_sum:,.2f} {unit}"
                        if calc_type == "Incrementale"
                        else f"Media ({res_period_type}): {(total_sum/count):,.2f} {unit}"
                    )
                else:
                    summary += "Nessun dato aggregato."
                st.caption(summary)
        except Exception as e:
            st.error(f"Errore visualizzazione: {e}")

with tab6:  # Esportazione Dati
    st.header("📦 Esportazione Dati")
    export_base_path_str = "N/D"
    try:
        export_base_path_str = str(Path(db.CSV_EXPORT_BASE_PATH).resolve())
    except AttributeError:
        st.warning("CSV_EXPORT_BASE_PATH non definito in database_manager.")
    except Exception as e:
        st.warning(f"Impossibile risolvere CSV_EXPORT_BASE_PATH: {e}")

    st.markdown(
        f"CSV generati automaticamente al salvataggio dei target.\nSalvati (sul server) in: `{export_base_path_str}`"
    )

    if export_base_path_str != "N/D":
        export_path = Path(db.CSV_EXPORT_BASE_PATH)
        if not export_path.exists():
            try:
                export_path.mkdir(parents=True, exist_ok=True)
                st.info(f"Cartella esportazioni creata: {export_path}.")
            except Exception as e:
                st.error(f"Impossibile creare cartella esportazioni: {e}")

        if st.button("Esporta CSV Globali in ZIP...", type="primary"):
            if not export_path.exists() or not any(
                f.name in export_manager.GLOBAL_CSV_FILES.values()
                for f in export_path.iterdir()
                if f.is_file()
            ):
                st.warning(
                    f"Nessun CSV globale in {export_path.resolve()}. Salva prima target."
                )
            else:
                default_zip_name = f"kpi_global_data_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                temp_zip_path = export_path / default_zip_name
                try:
                    success, message_or_zip_bytes = (
                        export_manager.package_all_csvs_as_zip(
                            str(export_path), str(temp_zip_path)
                        )
                    )
                    if success:
                        with open(temp_zip_path, "rb") as fp:
                            st.download_button(
                                label="Scarica ZIP",
                                data=fp,
                                file_name=default_zip_name,
                                mime="application/zip",
                            )
                        st.success(f"Archivio ZIP '{default_zip_name}' pronto.")
                        # Consider cleaning up temp_zip_path if it's truly temporary
                    else:
                        st.error(f"Errore Esportazione ZIP: {message_or_zip_bytes}")
                except Exception as e:
                    st.error(f"Errore creazione ZIP: {e}")

        st.markdown("---")
        st.subheader("File CSV Globali Esistenti:")
        if export_path.exists() and export_path.is_dir():
            csv_files_found = [
                f
                for f in export_path.iterdir()
                if f.is_file()
                and f.suffix.lower() == ".csv"
                and f.name in export_manager.GLOBAL_CSV_FILES.values()
            ]
            if csv_files_found:
                for csv_file in csv_files_found:
                    col_file, col_btn = st.columns([3, 1])
                    with col_file:
                        st.write(
                            f"- `{csv_file.name}` (Mod: {datetime.datetime.fromtimestamp(csv_file.stat().st_mtime):%Y-%m-%d %H:%M})"
                        )
                    with col_btn, open(csv_file, "rb") as fp_csv:
                        st.download_button(
                            label=f"Scarica",
                            data=fp_csv,
                            file_name=csv_file.name,
                            mime="text/csv",
                            key=f"dl_{csv_file.stem}",
                        )
            else:
                st.info("Nessun file CSV globale. Salva target per generarli.")
        else:
            st.warning("Cartella esportazione non esistente/accessibile.")
    else:
        st.error("Percorso base esportazioni CSV non configurato.")
