# src/interfaces/streamlit_app/components/analysis.py
import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name

def app():
    st.title("📈 Analysis & Results")

    # --- Mode Selection ---
    view_mode = st.radio("View Mode:", ["Single KPI Focus", "Global Comparison"], horizontal=True)

    # --- Global Filters ---
    st.sidebar.markdown("### 🔍 Filters")
    years_data = db_retriever.get_distinct_years()
    years = [str(y['year']) for y in years_data]
    current_year = str(datetime.datetime.now().year)
    
    selected_years = st.sidebar.multiselect("Years", years, default=[current_year] if current_year in years else (years[:1] if years else []))

    plants = db_retriever.get_all_plants(visible_only=True)
    plant_names = [p['name'] for p in plants]
    
    if view_mode == "Single KPI Focus":
        selected_plant_name = st.sidebar.selectbox("Plant", plant_names)
    else:
        selected_plant_name = st.sidebar.selectbox("Plant", ["All Plants"] + plant_names)
    
    periods = ["Day", "Week", "Month", "Quarter", "Year"]
    selected_period = st.sidebar.selectbox("Period Detail", periods, index=2)

    kpis_raw = db_retriever.get_all_kpis_detailed(only_visible=True)
    kpis = [dict(k) for k in kpis_raw]
    
    if view_mode == "Single KPI Focus":
        st.sidebar.markdown("### 🎯 KPI Selection")
        kpi_display_list = [f"{k['hierarchy_path']} > {k['indicator_name']}" for k in kpis]
        selected_kpi_display = st.sidebar.selectbox("Select KPI:", kpi_display_list)
        
        selected_kpi = next(k for i, k in enumerate(kpis) if kpi_display_list[i] == selected_kpi_display)
        
        st.subheader(f"📊 {selected_kpi_display}")
        
        plant_id = next((p['id'] for p in plants if p['name'] == selected_plant_name), None)
        
        if not plant_id:
            st.warning("⚠️ Please select a specific plant.")
        elif not selected_years:
            st.warning("⚠️ Please select at least one year.")
        else:
            all_data = []
            target1_name, target2_name = st.session_state.settings.get('display_names', {}).get('target1', 'Target 1'), st.session_state.settings.get('display_names', {}).get('target2', 'Target 2')
            
            for y in selected_years:
                # Find available target numbers dynamically
                t_nums = db_retriever.get_available_target_numbers_for_kpi(int(y), plant_id, selected_kpi['id'])
                if not t_nums: t_nums = [1, 2] # fallback
                
                for tn in t_nums:
                    res = db_retriever.get_periodic_targets_for_kpi(int(y), plant_id, selected_kpi['id'], selected_period, tn)
                    if res:
                        df = pd.DataFrame([dict(row) for row in res])
                        if not df.empty and 'period' in df.columns:
                            label = f"Target {tn}"
                            if tn == 1: label = target1_name
                            elif tn == 2: label = target2_name
                            
                            df['Series'] = label # No year in legend for continuous line
                            df['Year'] = int(y)
                            all_data.append(df)
            
            if not all_data:
                st.info("No target data found for this selection.")
            else:
                combined_df = pd.concat(all_data)
                
                # --- Convert Period to Real Datetime for Correct Sorting ---
                def to_actual_date(row):
                    y = int(row['Year'])
                    p = str(row['period'])
                    try:
                        if selected_period == "Day":
                            return pd.to_datetime(p)
                        elif selected_period == "Month":
                            return pd.to_datetime(f"{y} {p} 01")
                        elif selected_period == "Week":
                            # p is usually 'YYYY-Www'
                            return pd.to_datetime(p + '-1', format='%G-W%V-%u')
                        elif selected_period == "Quarter":
                            q_num = int(p[1])
                            month = (q_num - 1) * 3 + 1
                            return pd.to_datetime(f"{y}-{month:02d}-01")
                        elif selected_period == "Year":
                            return pd.to_datetime(f"{y}-01-01")
                    except:
                        return p # Fallback to string if parsing fails
                    return p

                combined_df['DateAxis'] = combined_df.apply(to_actual_date, axis=1)
                combined_df = combined_df.sort_values('DateAxis')

                with st.expander("📄 View Data Table"):
                    pivot_df = combined_df.pivot(index='DateAxis', columns='Series', values='Target').reset_index()
                    st.dataframe(pivot_df, use_container_width=True)
                
                # Use line_group to ensure continuity if color is not enough, 
                # though sorting by DateAxis should already connect them.
                fig = px.line(combined_df, x='DateAxis', y='Target', color='Series', markers=True, 
                              line_group='Series',
                              title=f"Timeline Trend: {selected_kpi['indicator_name']} - Plant: {selected_plant_name}")
                
                fig.update_xaxes(title="Timeline")
                fig.update_layout(hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True, key=f"chart_single_{selected_kpi['id']}")

                # --- Metrics Overview ---
                st.markdown("---")
                st.subheader("📊 Performance Metrics")
                
                import numpy as np
                cols = st.columns(2)
                
                with cols[0]:
                    st.markdown("**📅 Year-over-Year (YoY)**")
                    if len(selected_years) >= 2:
                        sorted_years = sorted([int(y) for y in selected_years])
                        cur_y = sorted_years[-1]
                        prev_y = sorted_years[-2]
                        
                        for series in combined_df['Series'].unique():
                            sdf = combined_df[combined_df['Series'] == series]
                            cur_val = sdf[sdf['Year'] == cur_y]['Target'].sum()
                            prev_val = sdf[sdf['Year'] == prev_y]['Target'].sum()
                            
                            if prev_val != 0:
                                delta = ((cur_val - prev_val) / abs(prev_val)) * 100
                                st.metric(f"{series} ({prev_y} vs {cur_y})", f"{cur_val:,.0f}", f"{delta:+.1f}%")
                            else:
                                st.write(f"{series}: Insufficient history for YoY")
                    else:
                        st.info("Select at least 2 years for YoY comparison.")

                with cols[1]:
                    st.markdown("**📈 Overall Trend Analysis**")
                    for series in combined_df['Series'].unique():
                        sdf = combined_df[combined_df['Series'] == series].sort_values('DateAxis')
                        y_vals = sdf['Target'].values
                        if len(y_vals) > 2:
                            x_vals = np.arange(len(y_vals))
                            slope, _ = np.polyfit(x_vals, y_vals, 1)
                            mean_v = np.mean(y_vals)
                            rel_slope = (slope / mean_v * 100) if abs(mean_v) > 1e-9 else 0
                            
                            trend_icon = "⤴️" if rel_slope > 0.5 else "⤵️" if rel_slope < -0.5 else "➡️"
                            trend_text = "Upward" if rel_slope > 0.5 else "Downward" if rel_slope < -0.5 else "Stable"
                            color = "green" if rel_slope > 0.5 else "red" if rel_slope < -0.5 else "gray"
                            
                            st.markdown(f"{trend_icon} **{series}:** {trend_text} (`{rel_slope:+.2f}%` per period)")
                        else:
                            st.write(f"{series}: Not enough data for trend.")

    else:
        st.subheader("🌎 Global KPI Overview")
        
        if not selected_years:
            st.warning("⚠️ Please select at least one year.")
            return

        plant_id = next((p['id'] for p in plants if p['name'] == selected_plant_name), None) if selected_plant_name != "All Plants" else None

        for k in kpis[:15]:
            k_data = []
            for y in selected_years:
                data = db_retriever.get_periodic_targets_for_kpi_all_plants(k['id'], selected_period, int(y))
                if data:
                    df = pd.DataFrame([dict(row) for row in data])
                    if plant_id: df = df[df['plant_id'] == plant_id]
                    if not df.empty:
                        df['Year'] = int(y)
                        k_data.append(df)
            
            if not k_data: continue
            
            with st.expander(f"📉 {k['indicator_name']} - {k['hierarchy_path']}", expanded=True):
                combined_k_df = pd.concat(k_data)
                
                # --- Convert Period to Real Datetime ---
                def to_actual_date_global(row):
                    y = int(row['Year'])
                    p = str(row['period'])
                    try:
                        if selected_period == "Day": return pd.to_datetime(p)
                        elif selected_period == "Month": return pd.to_datetime(f"{y} {p} 01")
                        elif selected_period == "Week": return pd.to_datetime(p + '-1', format='%G-W%V-%u')
                        elif selected_period == "Quarter":
                            q_num = int(p[1]); month = (q_num - 1) * 3 + 1
                            return pd.to_datetime(f"{y}-{month:02d}-01")
                        elif selected_period == "Year": return pd.to_datetime(f"{y}-01-01")
                    except: return p
                    return p

                combined_k_df['DateAxis'] = combined_k_df.apply(to_actual_date_global, axis=1)
                combined_k_df = combined_k_df.sort_values(['DateAxis', 'plant_name'])

                # Legend label: Plant + Target No
                combined_k_df['Label'] = combined_k_df.apply(lambda x: f"{x['plant_name']} (T{x['target_number']})", axis=1)
                
                fig = px.line(combined_k_df, x='DateAxis', y='target_value', color='Label', markers=True, height=350,
                              line_group='Label',
                              title=f"{k['indicator_name']} - Sequential Timeline")
                
                fig.update_xaxes(title="Timeline")
                fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), hovermode="closest")
                st.plotly_chart(fig, use_container_width=True, key=f"global_chart_{k['id']}")
