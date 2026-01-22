import streamlit as st
import pandas as pd
import datetime
from src import data_retriever as db_retriever
from src.gui.shared.helpers import get_kpi_display_name

def app():
    st.title("📈 Results Analysis")

    # --- Filters ---
    col1, col2, col3 = st.columns(3)
    with col1:
        years = [y['year'] for y in db_retriever.get_distinct_years()]
        selected_year = st.selectbox("Year", ["All"] + years)
    with col2:
        plants = db_retriever.get_all_plants(visible_only=True)
        plant_names = [p['name'] for p in plants]
        selected_plant_name = st.selectbox("Plant", ["All"] + plant_names)
    with col3:
        periods = ["Day", "Week", "Month", "Quarter", "Year"]
        selected_period = st.selectbox("Period", periods, index=2)

    kpis = db_retriever.get_all_kpis_detailed(only_visible=True)
    kpi_names = [get_kpi_display_name(kpi) for kpi in kpis]
    selected_kpi_name = st.selectbox("KPI", ["All"] + kpi_names)

    # --- Data Display ---
    if selected_kpi_name != "All":
        selected_kpi = next((kpi for kpi in kpis if get_kpi_display_name(kpi) == selected_kpi_name), None)
        if selected_kpi:
            kpi_id = selected_kpi['id']
            plant_id = next((p['id'] for p in plants if p['name'] == selected_plant_name), None) if selected_plant_name != "All" else None
            
            if plant_id:
                data = db_retriever.get_periodic_targets_for_kpi(selected_year if selected_year != "All" else None, plant_id, kpi_id, selected_period, 1)
            else:
                data = db_retriever.get_periodic_targets_for_kpi_all_plants(kpi_id, selected_period, selected_year if selected_year != "All" else None)

            if data:
                df = pd.DataFrame(data)
                st.dataframe(df)
                
                # Chart
                if selected_period != "Year":
                    st.line_chart(df.rename(columns={'Period': 'index'}).set_index('index'))
            else:
                st.info("No data available for the selected filters.")