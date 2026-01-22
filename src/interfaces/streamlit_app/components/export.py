import streamlit as st
import traceback
from src import export_manager
from src.config.settings import CSV_EXPORT_BASE_PATH

def app():
    st.title("📦 Data Export")

    st.write(f"CSV files will be exported to: `{CSV_EXPORT_BASE_PATH}`")

    if st.button("Export All Data to CSVs"):
        try:
            export_manager.export_all_data_to_global_csvs()
            st.success("All data exported to CSV files successfully.")
        except Exception as e:
            st.error(f"An error occurred during CSV export: {e}")
            st.code(traceback.format_exc())

    st.download_button(
        label="Download All Data as ZIP",
        data=export_manager.package_all_csvs_as_zip(return_bytes_for_streamlit=True)[1],
        file_name="dataentryKPI_backup.zip",
        mime="application/zip",
    )