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
from src.interfaces.streamlit_app.components import (
    kpi_explorer, plants, kpi_templates, 
    export, analysis, 
    settings, global_splits
)

st.set_page_config(
    page_title="KPI Target Management",
    page_icon="📊",
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
    except Exception as e:
        st.error(f"Error during database setup: {e}")
        st.session_state.db_setup_done = False

# --- Modern Navigation ---
# We provide unique url_path because all functions are named 'app'
pages = [
    st.Page(target_entry.app, title="Target Entry", icon="🎯", url_path="target_entry", default=True),
    st.Page(kpi_explorer.app, title="KPI Explorer", icon="📁", url_path="explorer"),
    st.Page(kpi_templates.app, title="Templates", icon="📋", url_path="templates"),
    st.Page(global_splits.app, title="Global Splits", icon="✂️", url_path="splits"),
    st.Page(plants.app, title="Plant Management", icon="🏭", url_path="plants"),
    st.Page(analysis.app, title="Analysis & Results", icon="📈", url_path="analysis"),
    st.Page(export.app, title="Data Center", icon="📦", url_path="export"),
    st.Page(settings.app, title="Settings", icon="⚙️", url_path="settings"),
]

# Create navigation
pg = st.navigation(pages)

# Run the selected page
if st.session_state.get('db_setup_done', False):
    pg.run()
else:
    st.warning("Database not configured correctly. Please check system logs.")
