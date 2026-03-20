# src/interfaces/streamlit_app/components/global_splits.py
import streamlit as st
import json
import calendar
import datetime
import pandas as pd
import tempfile
import os
import plotly.express as px
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
        return {m: 100.0/12 for m in calendar.month_name[1:] if m}
    elif logic == REPARTITION_LOGIC_QUARTER:
        return {f"Q{i+1}": 25.0 for i in range(4)}
    return {}

def _render_multivariate_section(context_id):
    """Renders the predictor UI and returns the suggested weights if applied."""
    st.markdown("---")
    st.subheader("🚀 Multivariate Seasonality Predictor")
    st.markdown("Predict weights using external data drivers (e.g. Weather, Market, History).")
    
    with st.container(border=True):
        up = st.file_uploader("Upload CSV/XLSX for Analysis", type=["csv", "xlsx"], key=f"up_{context_id}")
        if up:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(up.name)[1]) as tmp:
                tmp.write(up.getvalue())
                tmp_path = tmp.name

            try:
                df = pd.read_csv(tmp_path) if up.name.endswith('.csv') else pd.read_excel(tmp_path)
                st.dataframe(df.head(3), use_container_width=True)
                
                cols = df.columns.tolist()
                c1, c2 = st.columns(2)
                with c1:
                    target_cols = st.multiselect("Target History Columns", cols, key=f"tcols_{context_id}")
                    date_col = st.selectbox("Timeline Column", cols, key=f"dcol_{context_id}")
                with c2:
                    feature_cols = st.multiselect("Driver Columns", cols, key=f"fcols_{context_id}")
                    p_type = st.selectbox("Aggregate as", ["Month", "Quarter", "Week", "Day"], key=f"ptype_{context_id}")
                
                if st.button("Calculate Predictive Split", type="primary", use_container_width=True, key=f"run_{context_id}"):
                    if not target_cols:
                        st.warning("Select target columns.")
                    else:
                        with st.spinner("Analyzing..."):
                            weights, coefficients, r_squared, plot_df = split_analyzer.analyze_seasonality_from_file(
                                tmp_path, target_cols, feature_cols, date_col, p_type
                            )
                            final_vals = {k: round(v * 100, 4) for k, v in weights.items()}
                            if p_type == "Month":
                                final_vals = {calendar.month_name[int(k)]: v for k, v in final_vals.items()}

                            st.session_state[f"suggested_{context_id}"] = final_vals
                            st.session_state[f"model_stats_{context_id}"] = {
                                "r2": r_squared, 
                                "coefs": coefficients,
                                "plot_data": plot_df.to_json()
                            }
                
                if f"suggested_{context_id}" in st.session_state:
                    stats = st.session_state[f"model_stats_{context_id}"]
                    st.success(f"**Fit Accuracy (R²):** `{stats['r2']:.4f}`")
                    
                    st.markdown("#### 📈 Model Fit Visualization")
                    plot_df = pd.read_json(stats['plot_data'])
                    melted_df = plot_df.melt(id_vars=['period_idx'], var_name='Variable', value_name='Normalized Value')
                    fig = px.line(melted_df, x='period_idx', y='Normalized Value', color='Variable', markers=True)
                    fig.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0))
                    st.plotly_chart(fig, use_container_width=True, key=f"plot_{context_id}")

                    res_c1, res_c2 = st.columns([1, 1.2])
                    with res_c1:
                        st.markdown("**Driver Influence:**")
                        for feat, coef in stats['coefs'].items():
                            st.write(f"- {feat}: `{coef:.4f}`")
                    with res_c2:
                        st.markdown("**Predicted Weights:**")
                        st.json(st.session_state[f"suggested_{context_id}"])
                    
                    if st.button("Apply to Template Below", use_container_width=True, key=f"apply_{context_id}"):
                        st.session_state[f"val_override_{context_id}"] = json.dumps(st.session_state[f"suggested_{context_id}"], indent=2)
                        st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(tmp_path): os.remove(tmp_path)

def app():
    st.title("✂️ Global Splits Management")
    st.markdown("Manage repartition templates that can be applied to multiple KPIs.")

    # --- Sidebar: List of Splits ---
    st.sidebar.subheader("Existing Templates")
    all_splits = kpi_splits_manager.get_all_global_splits()
    
    split_names = ["+ Create New Split"] + [f"{s['year']} - {s['name']}" for s in all_splits]
    selected_split_label = st.sidebar.radio("Select Template:", split_names)

    # Prepare common data
    all_inds = sorted(data_retriever.get_all_kpi_indicators(), key=lambda x: x['name'])
    ind_options = {f"{i['name']} [ID:{i['id']}]": i['id'] for i in all_inds}

    # --- Main Layout ---
    col_config, col_inds = st.columns([1.4, 1])

    if selected_split_label == "+ Create New Split":
        with col_config:
            st.subheader("🆕 Create New Global Split")
            _render_multivariate_section("new_split")
            
            st.markdown("---")
            st.subheader("📋 Template Details")
            with st.form("new_split_form"):
                name = st.text_input("Template Name")
                year = st.number_input("Target Year", min_value=2000, max_value=2100, value=datetime.datetime.now().year)
                logic = st.selectbox("Repartition Logic", REPARTITION_LOGIC_OPTIONS)
                profile = st.selectbox("Default Distribution Profile", DISTRIBUTION_PROFILE_OPTIONS)
                
                initial_val = st.session_state.get("val_override_new_split", "{}")
                values_json = st.text_area("Repartition Weights (%)", value=initial_val, height=200)
                
                # In creation mode, we'll store the indicators in session state before form submission
                st.markdown("*(Select KPIs in the right column before saving)*")
                
                submitted = st.form_submit_button("Create Template & Link KPIs", type="primary")
                if submitted:
                    if not name: st.error("Name is required.")
                    else:
                        try:
                            # 1. Add split
                            v = json.loads(values_json) if values_json.strip() not in ["{}", ""] else _get_preset_values(logic, year)
                            new_id = kpi_splits_manager.add_global_split(name, year, logic, v, profile, {})
                            
                            # 2. Link indicators from session state
                            selected_labels = st.session_state.get("temp_inds_selection", [])
                            if selected_labels:
                                new_links = [{'indicator_id': ind_options[label]} for label in selected_labels]
                                kpi_splits_manager.update_global_split_indicators(new_id, new_links)
                            
                            st.success(f"Split '{name}' created and linked!")
                            if "val_override_new_split" in st.session_state: del st.session_state["val_override_new_split"]
                            if "temp_inds_selection" in st.session_state: del st.session_state["temp_inds_selection"]
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

        with col_inds:
            st.subheader("🎯 Affected KPIs")
            st.caption("Select indicators that will follow this new template.")
            st.multiselect("Select KPIs to Link", options=list(ind_options.keys()), key="temp_inds_selection")

    else:
        # Edit existing
        split_id = next(s['id'] for s in all_splits if f"{s['year']} - {s['name']}" == selected_split_label)
        split = kpi_splits_manager.get_global_split(split_id)
        
        with col_config:
            st.subheader(f"✏️ Edit Split: {split['name']}")
            _render_multivariate_section(f"edit_{split_id}")

            st.markdown("---")
            st.subheader("📋 Template Details")
            with st.form("edit_split_form"):
                new_name = st.text_input("Template Name", value=split['name'])
                new_year = st.number_input("Target Year", min_value=2000, max_value=2100, value=split['year'])
                new_logic = st.selectbox("Repartition Logic", REPARTITION_LOGIC_OPTIONS, 
                                       index=REPARTITION_LOGIC_OPTIONS.index(split['repartition_logic']) 
                                       if split['repartition_logic'] in REPARTITION_LOGIC_OPTIONS else 0)
                new_profile = st.selectbox("Distribution Profile", DISTRIBUTION_PROFILE_OPTIONS, 
                                         index=DISTRIBUTION_PROFILE_OPTIONS.index(split['distribution_profile'])
                                         if split['distribution_profile'] in DISTRIBUTION_PROFILE_OPTIONS else 0)
                
                initial_val = st.session_state.get(f"val_override_edit_{split_id}", json.dumps(split['repartition_values'], indent=2))
                new_values_json = st.text_area("Repartition Weights (%)", value=initial_val, height=200)
                
                update_btn = st.form_submit_button("Save Template Changes", type="primary")
                if update_btn:
                    try:
                        v = json.loads(new_values_json)
                        kpi_splits_manager.update_global_split(split_id, name=new_name, year=new_year, 
                                                             repartition_logic=new_logic, repartition_values=v, 
                                                             distribution_profile=new_profile)
                        st.success("Template updated!")
                        if f"val_override_edit_{split_id}" in st.session_state: del st.session_state[f"val_override_edit_{split_id}"]
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

            if st.button("🗑️ Delete Template", use_container_width=True):
                if st.checkbox("Confirm permanent deletion."):
                    kpi_splits_manager.delete_global_split(split_id)
                    st.success("Deleted.")
                    st.rerun()

        with col_inds:
            st.subheader("🎯 Affected KPIs")
            st.caption("Indicators following this split template.")
            
            current_afflicted = kpi_splits_manager.get_indicators_for_global_split(split_id)
            current_ids = [i['indicator_id'] for i in current_afflicted]
            default_labels = [f"{i['name']} [ID:{i['id']}]" for i in all_inds if i['id'] in current_ids]
            
            selected_labels = st.multiselect("Select KPIs to Link", options=list(ind_options.keys()), default=default_labels, key=f"inds_edit_{split_id}")
            
            if st.button("Sync KPI Links", type="primary", use_container_width=True):
                new_data = []
                for label in selected_labels:
                    iid = ind_options[label]
                    existing = next((i for i in current_afflicted if i['indicator_id'] == iid), None)
                    new_data.append({
                        'indicator_id': iid,
                        'override_distribution_profile': existing['override_distribution_profile'] if existing else None
                    })
                kpi_splits_manager.update_global_split_indicators(split_id, new_data)
                st.success("KPI list updated!")
                st.rerun()
