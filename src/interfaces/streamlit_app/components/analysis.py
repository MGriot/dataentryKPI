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
    current_year = str(datetime.datetime.now().year)
    
    # Requirement: Allow multi-year selection
    selected_years = st.sidebar.multiselect("Years", years, default=[current_year] if current_year in years else (years[:1] if years else []))

    plants = db_retriever.get_all_plants(visible_only=True)
    plant_names = [p['name'] for p in plants]
    
    # Requirement: In single KPI avoid "All Plants" selection (use first plant as default)
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
        # Use hierarchy_path
        kpi_display_list = [f"{k['hierarchy_path']} > {k['indicator_name']}" for k in kpis]
        selected_kpi_display = st.sidebar.selectbox("Select KPI:", kpi_display_list)
        
        selected_kpi = next(k for i, k in enumerate(kpis) if kpi_display_list[i] == selected_kpi_display)
        
        # --- Single KPI Display ---
        st.subheader(f"📊 {selected_kpi_display}")
        
        plant_id = next((p['id'] for p in plants if p['name'] == selected_plant_name), None)
        
        if not plant_id:
            st.warning("⚠️ Please select a specific plant.")
        elif not selected_years:
            st.warning("⚠️ Please select at least one year.")
        else:
            all_data = []
            for y in selected_years:
                # Fetch Targets 1 and 2 for each year
                t1 = db_retriever.get_periodic_targets_for_kpi(y, plant_id, selected_kpi['id'], selected_period, 1)
                t2 = db_retriever.get_periodic_targets_for_kpi(y, plant_id, selected_kpi['id'], selected_period, 2)
                
                if t1:
                    df1 = pd.DataFrame(t1)
                    df1['Type'] = f'Target 1 ({y})'
                    df1['Year'] = y
                    all_data.append(df1)
                if t2:
                    df2 = pd.DataFrame(t2)
                    df2['Type'] = f'Target 2 ({y})'
                    df2['Year'] = y
                    all_data.append(df2)
            
            if not all_data:
                st.info("No target data found for this selection.")
            else:
                combined_df = pd.concat(all_data)
                
                # Table
                with st.expander("📄 View Data Table"):
                    # Improve table for multi-year
                    pivot_df = combined_df.pivot(index='Period', columns='Type', values='Target').reset_index()
                    st.dataframe(pivot_df, use_container_width=True)
                
                # Plotly Chart with improved day scale
                fig = px.line(combined_df, x='Period', y='Target', color='Type', markers=True, 
                              title=f"Trend for {selected_kpi['indicator_name']} - Plant: {selected_plant_name}")
                
                # Requirement: Improve day scale visualization
                if selected_period == "Day":
                    fig.update_xaxes(
                        tickformat="%d %b",
                        dtick="M1", # Show tick every month start
                        ticklabelmode="period"
                    )
                
                fig.update_layout(hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

    else:
        # --- Global Comparison ---
        st.subheader("🌎 Global KPI Overview")
        
        if not selected_years:
            st.warning("⚠️ Please select at least one year.")
            return

        plant_id = next((p['id'] for p in plants if p['name'] == selected_plant_name), None) if selected_plant_name != "All Plants" else None

        # Display summaries for active KPIs
        for k in kpis[:15]: # Show top 15
            k_data = []
            for y in selected_years:
                data = db_retriever.get_periodic_targets_for_kpi_all_plants(k['id'], selected_period, int(y))
                if data:
                    df = pd.DataFrame([dict(row) for row in data])
                    if plant_id: df = df[df['plant_id'] == plant_id]
                    if not df.empty:
                        df['Year'] = y
                        k_data.append(df)
            
            if not k_data: continue
            
            with st.expander(f"📉 {k['indicator_name']} - {k['hierarchy_path']}", expanded=True):
                combined_k_df = pd.concat(k_data)
                combined_k_df['Label'] = combined_k_df.apply(lambda x: f"{x['plant_name']} (T{x['target_number']} - {x['Year']})", axis=1)
                
                fig = px.line(combined_k_df, x='period', y='target_value', color='Label', markers=True, height=350)
                
                if selected_period == "Day":
                    fig.update_xaxes(tickformat="%d %b")
                
                fig.update_layout(margin=dict(l=20, r=20, t=30, b=20), hovermode="closest")
                st.plotly_chart(fig, use_container_width=True)
