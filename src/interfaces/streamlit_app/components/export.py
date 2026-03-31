import streamlit as st
import pandas as pd
import traceback
from src import export_manager
from src.config.settings import CSV_EXPORT_BASE_PATH

def app():
    st.title("📦 Data Center & Exports")
    
    st.info(f"📁 Files are saved to: `{CSV_EXPORT_BASE_PATH}`")

    # --- 1. INDIVIDUAL TABLE EXPORT (Move to top for visibility) ---
    with st.container(border=True):
        st.header("📂 Individual Table Export")
        st.caption("Export a specific database table to a CSV file for targeted analysis.")

        table_options = [
            "Plants", 
            "KPI Hierarchy", 
            "KPI Definitions", 
            "Plant Visibility", 
            "Annual Targets", 
            "Periodic Targets"
        ]
        
        c1, c2 = st.columns([2, 1])
        selected_table = c1.selectbox("Select Table:", table_options, key="sel_single_tab")
        
        if c2.button("🚀 Export Table", use_container_width=True):
            try:
                msg = export_manager.export_single_table(selected_table)
                if "Success" in msg:
                    st.success(msg)
                else:
                    st.error(msg)
            except Exception as e:
                st.error(f"Export failed: {e}")

    st.markdown("---")

    # --- 2. GLOBAL EXPORT ---
    with st.container(border=True):
        st.header("🌐 Global Data Export")
        st.caption("Generate all flat CSV files at once. This will overwrite previous exports.")
        
        if st.button("Export All Data to CSVs", type="primary", use_container_width=True):
            try:
                export_manager.export_all_data_to_global_csvs()
                st.success("All data exported to CSV files successfully.")
            except Exception as e:
                st.error(f"An error occurred during CSV export: {e}")
                st.code(traceback.format_exc())

    st.markdown("---")

    # --- 3. LEAN EXPORT ---
    with st.container(border=True):
        st.header("📦 Lean Export Mode")
        st.caption("Generate a high-portability CSV file with minimal columns for BI tools (Power BI, Tableau).")

        col1, col2 = st.columns(2)
        
        if col1.button("Generate Lean CSV", use_container_width=True):
            try:
                export_manager.export_lean_data_to_csv()
                st.success("Lean target data generated successfully.")
            except Exception as e:
                st.error(f"Lean export failed: {e}")

        # Direct download
        from src import data_retriever
        lean_data = data_retriever.get_lean_targets()
        if lean_data:
            df_lean = pd.DataFrame(lean_data)
            col2.download_button(
                label="📥 Download Lean CSV",
                data=df_lean.to_csv(index=False).encode('utf-8'),
                file_name="lean_target_data.csv",
                mime="text/csv",
                use_container_width=True
            )
