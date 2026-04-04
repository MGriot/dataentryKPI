# src/interfaces/streamlit_app/components/global_splits.py
import streamlit as st
import json
import calendar
import datetime
import pandas as pd
import tempfile
import os
import plotly.express as px
import math
from src.kpi_management import splits as kpi_splits_manager
from src import data_retriever
from src.services import split_analyzer
from src.interfaces.common_ui.constants import (
    DISTRIBUTION_PROFILE_OPTIONS,
    PROFILE_EVEN,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL
)

def _get_universal_presets(profile):
    months = [m for m in calendar.month_name[1:] if m]
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    
    def calc(num_periods, labels):
        if profile == PROFILE_EVEN:
            factors = [1.0] * num_periods
        elif profile == PROFILE_ANNUAL_PROGRESSIVE:
            factors = [0.8 + (1.2 - 0.8) * (i / (num_periods-1)) for i in range(num_periods)]
        elif profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
            factors = [1.0 + 0.2 * math.sin(2 * math.pi * (i / (num_periods-1))) for i in range(num_periods)]
        else:
            factors = [1.0] * num_periods
        total_f = sum(factors)
        return {label: round((factors[i] / total_f) * 100.0, 4) for i, label in enumerate(labels)}

    return {
        "mode": "universal",
        "monthly": calc(12, months),
        "quarterly": calc(4, quarters)
    }

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
                
                with st.expander("🔍 Data Preview (First 100 rows)", expanded=True):
                    st.dataframe(df.head(100), use_container_width=True)
                
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
                            weights, coefficients, r_squared, plot_df, model_name = split_analyzer.analyze_seasonality_from_file(
                                tmp_path, target_cols, feature_cols, date_col, p_type
                            )
                            final_vals = {k: round(v * 100, 4) for k, v in weights.items()}
                            if p_type == "Month":
                                final_vals = {calendar.month_name[int(k)]: v for k, v in final_vals.items()}

                            st.session_state[f"suggested_{context_id}"] = final_vals
                            st.session_state[f"model_stats_{context_id}"] = {
                                "model_name": model_name,
                                "r2": r_squared, 
                                "coefs": coefficients,
                                "plot_data": plot_df.to_json()
                            }
                
                if f"suggested_{context_id}" in st.session_state:
                    stats = st.session_state[f"model_stats_{context_id}"]
                    st.success(f"**Winning Model:** `{stats['model_name']}` | **Fit Accuracy (R²):** `{stats['r2']:.4f}`")
                    
                    st.markdown("#### 📈 Model Fit Visualization")
                    plot_df = pd.read_json(stats['plot_data'])
                    
                    fig = px.line(plot_df, x='period_idx', y=['Actual_Target', 'Predicted_Fit'], markers=True, 
                                 labels={'value': 'Normalized Value', 'period_idx': 'Period Index'},
                                 title=f"Seasonality Fit ({stats['model_name']})")
                    
                    fig.add_scatter(
                        x=plot_df['period_idx'].tolist() + plot_df['period_idx'].tolist()[::-1],
                        y=plot_df['CI_Upper'].tolist() + plot_df['CI_Lower'].tolist()[::-1],
                        fill='toself',
                        fillcolor='rgba(255, 0, 0, 0.1)',
                        line=dict(color='rgba(255, 255, 255, 0)'),
                        hoverinfo="skip",
                        showlegend=True,
                        name='90% Confidence Interval'
                    )
                    
                    fig.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified")
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
                        # Wrap suggested into universal format
                        u_data = {"mode": "universal", "monthly": st.session_state[f"suggested_{context_id}"]}
                        st.session_state[f"val_override_{context_id}"] = json.dumps(u_data, indent=2)
                        st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(tmp_path): os.remove(tmp_path)

def app():
    st.title("✂️ Global Splits Management")
    st.markdown("Manage universal repartition templates that work across all levels.")

    # --- Sidebar: List of Splits ---
    st.sidebar.subheader("Existing Templates")
    all_splits = kpi_splits_manager.get_all_global_splits()
    
    def get_split_label(s):
        years = s.get('years', [])
        if not years and s.get('year'): years = [s['year']]
        years_str = ", ".join(map(str, years))
        return f"{years_str} - {s['name']}"

    split_labels_map = {get_split_label(s): s['id'] for s in all_splits}
    split_names = ["+ Create New Split"] + list(split_labels_map.keys())
    selected_split_label = st.sidebar.radio("Select Template:", split_names)

    # Prepare common data
    all_inds = sorted(data_retriever.get_all_kpi_indicators(), key=lambda x: x['name'])
    ind_options = {f"{i['name']} [ID:{i['id']}]": i['id'] for i in all_inds}
    
    year_options = list(range(2020, 2035))

    # --- Main Layout ---
    col_config, col_inds = st.columns([1.4, 1])

    if selected_split_label == "+ Create New Split":
        with col_config:
            st.subheader("🆕 Create New Global Split")
            _render_multivariate_section("new_split")
            
            st.markdown("---")
            st.subheader("📋 Template Details")
            
            if "new_split_profile" not in st.session_state:
                st.session_state.new_split_profile = PROFILE_EVEN
            
            with st.form("new_split_form"):
                name = st.text_input("Template Name")
                years = st.multiselect("Target Year(s)", options=year_options, default=[datetime.datetime.now().year])
                profile = st.selectbox("Universal Distribution Profile", DISTRIBUTION_PROFILE_OPTIONS, key="new_profile_sel")
                
                if profile != st.session_state.new_split_profile:
                    st.session_state.new_split_profile = profile
                    st.session_state["val_override_new_split"] = json.dumps(_get_universal_presets(profile), indent=2)

                initial_val = st.session_state.get("val_override_new_split", json.dumps(_get_universal_presets(st.session_state.new_split_profile), indent=2))
                values_json = st.text_area("Multi-level Repartition Weights (%)", value=initial_val, height=300)
                
                submitted = st.form_submit_button("Create Universal Template", type="primary")
                if submitted:
                    if not name: st.error("Name is required.")
                    elif not years: st.error("At least one year is required.")
                    else:
                        try:
                            v = json.loads(values_json)
                            new_id = kpi_splits_manager.add_global_split(name, years, "universal", v, profile, {})
                            
                            selected_labels = st.session_state.get("temp_inds_selection", [])
                            if selected_labels:
                                new_links = [{'indicator_id': ind_options[label]} for label in selected_labels]
                                kpi_splits_manager.update_global_split_indicators(new_id, new_links)
                            
                            st.success(f"Split '{name}' created!")
                            for k in ["val_override_new_split", "temp_inds_selection", "new_split_profile"]:
                                if k in st.session_state: del st.session_state[k]
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

        with col_inds:
            st.subheader("🎯 Affected KPIs")
            st.multiselect("Link KPIs to this Split", options=list(ind_options.keys()), key="temp_inds_selection")

    else:
        # Edit existing
        split_id = split_labels_map[selected_split_label]
        split = kpi_splits_manager.get_global_split(split_id)
        current_afflicted = kpi_splits_manager.get_indicators_for_global_split(split_id)
        
        years_raw = split.get('years', [])
        if not years_raw and split.get('year'): years_raw = [split['year']]
        
        st.info(f"📊 **Summary:** Universal Split applied to {len(current_afflicted)} KPIs.")

        if f"edit_split_profile_{split_id}" not in st.session_state:
            st.session_state[f"edit_split_profile_{split_id}"] = split['distribution_profile']

        with col_config:
            st.subheader(f"✏️ Edit: {split['name']}")
            _render_multivariate_section(f"edit_{split_id}")

            st.markdown("---")
            st.subheader("📋 Template Details")
            with st.form("edit_split_form"):
                new_name = st.text_input("Template Name", value=split['name'])
                new_years = st.multiselect("Target Year(s)", options=year_options, default=years_raw)
                new_profile = st.selectbox("Distribution Profile", DISTRIBUTION_PROFILE_OPTIONS, 
                                         index=DISTRIBUTION_PROFILE_OPTIONS.index(st.session_state[f"edit_split_profile_{split_id}"])
                                         if st.session_state[f"edit_split_profile_{split_id}"] in DISTRIBUTION_PROFILE_OPTIONS else 0)
                
                if new_profile != st.session_state[f"edit_split_profile_{split_id}"]:
                    st.session_state[f"edit_split_profile_{split_id}"] = new_profile
                    st.session_state[f"val_override_edit_{split_id}"] = json.dumps(_get_universal_presets(new_profile), indent=2)

                initial_val = st.session_state.get(f"val_override_edit_{split_id}", json.dumps(split['repartition_values'], indent=2))
                new_values_json = st.text_area("Multi-level Repartition Weights (%)", value=initial_val, height=300)
                
                update_btn = st.form_submit_button("Update Universal Split", type="primary")
                if update_btn:
                    try:
                        v = json.loads(new_values_json)
                        kpi_splits_manager.update_global_split(split_id, name=new_name, years=new_years, 
                                                             repartition_logic="universal", repartition_values=v, 
                                                             distribution_profile=new_profile)
                        st.success("Template updated!")
                        for k in [f"val_override_edit_{split_id}", f"edit_split_profile_{split_id}"]:
                            if k in st.session_state: del st.session_state[k]
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

            if st.button("🗑️ Delete Template", use_container_width=True):
                st.session_state[f"confirm_delete_{split_id}"] = True

            if st.session_state.get(f"confirm_delete_{split_id}"):
                st.warning("Delete permanently?")
                if st.button("Yes, Delete", type="primary"):
                    kpi_splits_manager.delete_global_split(split_id)
                    st.rerun()

        with col_inds:
            st.subheader("🎯 Affected KPIs")
            default_labels = [f"{i['name']} [ID:{i['id']}]" for i in all_inds if i['id'] in [a['indicator_id'] for a in current_afflicted]]
            selected_labels = st.multiselect("Link/Unlink KPIs", options=list(ind_options.keys()), default=default_labels, key=f"inds_edit_{split_id}")
            
            st.markdown("---")
            new_data = []
            for label in selected_labels:
                iid = ind_options[label]
                existing = next((i for i in current_afflicted if i['indicator_id'] == iid), None)
                with st.container(border=True):
                    c_name, c_ov = st.columns([1.5, 1])
                    c_name.write(label)
                    opts = ["(Default)"] + DISTRIBUTION_PROFILE_OPTIONS
                    current_ov = existing['override_distribution_profile'] if existing and existing['override_distribution_profile'] else "(Default)"
                    ov_profile = c_ov.selectbox("Override:", opts, index=opts.index(current_ov) if current_ov in opts else 0, key=f"ov_{split_id}_{iid}")
                    new_data.append({'indicator_id': iid, 'override_distribution_profile': None if ov_profile == "(Default)" else ov_profile})
            
            if st.button("Sync KPIs", type="primary", use_container_width=True):
                kpi_splits_manager.update_global_split_indicators(split_id, new_data)
                st.success("Updated!")
                st.rerun()
