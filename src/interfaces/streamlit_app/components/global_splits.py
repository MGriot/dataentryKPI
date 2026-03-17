import streamlit as st
import json
import calendar
import datetime
from src.kpi_management import splits as kpi_splits_manager
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
        return {m: 100.0 for m in calendar.month_name[1:]}
    elif logic == REPARTITION_LOGIC_QUARTER:
        return {f"Q{i+1}": 25.0 for i in range(4)}
    elif logic == REPARTITION_LOGIC_WEEK:
        try:
            last_day = datetime.date(year, 12, 28)
            num_weeks = last_day.isocalendar()[1]
            return {f"Week {i+1}": 100.0 for i in range(num_weeks)}
        except:
            return {f"Week {i+1}": 100.0 for i in range(52)}
    return {}

def _get_preset_params(profile, year):
    if profile == PROFILE_ANNUAL_PROGRESSIVE:
        return {"weight_initial": 1.6, "weight_final": 0.4}
    elif profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
        return {"weight_initial": 1.6, "weight_final": 0.4, "weekday_bias": 1.1}
    elif profile in (PROFILE_TRUE_ANNUAL_SINUSOIDAL, PROFILE_MONTHLY_SINUSOIDAL, PROFILE_QUARTERLY_SINUSOIDAL):
        return {"amplitude": 0.3, "phase_offset": 0.0}
    elif profile == PROFILE_QUARTERLY_PROGRESSIVE:
        return {"weight_initial": 1.5, "weight_final": 0.5}
    elif profile == "event_based_spikes_or_dips":
        return {"events": [{"date": f"{year}-01-01", "multiplier": 2.0}]}
    return {}

def app():
    st.title("✂️ Global Splits Management")
    st.markdown("Manage repartition templates that can be applied to multiple KPIs.")

    # --- Sidebar: List of Splits ---
    st.sidebar.subheader("Existing Templates")
    all_splits = kpi_splits_manager.get_all_global_splits()
    
    split_names = ["+ Create New Split"] + [f"{s['year']} - {s['name']}" for s in all_splits]
    selected_split_label = st.sidebar.radio("Select Template:", split_names)

    # --- Main Content: Editor ---
    if selected_split_label == "+ Create New Split":
        st.subheader("🆕 Create New Global Split")
        with st.form("new_split_form"):
            name = st.text_input("Template Name")
            year = st.number_input("Target Year", min_value=2000, max_value=2100, value=datetime.datetime.now().year)
            logic = st.selectbox("Repartition Logic", REPARTITION_LOGIC_OPTIONS)
            profile = st.selectbox("Intra-Period Distribution Profile", DISTRIBUTION_PROFILE_OPTIONS)
            
            st.info("Presets for Repartition Values and Profile Parameters will be applied upon saving if left as empty '{}'.")
            values_json = st.text_area("Repartition Values (JSON)", value="{}")
            params_json = st.text_area("Profile Parameters (JSON)", value="{}")
            
            submitted = st.form_submit_button("Create Template")
            if submitted:
                if not name:
                    st.error("Name is required.")
                else:
                    try:
                        v = json.loads(values_json) if values_json.strip() != "{}" else _get_preset_values(logic, year)
                        p = json.loads(params_json) if params_json.strip() != "{}" else _get_preset_params(profile, year)
                        kpi_splits_manager.add_global_split(name, year, logic, v, profile, p)
                        st.success(f"Split '{name}' created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        # Edit existing
        split_id = next(s['id'] for s in all_splits if f"{s['year']} - {s['name']}" == selected_split_label)
        split = kpi_splits_manager.get_global_split(split_id)
        
        st.subheader(f"✏️ Edit Split: {split['name']}")
        
        with st.form("edit_split_form"):
            new_name = st.text_input("Template Name", value=split['name'])
            new_year = st.number_input("Target Year", min_value=2000, max_value=2100, value=split['year'])
            new_logic = st.selectbox("Repartition Logic", REPARTITION_LOGIC_OPTIONS, index=REPARTITION_LOGIC_OPTIONS.index(split['repartition_logic']))
            new_profile = st.selectbox("Intra-Period Distribution Profile", DISTRIBUTION_PROFILE_OPTIONS, index=DISTRIBUTION_PROFILE_OPTIONS.index(split['distribution_profile']))
            
            new_values_json = st.text_area("Repartition Values (JSON)", value=json.dumps(split['repartition_values'], indent=2))
            new_params_json = st.text_area("Profile Parameters (JSON)", value=json.dumps(split['profile_params'], indent=2))
            
            # --- NEW: Multivariate Trend Analysis ---
            st.divider()
            st.subheader("🧪 Data-Driven Trend Analysis")
            st.markdown("Upload historical data (CSV/XLSX) to suggest seasonal weights based on trends.")
            
            uploaded_file = st.file_uploader("Upload reference data", type=["csv", "xlsx"], key=f"upload_{split_id}")
            if uploaded_file:
                import pandas as pd
                try:
                    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    st.dataframe(df.head(), use_container_width=True)
                    
                    cols = df.columns.tolist()
                    c1, c2 = st.columns(2)
                    with c1:
                        date_col = st.selectbox("Date Column", cols)
                    with c2:
                        val_col = st.selectbox("Indicator/Value Column", cols)
                    
                    if st.button("Analyze Trend & Suggest Weights", key=f"analyze_{split_id}"):
                        from src.target_management.repartition import get_seasonal_weights_from_df
                        suggestions = get_seasonal_weights_from_df(df, date_col, val_col, period=split['repartition_logic'])
                        if suggestions:
                            st.success("Trend analyzed!")
                            st.json(suggestions)
                            if st.button("Apply Suggestions Above", key=f"apply_{split_id}"):
                                # This is tricky inside a form, but we can store in session state
                                st.session_state[f"suggested_vals_{split_id}"] = suggestions
                                st.rerun()
                        else:
                            st.error("Could not extract trends. Ensure date column is valid.")
                except Exception as e:
                    st.error(f"Error processing file: {e}")

            if f"suggested_vals_{split_id}" in st.session_state:
                st.info("💡 Suggested values available. Re-paste the JSON above if you want to use them, or we can automate this in a future update.")

            col1, col2 = st.columns([1, 1])
            with col1:
                update_btn = st.form_submit_button("Update Template")
            with col2:
                # We can't have a normal button inside a form that isn't a submit button for different logic easily
                # but we can use a separate form or logic outside
                pass

            if update_btn:
                try:
                    v = json.loads(new_values_json)
                    p = json.loads(new_params_json)
                    kpi_splits_manager.update_global_split(split_id, name=new_name, year=new_year, repartition_logic=new_logic, repartition_values=v, distribution_profile=new_profile, profile_params=p)
                    st.success("Template updated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        if st.button("🗑️ Delete Template", type="secondary"):
            if st.checkbox("Confirm Deletion"):
                kpi_splits_manager.delete_global_split(split_id)
                st.success("Template deleted.")
                st.rerun()
