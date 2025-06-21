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
import numpy as np  # For pi in SINE_PHASE_OFFSET if used directly

# --- Database Setup ---
try:
    db.setup_databases()
except Exception as e:
    st.error(f"Failed to setup databases: {e}")
    # Consider st.stop() if the app cannot function without DB setup
    # st.stop()

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
    return [dict(row) for row in data]


# --- Distribution Profile & Logic Options ---
DISTRIBUTION_PROFILE_OPTIONS = [
    "even_distribution",
    "annual_progressive",
    "annual_progressive_weekday_bias",
    "true_annual_sinusoidal",
    "monthly_sinusoidal",
    "legacy_intra_period_progressive",
    "quarterly_progressive",
    "quarterly_sinusoidal",
]
REPARTITION_LOGIC_OPTIONS = ["Anno", "Mese", "Trimestre", "Settimana"]


# --- Initialize Session State (existing + new if needed) ---
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
if "hr_group_selector_sb_val" not in st.session_state:
    st.session_state.hr_group_selector_sb_val = ""
if "hr_subgroup_selector_sb_val" not in st.session_state:
    st.session_state.hr_subgroup_selector_sb_val = ""
if "hr_indicator_selector_sb_val" not in st.session_state:
    st.session_state.hr_indicator_selector_sb_val = ""


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
    st.session_state.spec_group_sel = ""
if "spec_subgroup_sel" not in st.session_state:
    st.session_state.spec_subgroup_sel = ""
if "spec_indicator_sel" not in st.session_state:
    st.session_state.spec_indicator_sel = ""


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
    load_all_kpis_with_hierarchy.clear()  # Also used by spec tab
    load_kpi_by_id.clear()  # Also used by spec tab


def clear_spec_caches():
    load_all_kpis_with_hierarchy.clear()
    load_kpi_by_id.clear()
    # Hierarchy caches might also need clearing if a spec change implies a hierarchy change visibility
    # load_kpi_groups.clear()
    # load_kpi_subgroups_by_group.clear()
    # load_kpi_indicators_by_subgroup.clear()


def clear_stabilimenti_caches():
    load_stabilimenti.clear()


def clear_target_caches():
    load_annual_target.clear()
    load_ripartiti_data.clear()
    # Also clear KPI and stabilimenti caches as they feed into target entry
    load_all_kpis_with_hierarchy.clear()
    load_stabilimenti.clear()


# --- TAB 1: Inserimento Target ---
with tab1:
    st.header("🎯 Inserimento Target Annuali")

    filt_col1, filt_col2 = st.columns(2)
    with filt_col1:
        current_year_dt = datetime.datetime.now().year
        if "target_year_sel_val" not in st.session_state:
            st.session_state.target_year_sel_val = current_year_dt
        selected_year_target = st.number_input(
            "Anno",
            min_value=2020,
            max_value=2050,
            value=st.session_state.target_year_sel_val,
            key="target_year_sel_widget",
            on_change=lambda: setattr(
                st.session_state,
                "target_year_sel_val",
                st.session_state.target_year_sel_widget,
            ),
        )
    with filt_col2:
        stabilimenti_vis_target = load_stabilimenti(only_visible=True)
        if not stabilimenti_vis_target:
            st.warning(
                "Nessuno stabilimento (visibile) definito. Aggiungine uno nella scheda 'Gestione Stabilimenti'."
            )
            st.stop()
        stabilimenti_map_target = {s["name"]: s["id"] for s in stabilimenti_vis_target}
        if "target_stabilimento_sel_val" not in st.session_state:
            st.session_state.target_stabilimento_sel_val = (
                list(stabilimenti_map_target.keys())[0]
                if stabilimenti_map_target
                else ""
            )

        selected_stabilimento_name_target = st.selectbox(
            "Stabilimento",
            options=list(stabilimenti_map_target.keys()),
            key="target_stabilimento_sel_widget",
            index=(
                list(stabilimenti_map_target.keys()).index(
                    st.session_state.target_stabilimento_sel_val
                )
                if st.session_state.target_stabilimento_sel_val
                in stabilimenti_map_target
                else 0
            ),
            on_change=lambda: setattr(
                st.session_state,
                "target_stabilimento_sel_val",
                st.session_state.target_stabilimento_sel_widget,
            ),
        )
        selected_stabilimento_id_target = stabilimenti_map_target.get(
            selected_stabilimento_name_target
        )

    if not selected_stabilimento_id_target:
        st.info("Seleziona Anno e Stabilimento per caricare i KPI.")
        st.stop()

    st.markdown("---")

    kpis_for_target_entry = [
        kpi for kpi in load_all_kpis_with_hierarchy() if kpi.get("visible", False)
    ]
    if not kpis_for_target_entry:
        st.warning(
            "Nessun KPI (visibile per target) definito. Aggiungi e/o rendi visibili le specifiche KPI."
        )
        st.stop()

    kpis_for_target_entry.sort(
        key=lambda k: (
            k.get("group_name", ""),
            k.get("subgroup_name", ""),
            k.get("indicator_name", ""),
        )
    )

    with st.form("all_targets_form"):
        targets_data_to_save = {}
        all_inputs_valid = True  # Initialize validation flag for the entire form

        for kpi_row_data in kpis_for_target_entry:
            kpi_id = kpi_row_data["id"]
            kpi_display_name_str = get_kpi_display_name(kpi_row_data)
            kpi_unit = kpi_row_data.get("unit_of_measure") or ""
            calc_type = kpi_row_data.get("calculation_type", "Incrementale")
            frame_label_text = f"{kpi_display_name_str} (Unità: {kpi_unit if kpi_unit else 'N/D'}) - Tipo: {calc_type}"
            key_prefix = (
                f"kpi_{kpi_id}_{selected_year_target}_{selected_stabilimento_id_target}"
            )

            with st.expander(frame_label_text, expanded=True):
                existing_target_db = load_annual_target(
                    selected_year_target, selected_stabilimento_id_target, kpi_id
                )
                def_t1, def_t2 = 0.0, 0.0
                def_profile = "annual_progressive"
                def_logic = "Anno"
                def_repart_map = {}

                if existing_target_db:
                    def_t1 = float(existing_target_db.get("annual_target1", 0.0) or 0.0)
                    def_t2 = float(existing_target_db.get("annual_target2", 0.0) or 0.0)
                    db_profile = existing_target_db.get("distribution_profile")
                    def_profile = (
                        db_profile
                        if db_profile in DISTRIBUTION_PROFILE_OPTIONS
                        else "annual_progressive"
                    )
                    def_logic = existing_target_db.get("repartition_logic") or "Anno"
                    repart_values_str = existing_target_db.get("repartition_values")
                    if repart_values_str:
                        try:
                            def_repart_map = json.loads(repart_values_str)
                            if not isinstance(def_repart_map, dict):
                                def_repart_map = {}
                        except json.JSONDecodeError:
                            if def_logic == "Settimana":
                                def_repart_map = {
                                    "weekly_json_initial": repart_values_str
                                }
                            else:
                                def_repart_map = {}
                if (
                    def_profile
                    in ["annual_progressive", "annual_progressive_weekday_bias"]
                    and "start_factor" not in def_repart_map
                ):
                    def_repart_map["start_factor"] = (
                        1.2 if def_profile == "annual_progressive" else 1.1
                    )
                    def_repart_map["end_factor"] = (
                        0.8 if def_profile == "annual_progressive" else 0.9
                    )

                in_col1, in_col2, in_col3 = st.columns([1, 1, 2])
                with in_col1:
                    annual_target1 = st.number_input(
                        "Target 1",
                        value=def_t1,
                        key=f"{key_prefix}_t1",
                        format="%.2f",
                        step=0.01,
                    )
                with in_col2:
                    annual_target2 = st.number_input(
                        "Target 2",
                        value=def_t2,
                        key=f"{key_prefix}_t2",
                        format="%.2f",
                        step=0.01,
                    )
                with in_col3:
                    profile_val = st.selectbox(
                        "Profilo Distribuzione",
                        DISTRIBUTION_PROFILE_OPTIONS,
                        index=DISTRIBUTION_PROFILE_OPTIONS.index(def_profile),
                        key=f"{key_prefix}_prof",
                    )

                repart_logic_val = def_logic
                show_logic_radios = True
                if profile_val in [
                    "annual_progressive",
                    "annual_progressive_weekday_bias",
                    "true_annual_sinusoidal",
                    "even_distribution",
                ]:
                    show_logic_radios = False
                    repart_logic_val = "Anno"
                elif profile_val in ["quarterly_progressive", "quarterly_sinusoidal"]:
                    if def_logic not in ["Mese", "Trimestre", "Settimana"]:
                        repart_logic_val = "Trimestre"

                if show_logic_radios:
                    repart_logic_val = st.radio(
                        "Logica Ripartizione Valori",
                        REPARTITION_LOGIC_OPTIONS,
                        index=REPARTITION_LOGIC_OPTIONS.index(repart_logic_val),
                        horizontal=True,
                        key=f"{key_prefix}_logic_radio",
                    )
                else:
                    st.caption(
                        f"Logica Ripartizione (implicita per profilo): {repart_logic_val}"
                    )

                current_repartition_values = {}
                if repart_logic_val == "Anno":
                    if profile_val in [
                        "annual_progressive",
                        "annual_progressive_weekday_bias",
                    ]:
                        fac_col1, fac_col2 = st.columns(2)
                        with fac_col1:
                            start_factor = st.number_input(
                                "Fatt. Iniziale",
                                value=float(def_repart_map.get("start_factor", 1.2)),
                                key=f"{key_prefix}_startf",
                                format="%.2f",
                                step=0.01,
                            )
                        with fac_col2:
                            end_factor = st.number_input(
                                "Fatt. Finale",
                                value=float(def_repart_map.get("end_factor", 0.8)),
                                key=f"{key_prefix}_endf",
                                format="%.2f",
                                step=0.01,
                            )
                        current_repartition_values = {
                            "start_factor": start_factor,
                            "end_factor": end_factor,
                        }
                elif repart_logic_val == "Mese":
                    st.markdown(f"**Percentuali di Ripartizione per Mese (%):**")
                    periods = [calendar.month_name[i] for i in range(1, 13)]
                    num_cols_repart = 4
                    period_cols = st.columns(num_cols_repart)
                    total_perc_month = 0.0
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
                                key=f"{key_prefix}_repart_{period_name}",
                            )
                            current_repartition_values[period_name] = perc_val
                            total_perc_month += perc_val
                    if (
                        abs(annual_target1) > 1e-9 or abs(annual_target2) > 1e-9
                    ) and not (99.9 <= total_perc_month <= 100.1):
                        st.error(
                            f"KPI {kpi_display_name_str}: Somma % Mesi = {total_perc_month:.2f}%. Deve essere ~100% se target non è zero.",
                            icon="⚠️",
                        )
                        all_inputs_valid = False
                elif repart_logic_val == "Trimestre":
                    st.markdown(f"**Percentuali di Ripartizione per Trimestre (%):**")
                    periods = ["Q1", "Q2", "Q3", "Q4"]
                    num_cols_repart = 4
                    period_cols = st.columns(num_cols_repart)
                    total_perc_quarter = 0.0
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
                                key=f"{key_prefix}_repart_{period_name}",
                            )
                            current_repartition_values[period_name] = perc_val
                            total_perc_quarter += perc_val
                    if (
                        abs(annual_target1) > 1e-9 or abs(annual_target2) > 1e-9
                    ) and not (99.9 <= total_perc_quarter <= 100.1):
                        st.error(
                            f"KPI {kpi_display_name_str}: Somma % Trimestri = {total_perc_quarter:.2f}%. Deve essere ~100% se target non è zero.",
                            icon="⚠️",
                        )
                        all_inputs_valid = False
                elif repart_logic_val == "Settimana":
                    st.markdown(f"**Valori Settimanali (JSON):**")
                    initial_json_str = def_repart_map.get(
                        "weekly_json_initial",
                        json.dumps(
                            (
                                def_repart_map
                                if def_repart_map
                                and "weekly_json_initial" not in def_repart_map
                                else {"Info": 'Es: {"2024-W01": 2.5}'}
                            ),
                            indent=2,
                        ),
                    )
                    weekly_json_str = st.text_area(
                        "JSON Settimane",
                        value=initial_json_str,
                        height=100,
                        key=f"{key_prefix}_weekly_json",
                        help='Es: {"2024-W01": 2.5, ...} per % o {"2024-W01": 110} per moltiplicatori Media',
                    )
                    current_repartition_values = {
                        "weekly_json_text_content": weekly_json_str
                    }

                targets_data_to_save[kpi_id] = {
                    "annual_target1": annual_target1,
                    "annual_target2": annual_target2,
                    "distribution_profile": profile_val,
                    "repartition_logic": repart_logic_val,
                    "repartition_values_ui": current_repartition_values,
                }
                st.caption(f"Profilo: {profile_val}, Logica Rip.: {repart_logic_val}")
                st.markdown("---")

        submitted_all_targets = st.form_submit_button(
            "SALVA TUTTI I TARGET", type="primary", use_container_width=True
        )

        if submitted_all_targets:
            if not all_inputs_valid:
                st.error(
                    "Correggi gli errori di validazione nelle percentuali prima di salvare."
                )
            elif not targets_data_to_save:
                st.warning("Nessun target definito per il salvataggio.")
            else:
                final_targets_for_db = {}
                conversion_error = False
                for kpi_id_save, data_from_ui in targets_data_to_save.items():
                    actual_repart_values = {}
                    logic_saved = data_from_ui["repartition_logic"]
                    ui_values = data_from_ui["repartition_values_ui"]

                    if logic_saved == "Settimana":
                        json_str_to_parse = ui_values.get(
                            "weekly_json_text_content", "{}"
                        )
                        if not json_str_to_parse.strip():
                            json_str_to_parse = "{}"
                        try:
                            actual_repart_values = json.loads(json_str_to_parse)
                            if not isinstance(actual_repart_values, dict):
                                st.error(
                                    f"KPI ID {kpi_id_save}: L'input settimanale deve essere un JSON object (es. {{...}}). Trovato: {type(actual_repart_values)}",
                                    icon="⚠️",
                                )
                                conversion_error = True
                                break
                        except json.JSONDecodeError:
                            st.error(
                                f"KPI ID {kpi_id_save}: Formato JSON non valido per i valori settimanali.",
                                icon="⚠️",
                            )
                            conversion_error = True
                            break
                    else:
                        actual_repart_values = ui_values

                    if conversion_error:
                        break

                    final_targets_for_db[kpi_id_save] = {
                        "annual_target1": data_from_ui["annual_target1"],
                        "annual_target2": data_from_ui["annual_target2"],
                        "distribution_profile": data_from_ui["distribution_profile"],
                        "repartition_logic": logic_saved,
                        "repartition_values": actual_repart_values,
                        "profile_params": {},
                    }

                if not conversion_error:
                    try:
                        db.save_annual_targets(
                            selected_year_target,
                            selected_stabilimento_id_target,
                            final_targets_for_db,
                        )
                        st.success(
                            "Target salvati e ripartizioni ricalcolate con successo!"
                        )
                        clear_target_caches()
                        st.balloons()
                    except Exception as e:
                        st.error(
                            f"Errore durante il salvataggio o il ricalcolo delle ripartizioni: {e}"
                        )
                        import traceback

                        st.error(traceback.format_exc())

# --- TAB 2: Gestione Gerarchia KPI ---
with tab2:
    st.header("🗂️ Gestione Gerarchia KPI")

    def reset_hr_edit_state():
        st.session_state.hr_editing_item_type = None
        st.session_state.hr_editing_item_id = None
        st.session_state.hr_editing_item_name = ""
        st.session_state.hr_group_selector_sb_val = ""
        st.session_state.hr_subgroup_selector_sb_val = ""
        st.session_state.hr_indicator_selector_sb_val = ""

    if (
        "hr_group_to_select_after_save" in st.session_state
        and st.session_state.hr_group_to_select_after_save
    ):
        st.session_state.hr_group_selector_sb_val = (
            st.session_state.hr_group_to_select_after_save
        )
        del st.session_state.hr_group_to_select_after_save
    if (
        "hr_subgroup_to_select_after_save" in st.session_state
        and st.session_state.hr_subgroup_to_select_after_save
    ):
        st.session_state.hr_subgroup_selector_sb_val = (
            st.session_state.hr_subgroup_to_select_after_save
        )
        del st.session_state.hr_subgroup_to_select_after_save
    if (
        "hr_indicator_to_select_after_save" in st.session_state
        and st.session_state.hr_indicator_to_select_after_save
    ):
        st.session_state.hr_indicator_selector_sb_val = (
            st.session_state.hr_indicator_to_select_after_save
        )
        del st.session_state.hr_indicator_to_select_after_save

    with st.container(border=True):
        st.subheader("Gruppi KPI")
        groups = load_kpi_groups()
        groups_map = {g["name"]: g["id"] for g in groups}
        group_options = [""] + list(groups_map.keys())
        try:
            group_idx = group_options.index(st.session_state.hr_group_selector_sb_val)
        except ValueError:
            group_idx = 0

        selected_group_name_hr = st.selectbox(
            "Seleziona Gruppo",
            options=group_options,
            key="hr_group_selector_widget",
            index=group_idx,
            on_change=lambda: (
                setattr(
                    st.session_state,
                    "hr_group_selector_sb_val",
                    st.session_state.hr_group_selector_widget,
                ),
                setattr(st.session_state, "hr_selected_subgroup_id", None),
                setattr(st.session_state, "hr_selected_indicator_id", None),
                setattr(st.session_state, "hr_subgroup_selector_sb_val", ""),
                setattr(st.session_state, "hr_indicator_selector_sb_val", ""),
            ),
        )
        st.session_state.hr_selected_group_id = groups_map.get(selected_group_name_hr)
        if st.session_state.hr_group_selector_sb_val != selected_group_name_hr:
            st.session_state.hr_group_selector_sb_val = selected_group_name_hr

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
                        db.delete_kpi_group(st.session_state.hr_selected_group_id)
                        st.success(f"Gruppo '{selected_group_name_hr}' eliminato.")
                        clear_hierarchy_caches()
                        clear_spec_caches()
                        st.session_state.hr_selected_group_id = None
                        st.session_state.hr_group_selector_sb_val = ""
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
                if st.form_submit_button("Salva"):
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
                            st.session_state.hr_group_to_select_after_save = (
                                new_group_name_input
                            )
                            reset_hr_edit_state()
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
            subgroup_options = [""] + list(subgroups_map.keys())
            try:
                subgroup_idx = subgroup_options.index(
                    st.session_state.hr_subgroup_selector_sb_val
                )
            except ValueError:
                subgroup_idx = 0
            selected_subgroup_name_hr = st.selectbox(
                "Seleziona Sottogruppo",
                options=subgroup_options,
                key="hr_subgroup_selector_widget",
                index=subgroup_idx,
                on_change=lambda: (
                    setattr(
                        st.session_state,
                        "hr_subgroup_selector_sb_val",
                        st.session_state.hr_subgroup_selector_widget,
                    ),
                    setattr(st.session_state, "hr_selected_indicator_id", None),
                    setattr(st.session_state, "hr_indicator_selector_sb_val", ""),
                ),
            )
            st.session_state.hr_selected_subgroup_id = subgroups_map.get(
                selected_subgroup_name_hr
            )
            if (
                st.session_state.hr_subgroup_selector_sb_val
                != selected_subgroup_name_hr
            ):
                st.session_state.hr_subgroup_selector_sb_val = selected_subgroup_name_hr
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
                        st.session_state.hr_subgroup_selector_sb_val = ""
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
                    if st.form_submit_button("Salva"):
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
                                st.session_state.hr_subgroup_to_select_after_save = (
                                    new_subgroup_name_input
                                )
                                reset_hr_edit_state()
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
            indicator_options = [""] + list(indicators_map.keys())
            try:
                indicator_idx = indicator_options.index(
                    st.session_state.hr_indicator_selector_sb_val
                )
            except ValueError:
                indicator_idx = 0
            selected_indicator_name_hr = st.selectbox(
                "Seleziona Indicatore",
                options=indicator_options,
                key="hr_indicator_selector_widget",
                index=indicator_idx,
                on_change=lambda: setattr(
                    st.session_state,
                    "hr_indicator_selector_sb_val",
                    st.session_state.hr_indicator_selector_widget,
                ),
            )
            st.session_state.hr_selected_indicator_id = indicators_map.get(
                selected_indicator_name_hr
            )
            if (
                st.session_state.hr_indicator_selector_sb_val
                != selected_indicator_name_hr
            ):
                st.session_state.hr_indicator_selector_sb_val = (
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
                        st.session_state.hr_indicator_selector_sb_val = ""
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
                    if st.form_submit_button("Salva"):
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
                                st.session_state.hr_indicator_to_select_after_save = (
                                    new_indicator_name_input
                                )
                                reset_hr_edit_state()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore salvataggio indicatore: {e}")
        else:
            st.info("Seleziona un Sottogruppo KPI.")

# --- TAB 3: Gestione Specifiche KPI ---
with tab3:
    st.header("⚙️ Gestione Specifiche KPI")
    with st.expander("Aggiungi/Modifica Specifica KPI", expanded=True):

        def spec_group_changed():
            st.session_state.spec_subgroup_sel = ""
            st.session_state.spec_indicator_sel = ""
            st.session_state.spec_selected_subgroup_id = None
            st.session_state.spec_selected_indicator_id = None
            st.session_state.spec_editing_kpi_id = None
            if (
                "spec_manual_selection" not in st.session_state
                or st.session_state.spec_manual_selection
            ):  # Trigger only on actual user change
                st.session_state.spec_form_data = {
                    "description": "",
                    "calculation_type": "Incrementale",
                    "unit_of_measure": "",
                    "visible": True,
                }

        def spec_subgroup_changed():
            st.session_state.spec_indicator_sel = ""
            st.session_state.spec_selected_indicator_id = None
            st.session_state.spec_editing_kpi_id = None
            if (
                "spec_manual_selection" not in st.session_state
                or st.session_state.spec_manual_selection
            ):
                st.session_state.spec_form_data = {
                    "description": "",
                    "calculation_type": "Incrementale",
                    "unit_of_measure": "",
                    "visible": True,
                }

        def spec_indicator_changed():  # Called by on_change of indicator selectbox
            st.session_state.spec_editing_kpi_id = None  # Reset editing ID first
            st.session_state.spec_form_data = {
                "description": "",
                "calculation_type": "Incrementale",
                "unit_of_measure": "",
                "visible": True,
            }  # Reset form

            # Update selected_indicator_id from the widget's current value (which is st.session_state.spec_indicator_sel)
            # This logic is now mostly inside the selectbox's on_change or after its definition.
            # For clarity, this function now primarily loads data if an indicator_id is found.
            selected_indicator_id_from_sel = st.session_state.get(
                "spec_selected_indicator_id_from_widget"
            )

            if selected_indicator_id_from_sel:
                all_kpis = load_all_kpis_with_hierarchy()
                existing_kpi_spec = next(
                    (
                        kpi
                        for kpi in all_kpis
                        if kpi["indicator_id"] == selected_indicator_id_from_sel
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
            st.session_state.spec_group_sel = st.selectbox(
                "Gruppo",
                [""] + list(groups_spec_map.keys()),
                key="spec_group_sel_key",
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

            def spec_indicator_selectbox_on_change_handler():
                # This function will be called when the selectbox value changes.
                # It updates a temporary session state that spec_indicator_changed can then use.
                st.session_state.spec_selected_indicator_id_from_widget = (
                    available_indicators_spec_map.get(
                        st.session_state.spec_indicator_sel_key_widget
                    )
                )
                spec_indicator_changed()  # Now call the original change handler

            st.session_state.spec_indicator_sel = st.selectbox(
                "Indicatore",
                [""] + list(available_indicators_spec_map.keys()),
                key="spec_indicator_sel_key_widget",
                index=(
                    ([""] + list(available_indicators_spec_map.keys())).index(
                        st.session_state.spec_indicator_sel
                    )
                    if st.session_state.spec_indicator_sel
                    in ([""] + list(available_indicators_spec_map.keys()))
                    else 0
                ),
                disabled=not st.session_state.spec_selected_subgroup_id,
                on_change=spec_indicator_selectbox_on_change_handler,
            )
            # Primary update of spec_selected_indicator_id based on current selectbox name
            st.session_state.spec_selected_indicator_id = (
                available_indicators_spec_map.get(st.session_state.spec_indicator_sel)
            )

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
            if st.form_submit_button(form_action_button_text):
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
                        clear_hierarchy_caches()  # Clear hierarchy too as it might affect "available indicators" list
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
                    f"Sicuro di eliminare: {st.session_state.confirm_delete_spec_name} e tutti i target associati?",
                    icon="🗑️",
                )
                c_del_spec1, c_del_spec2, _ = st.columns([1, 1, 5])
                if c_del_spec1.button(
                    "Sì, Elimina", type="primary", key="confirm_del_spec_yes_final"
                ):
                    try:
                        kpi_id_to_delete = st.session_state.confirm_delete_spec_id
                        with sqlite3.connect(db.DB_TARGETS) as conn_targets:
                            conn_targets.execute(
                                "DELETE FROM annual_targets WHERE kpi_id = ?",
                                (kpi_id_to_delete,),
                            )
                            conn_targets.commit()
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
                                conn_periodic.commit()
                        with sqlite3.connect(db.DB_KPIS) as conn_kpis:
                            conn_kpis.execute(
                                "DELETE FROM kpis WHERE id = ?", (kpi_id_to_delete,)
                            )
                            conn_kpis.commit()
                        st.success("Specifica KPI e target associati eliminati.")
                        clear_spec_caches()
                        clear_target_caches()
                        clear_hierarchy_caches()
                        del st.session_state.confirm_delete_spec_id
                        st.session_state.spec_manage_select = ""
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore eliminazione: {e}")
                if c_del_spec2.button("No, Annulla", key="confirm_del_spec_no_final"):
                    del st.session_state.confirm_delete_spec_id
                    st.rerun()
    else:
        st.info("Nessuna specifica KPI definita.")

# --- TAB 4: Gestione Stabilimenti ---
with tab4:
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
            if st.form_submit_button("Salva Stabilimento"):
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
        ):
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

# --- TAB 5: Visualizzazione Risultati ---
with tab5:
    st.header("📈 Visualizzazione Risultati Ripartiti")
    vis_filt_cols = st.columns([1, 2, 2, 1, 1])
    with vis_filt_cols[0]:
        res_year = st.number_input(
            "Anno ",
            min_value=2020,
            max_value=2050,
            value=datetime.datetime.now().year,
            key="res_year_s",
        )
    with vis_filt_cols[1]:
        stabilimenti_res = load_stabilimenti()
        stabilimenti_map_res = {s["name"]: s["id"] for s in stabilimenti_res}
        res_stabilimento_name = st.selectbox(
            "Stabilimento ",
            [""] + list(stabilimenti_map_res.keys()),
            key="res_stabilimento_s",
        )
        res_stabilimento_id = stabilimenti_map_res.get(res_stabilimento_name)
    res_kpi_id_for_display = None
    res_kpi_data_obj_for_display = None
    with vis_filt_cols[2]:
        groups_res = load_kpi_groups()
        groups_map_res = {g["name"]: g["id"] for g in groups_res}
        res_group_name = st.selectbox(
            "Gruppo KPI ", [""] + list(groups_map_res.keys()), key="res_group_s"
        )
        res_group_id = groups_map_res.get(res_group_name)
        subgroups_res = load_kpi_subgroups_by_group(res_group_id)
        subgroups_map_res = {sg["name"]: sg["id"] for sg in subgroups_res}
        res_subgroup_name = st.selectbox(
            "Sottogruppo KPI ",
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
            "Indicatore KPI ",
            [""] + list(indicators_map_res.keys()),
            disabled=not res_subgroup_id,
            key="res_indicator_s",
        )
        res_indicator_id = indicators_map_res.get(res_indicator_name)
        if res_indicator_id:
            res_kpi_data_obj_for_display = next(
                (
                    kpi_spec
                    for kpi_spec in kpis_with_specs_res
                    if kpi_spec["indicator_id"] == res_indicator_id
                ),
                None,
            )
            if res_kpi_data_obj_for_display:
                res_kpi_id_for_display = res_kpi_data_obj_for_display["id"]
    with vis_filt_cols[3]:
        res_period_type = st.selectbox(
            "Periodo ",
            ["Giorno", "Settimana", "Mese", "Trimestre"],
            index=2,
            key="res_period_s",
        )
    with vis_filt_cols[4]:
        st.caption("Mostra Target 1 & 2")  # Placeholder
    st.markdown("---")

    if not all([res_stabilimento_id, res_kpi_id_for_display, res_period_type]):
        st.info(
            "Seleziona Anno, Stabilimento, Gerarchia KPI completa e Periodo per visualizzare i dati."
        )
    else:
        try:
            data_t1 = load_ripartiti_data(
                res_year,
                res_stabilimento_id,
                res_kpi_id_for_display,
                res_period_type,
                1,
            )
            data_t2 = load_ripartiti_data(
                res_year,
                res_stabilimento_id,
                res_kpi_id_for_display,
                res_period_type,
                2,
            )
            if not data_t1 and not data_t2:
                kpi_disp_name = (
                    get_kpi_display_name(res_kpi_data_obj_for_display)
                    if res_kpi_data_obj_for_display
                    else "N/D"
                )
                target_ann_info = load_annual_target(
                    res_year, res_stabilimento_id, res_kpi_id_for_display
                )
                prof_disp = (
                    target_ann_info.get("distribution_profile", "N/D")
                    if target_ann_info
                    else "N/D"
                )
                st.info(
                    f"Nessun dato ripartito per {kpi_disp_name} (Profilo: {prof_disp})."
                )
            else:
                df_t1 = (
                    pd.DataFrame(data_t1).rename(columns={"Target": "Valore Target 1"})
                    if data_t1
                    else pd.DataFrame(columns=["Periodo", "Valore Target 1"])
                )
                df_t2 = (
                    pd.DataFrame(data_t2).rename(columns={"Target": "Valore Target 2"})
                    if data_t2
                    else pd.DataFrame(columns=["Periodo", "Valore Target 2"])
                )
                if not df_t1.empty and not df_t2.empty:
                    df_merged = pd.merge(df_t1, df_t2, on="Periodo", how="outer")
                elif not df_t1.empty:
                    df_merged = df_t1
                    df_merged["Valore Target 2"] = np.nan
                elif not df_t2.empty:
                    df_merged = df_t2
                    df_merged["Valore Target 1"] = np.nan
                    if (
                        "Periodo" in df_merged.columns
                        and df_merged.columns[0] != "Periodo"
                    ):
                        df_merged = df_merged[
                            ["Periodo"]
                            + [col for col in df_merged.columns if col != "Periodo"]
                        ]
                else:
                    df_merged = pd.DataFrame(
                        columns=["Periodo", "Valore Target 1", "Valore Target 2"]
                    )
                for col in ["Valore Target 1", "Valore Target 2"]:
                    if col in df_merged.columns:
                        df_merged[col] = pd.to_numeric(
                            df_merged[col], errors="coerce"
                        ).round(2)
                st.dataframe(df_merged, use_container_width=True, hide_index=True)
                calc_type = (
                    res_kpi_data_obj_for_display.get("calculation_type", "Incrementale")
                    if res_kpi_data_obj_for_display
                    else "Incrementale"
                )
                unit = (
                    res_kpi_data_obj_for_display.get("unit_of_measure", "")
                    if res_kpi_data_obj_for_display
                    else ""
                )
                kpi_disp_name_sum = (
                    get_kpi_display_name(res_kpi_data_obj_for_display)
                    if res_kpi_data_obj_for_display
                    else "N/D"
                )
                target_ann_info_sum = load_annual_target(
                    res_year, res_stabilimento_id, res_kpi_id_for_display
                )
                prof_disp_sum = (
                    target_ann_info_sum.get("distribution_profile", "N/D")
                    if target_ann_info_sum
                    else "N/D"
                )
                summary_parts = [
                    f"KPI: {kpi_disp_name_sum}",
                    f"Profilo: {prof_disp_sum}",
                ]
                if (
                    "Valore Target 1" in df_merged.columns
                    and df_merged["Valore Target 1"].notna().any()
                ):
                    total_sum_t1 = df_merged["Valore Target 1"].sum()
                    count_t1 = df_merged["Valore Target 1"].notna().sum()
                    if count_t1 > 0:
                        agg_val_t1 = (
                            total_sum_t1
                            if calc_type == "Incrementale"
                            else (total_sum_t1 / count_t1)
                        )
                        label_t1 = (
                            "Totale T1" if calc_type == "Incrementale" else "Media T1"
                        )
                        summary_parts.append(
                            f"{label_t1} ({res_period_type}): {agg_val_t1:,.2f} {unit}"
                        )
                if (
                    "Valore Target 2" in df_merged.columns
                    and df_merged["Valore Target 2"].notna().any()
                ):
                    total_sum_t2 = df_merged["Valore Target 2"].sum()
                    count_t2 = df_merged["Valore Target 2"].notna().sum()
                    if count_t2 > 0:
                        agg_val_t2 = (
                            total_sum_t2
                            if calc_type == "Incrementale"
                            else (total_sum_t2 / count_t2)
                        )
                        label_t2 = (
                            "Totale T2" if calc_type == "Incrementale" else "Media T2"
                        )
                        summary_parts.append(
                            f"{label_t2} ({res_period_type}): {agg_val_t2:,.2f} {unit}"
                        )
                st.caption(" | ".join(summary_parts))
        except Exception as e:
            st.error(f"Errore durante la visualizzazione dei risultati: {e}")
            import traceback

            st.error(traceback.format_exc())

# --- TAB 6: Esportazione Dati ---
with tab6:
    st.header("📦 Esportazione Dati")
    export_base_path_str = "N/D"
    try:
        export_base_path_str = str(Path(db.CSV_EXPORT_BASE_PATH).resolve())
    except AttributeError:
        st.warning("CSV_EXPORT_BASE_PATH non definito in database_manager.")
    except Exception as e:
        st.warning(f"Impossibile risolvere CSV_EXPORT_BASE_PATH: {e}")
    st.markdown(
        f"I CSV globali vengono generati/sovrascritti automaticamente ogni volta che si salvano i target annuali.\nQuesti file sono salvati (sul server che esegue questa app Streamlit) in:\n`{export_base_path_str}`"
    )
    if export_base_path_str != "N/D":
        export_path = Path(db.CSV_EXPORT_BASE_PATH)
        if not export_path.exists():
            try:
                export_path.mkdir(parents=True, exist_ok=True)
                st.info(f"Cartella esportazioni creata: {export_path}.")
            except Exception as e:
                st.error(f"Impossibile creare cartella esportazioni: {e}")
        if st.button("Esporta CSV Globali in un File ZIP...", type="primary"):
            expected_csv_filenames_to_check = getattr(
                export_manager, "GLOBAL_CSV_FILES", {}
            ).values()
            if not export_path.exists() or not any(
                f.name in expected_csv_filenames_to_check
                for f in export_path.iterdir()
                if f.is_file()
            ):
                st.warning(
                    f"Nessuno dei file CSV globali attesi è stato trovato in {export_path.resolve()}. Salva prima qualche target."
                )
            else:
                default_zip_name = f"kpi_global_data_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                temp_zip_path_on_server = export_path / default_zip_name
                try:
                    success, message_or_path = export_manager.package_all_csvs_as_zip(
                        str(export_path), str(temp_zip_path_on_server)
                    )
                    if success:
                        with open(temp_zip_path_on_server, "rb") as fp:
                            st.download_button(
                                label=f"Scarica {default_zip_name}",
                                data=fp,
                                file_name=default_zip_name,
                                mime="application/zip",
                            )
                        st.success(
                            f"Archivio ZIP '{default_zip_name}' pronto per il download."
                        )
                    else:
                        st.error(f"Errore Esportazione ZIP: {message_or_path}")
                except Exception as e:
                    st.error(f"Errore imprevisto durante la creazione dello ZIP: {e}")
        st.markdown("---")
        st.subheader("File CSV Globali Esistenti (sul server):")
        if export_path.exists() and export_path.is_dir():
            expected_csv_filenames = getattr(
                export_manager, "GLOBAL_CSV_FILES", {}
            ).values()
            if not expected_csv_filenames:
                st.warning(
                    "`export_manager.GLOBAL_CSV_FILES` non definito o vuoto. Impossibile elencare i file attesi."
                )
            else:
                csv_files_found = [
                    f
                    for f in export_path.iterdir()
                    if f.is_file()
                    and f.suffix.lower() == ".csv"
                    and f.name in expected_csv_filenames
                ]
                if csv_files_found:
                    for csv_file in csv_files_found:
                        col_file, col_btn = st.columns([3, 1])
                        with col_file:
                            st.write(
                                f"- `{csv_file.name}` (Mod: {datetime.datetime.fromtimestamp(csv_file.stat().st_mtime):%Y-%m-%d %H:%M})"
                            )
                        with col_btn:
                            try:
                                with open(csv_file, "rb") as fp_csv:
                                    st.download_button(
                                        label=f"Scarica",
                                        data=fp_csv.read(),
                                        file_name=csv_file.name,
                                        mime="text/csv",
                                        key=f"dl_{csv_file.stem}",
                                    )
                            except Exception as e:
                                st.error(f"Err lettura {csv_file.name}: {e}")
                else:
                    st.info(
                        "Nessun file CSV globale corrispondente ai file attesi. Salva target per generarli."
                    )
        else:
            st.warning(
                f"Cartella esportazione non trovata o non accessibile: {export_path}"
            )
    else:
        st.error(
            "Percorso base per le esportazioni CSV non configurato correttamente in database_manager.py."
        )