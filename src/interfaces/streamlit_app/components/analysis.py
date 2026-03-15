import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name

def app():
    st.title("📈 Results Analysis Dashboard")

    # --- Mode Selection ---
    view_mode = st.radio("View Mode:", ["Single KPI Focus", "Global Comparison"], horizontal=True)

    # --- Global Filters ---
    st.sidebar.markdown("### 🔍 Filters")
    years_data = db_retriever.get_distinct_years()
    years = [str(y['year']) for y in years_data]
    selected_year = st.sidebar.selectbox("Year", ["All"] + years, index=1 if years else 0)

    plants = db_retriever.get_all_plants(visible_only=True)
    plant_names = [p['name'] for p in plants]
    selected_plant_name = st.sidebar.selectbox("Plant", ["All Plants"] + plant_names)
    
    periods = ["Day", "Week", "Month", "Quarter", "Year"]
    selected_period = st.sidebar.selectbox("Period Detail", periods, index=2)

    kpis_raw = db_retriever.get_all_kpis_detailed(only_visible=True)
    kpis = [dict(k) for k in kpis_raw]
    
    if view_mode == "Single KPI Focus":
        st.sidebar.markdown("### 🎯 KPI Selection")
        # Use a flat list for now, but formatted with hierarchy
        kpi_display_list = [f"{k['group_name']} > {k['subgroup_name']} > {k['indicator_name']}" for k in kpis]
        selected_kpi_display = st.sidebar.selectbox("Select KPI:", kpi_display_list)
        
        selected_kpi = next(k for i, k in enumerate(kpis) if kpi_display_list[i] == selected_kpi_display)
        
        # --- Single KPI Display ---
        st.subheader(f"📊 {selected_kpi_display}")
        
        plant_id = next((p['id'] for p in plants if p['name'] == selected_plant_name), None) if selected_plant_name != "All Plants" else None
        
        if not plant_id:
            st.warning("⚠️ Please select a specific plant to see the target details and chart.")
        else:
            # Fetch Targets 1 and 2
            t1 = db_retriever.get_periodic_targets_for_kpi(selected_year if selected_year != "All" else None, plant_id, selected_kpi['id'], selected_period, 1)
            t2 = db_retriever.get_periodic_targets_for_kpi(selected_year if selected_year != "All" else None, plant_id, selected_kpi['id'], selected_period, 2)
            
            if not t1 and not t2:
                st.info("No target data found for this selection.")
            else:
                # Merge into a single DF for plotting
                df1 = pd.DataFrame(t1) if t1 else pd.DataFrame(columns=['Period', 'Target'])
                df2 = pd.DataFrame(t2) if t2 else pd.DataFrame(columns=['Period', 'Target'])
                
                df1['Type'] = 'Target 1'
                df2['Type'] = 'Target 2'
                combined_df = pd.concat([df1, df2])
                
                # Table
                with st.expander("📄 View Data Table"):
                    pivot_df = combined_df.pivot(index='Period', columns='Type', values='Target').reset_index()
                    st.dataframe(pivot_df, use_container_width=True)
                
                # Plotly Chart
                fig = px.line(combined_df, x='Period', y='Target', color='Type', markers=True, 
                              title=f"Trend for {selected_kpi['indicator_name']} ({selected_year})")
                st.plotly_chart(fig, use_container_width=True)

    else:
        # --- Global Comparison ---
        st.subheader("🌎 Global KPI Overview")
        st.info("Showing comparison across multiple KPIs and Plants.")
        
        # Filter KPIs to show (maybe all top-level or something)
        # For now, let's show a summary for each KPI that has data
        
        year_val = int(selected_year) if selected_year != "All" else None
        plant_id = next((p['id'] for p in plants if p['name'] == selected_plant_name), None) if selected_plant_name != "All Plants" else None

        for k in kpis[:10]: # Limit for performance
            data = db_retriever.get_periodic_targets_for_kpi_all_plants(k['id'], selected_period, year_val)
            if not data: continue
            
            df = pd.DataFrame([dict(row) for row in data])
            if plant_id: df = df[df['plant_id'] == plant_id]
            if df.empty: continue
            
            with st.expander(f"📉 {k['indicator_name']} - {k['subgroup_name']}", expanded=True):
                # We need to distinguish targets and plants
                df['Label'] = df.apply(lambda x: f"{x['plant_name']} (T{x['target_number']})", axis=1)
                
                fig = px.line(df, x='period', y='target_value', color='Label', markers=True, height=300)
                fig.update_layout(margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)
