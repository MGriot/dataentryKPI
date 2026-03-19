# src/interfaces/streamlit_app/components/global_splits.py
import streamlit as st
import json
import calendar
import datetime
import pandas as pd
from src.kpi_management import splits as kpi_splits_manager
from src import data_retriever
from src.services import split_analyzer
from src.interfaces.common_ui.constants import (
    REPARTITION_LOGIC_OPTIONS,
    DISTRIBUTION_PROFILE_OPTIONS,
    REPARTITION_LOGIC_YEAR,
    REPARTITION_LOGIC_MONTH,
    REPARTITION_LOGIC_QUARTER,
    REPARTITION_LOGIC_WEEK,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    PROFILE_MONTHLY_SINUSOIDAL,
    PROFILE_QUARTERLY_SINUSOIDAL,
    PROFILE_QUARTERLY_PROGRESSIVE
)

def _get_preset_values(logic, year):
    if logic == REPARTITION_LOGIC_MONTH:
        return {m: 100.0/12 for m in calendar.month_name[1:]}
    elif logic == REPARTITION_LOGIC_QUARTER:
        return {f"Q{i+1}": 25.0 for i in range(4)}
    return {}

def app():
    st.title("✂️ Global Splits Management")
    st.markdown("Manage repartition templates that can be applied to multiple KPIs.")

    # --- Sidebar: List of Splits ---
    st.sidebar.subheader("Existing Templates")
    all_splits = kpi_splits_manager.get_all_global_splits()
    
    split_names = ["+ Create New Split"] + [f"{s['year']} - {s['name']}" for s in all_splits]
    selected_split_label = st.sidebar.radio("Select Template:", split_names)

    # --- Main Layout ---
    col_config, col_inds = st.columns([1.2, 1])

    with col_config:
        if selected_split_label == "+ Create New Split":
            st.subheader("🆕 Create New Global Split")
            with st.form("new_split_form"):
                name = st.text_input("Template Name")
                year = st.number_input("Target Year", min_value=2000, max_value=2100, value=datetime.datetime.now().year)
                logic = st.selectbox("Repartition Logic", REPARTITION_LOGIC_OPTIONS)
                profile = st.selectbox("Default Distribution Profile", DISTRIBUTION_PROFILE_OPTIONS)
                
                values_json = st.text_area("Repartition Values (JSON)", value="{}")
                
                submitted = st.form_submit_button("Create Template")
                if submitted:
                    if not name: st.error("Name is required.")
                    else:
                        try:
                            v = json.loads(values_json) if values_json.strip() != "{}" else _get_preset_values(logic, year)
                            kpi_splits_manager.add_global_split(name, year, logic, v, profile, {})
                            st.success(f"Split '{name}' created!")
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
        else:
            # Edit existing
            split_id = next(s['id'] for s in all_splits if f"{s['year']} - {s['name']}" == selected_split_label)
            split = kpi_splits_manager.get_global_split(split_id)
            st.subheader(f"✏️ Edit Split: {split['name']}")
            
            # 1. Advanced Multivariate Analysis (Outside form)
            with st.expander("🚀 Advanced Multivariate Analysis", expanded=False):
                st.info("Upload historical data to suggest weights based on multiple historical targets and correlated features.")
                up = st.file_uploader("Upload CSV/XLSX", type=["csv", "xlsx"], key=f"up_{split_id}")
                if up:
                    df = pd.read_csv(up) if up.name.endswith('.csv') else pd.read_excel(up)
                    st.dataframe(df.head(3))
                    
                    cols = df.columns.tolist()
                    c1, c2 = st.columns(2)
                    with c1:
                        target_cols = st.multiselect("Historical Target Columns (to Average)", cols, help="Select multiple years of history to create a stable baseline.")
                        date_col = st.selectbox("Date/Period Column", cols)
                    with c2:
                        feature_cols = st.multiselect("Multivariate Feature Columns (Drivers)", cols)
                        p_type = st.selectbox("Analyze bucket as", ["Month", "Quarter", "Week", "Day"])
                    
                    if st.button("Calculate Multivariate Weights"):
                        if not target_cols:
                            st.warning("Please select at least one historical target column.")
                        else:
                            try:
                                weights = split_analyzer.analyze_seasonality_from_file(up, target_cols, feature_cols, date_col, p_type)
                                st.session_state[f"suggested_{split_id}"] = weights
                                st.success("Multivariate Analysis Complete!")
                                st.json(weights)
                            except Exception as e: st.error(str(e))
                
                if f"suggested_{split_id}" in st.session_state:
                    if st.button("Apply weights below"):
                        st.session_state[f"val_override_{split_id}"] = json.dumps(st.session_state[f"suggested_{split_id}"], indent=2)
                        st.rerun()

            # 2. Main Edit Form
            with st.form("edit_split_form"):
                new_name = st.text_input("Template Name", value=split['name'])
                new_year = st.number_input("Target Year", min_value=2000, max_value=2100, value=split['year'])
                new_logic = st.selectbox("Repartition Logic", REPARTITION_LOGIC_OPTIONS, index=REPARTITION_LOGIC_OPTIONS.index(split['repartition_logic']))
                new_profile = st.selectbox("Distribution Profile", DISTRIBUTION_PROFILE_OPTIONS, index=DISTRIBUTION_PROFILE_OPTIONS.index(split['distribution_profile']))
                
                initial_val = st.session_state.get(f"val_override_{split_id}", json.dumps(split['repartition_values'], indent=2))
                new_values_json = st.text_area("Repartition Values (JSON)", value=initial_val)
                
                update_btn = st.form_submit_button("Save Template Changes")
                if update_btn:
                    try:
                        v = json.loads(new_values_json)
                        kpi_splits_manager.update_global_split(split_id, name=new_name, year=new_year, repartition_logic=new_logic, repartition_values=v, distribution_profile=new_profile)
                        st.success("Template updated!")
                        if f"val_override_{split_id}" in st.session_state: del st.session_state[f"val_override_{split_id}"]
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

            if st.button("🗑️ Delete Template"):
                kpi_splits_manager.delete_global_split(split_id)
                st.success("Deleted.")
                st.rerun()

    with col_inds:
        if selected_split_label != "+ Create New Split":
            st.subheader("🎯 Afflicted KPIs")
            st.caption("Select indicators that will follow this global split.")
            
            # Fetch current selection
            current_afflicted = kpi_splits_manager.get_indicators_for_global_split(split_id)
            current_ids = [i['indicator_id'] for i in current_afflicted]
            
            all_inds = sorted(db_retriever.get_all_kpi_indicators(), key=lambda x: x['name'])
            
            # Checkbox per indicator
            ind_options = {f"{i['name']} [ID:{i['id']}]": i['id'] for i in all_inds}
            default_labels = [f"{i['name']} [ID:{i['id']}]" for i in all_inds if i['id'] in current_ids]
            
            selected_labels = st.multiselect("Add/Remove KPIs", options=list(ind_options.keys()), default=default_labels)
            
            if st.button("Sync Afflicted KPIs"):
                new_data = []
                for label in selected_labels:
                    iid = ind_options[label]
                    # Check for existing override
                    existing = next((i for i in current_afflicted if i['indicator_id'] == iid), None)
                    new_data.append({
                        'indicator_id': iid,
                        'override_distribution_profile': existing['override_distribution_profile'] if existing else None
                    })
                kpi_splits_manager.update_global_split_indicators(split_id, new_data)
                st.success("Indicators synced!")
                st.rerun()
