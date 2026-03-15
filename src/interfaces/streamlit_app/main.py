import streamlit as st
import sys
from pathlib import Path

# Ensure the 'src' directory is in the Python path
src_path = Path(__file__).resolve().parents[3]
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from src.data_access.setup import setup_databases
from src.config.settings import load_settings

# Import page modules
from src.interfaces.streamlit_app.pages import target_entry
from src.interfaces.streamlit_app.components import kpi_explorer, plants, kpi_templates, master_sub_link, export, analysis, settings

st.set_page_config(
    page_title="KPI Target Management",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state for settings and database setup
if 'settings' not in st.session_state:
    st.session_state.settings = load_settings()

if 'db_setup_done' not in st.session_state:
    try:
        setup_databases()
        st.session_state.db_setup_done = True
        st.success("Database check and setup completed.")
    except Exception as e:
        st.error(f"Error during database setup: {e}")
        st.session_state.db_setup_done = False

# --- Page Navigation ---
st.sidebar.title("Navigation")

# Define pages (mirroring Tkinter tabs)
pages = {
    "🎯 Target Entry": target_entry,
    "📁 KPI Explorer": kpi_explorer,
    "📋 Indicator Template Management": kpi_templates,
    "🔗 Master/Sub Link Management": master_sub_link,
    "🏭 Plant Management": plants,
    "📦 Data Export": export,
    "📈 Results Analysis": analysis,
    "⚙️ Settings": settings,
}


selected_page_name = st.sidebar.radio("Go to:", list(pages.keys()))
selected_page_module = pages[selected_page_name]

# Dynamically import and run the selected page
if st.session_state.db_setup_done:
    if selected_page_module:
        selected_page_module.app()
    else:
        st.info("Page under construction.")
else:
    st.warning("Database not configured correctly. Some features may not be available.")
