import streamlit as st
import pandas as pd
import traceback
from src import export_manager
from src.config.settings import CSV_EXPORT_BASE_PATH

def app():
    st.title("📊 Data Center")

    st.write(f"CSV files will be exported to: `{CSV_EXPORT_BASE_PATH}`")

    if st.button("Export All Data to CSVs"):
        try:
            export_manager.export_all_data_to_global_csvs()
            st.success("All data exported to CSV files successfully.")
        except Exception as e:
            st.error(f"An error occurred during CSV export: {e}")
            st.code(traceback.format_exc())

    st.divider()
    st.header("📦 Lean Export Mode")
    st.caption("Generate a high-portability CSV file with minimal columns for external analysis tools.")

    if st.button("Generate Lean Data CSV"):
        try:
            export_manager.export_lean_data_to_csv()
            st.success("Lean target data generated successfully.")
        except Exception as e:
            st.error(f"Lean export failed: {e}")

    # For lean export, we can also provide a direct download of the list
    from src import data_retriever
    lean_data = data_retriever.get_lean_targets()
    if lean_data:
        df_lean = pd.DataFrame(lean_data)
        st.download_button(
            label="Download Lean CSV",
            data=df_lean.to_csv(index=False).encode('utf-8'),
            file_name="lean_target_data.csv",
            mime="text/csv",
        )

    st.divider()