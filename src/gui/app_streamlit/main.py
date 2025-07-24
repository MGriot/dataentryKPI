import streamlit as st
import sys
from pathlib import Path

# Ensure the 'src' directory is in the Python path
src_path = Path(__file__).resolve().parents[3] # Adjusted for pages subdirectory
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from db_core.setup import setup_databases
from app_config import load_settings

# Import page modules
from gui.app_streamlit.pages import target_entry
# ... other page imports will go here

st.set_page_config(
    page_title="Gestione Target KPI",
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
        st.success("Controllo e setup database completato.")
    except Exception as e:
        st.error(f"Errore durante il setup del database: {e}")
        st.session_state.db_setup_done = False

# --- Page Navigation ---
st.sidebar.title("Navigazione")

# Define pages (mirroring Tkinter tabs)
pages = {
    "🎯 Inserimento Target": target_entry,
    "🗂️ Gestione Gerarchia KPI": None, # Placeholder
    "📋 Gestione Template Indicatori": None, # Placeholder
    "⚙️ Gestione Specifiche KPI": None, # Placeholder
    "🔗 Gestione Link Master/Sub": None, # Placeholder
    "🏭 Gestione Stabilimenti": None, # Placeholder
    "📦 Esportazione Dati": None, # Placeholder
    "📈 Analisi Risultati": None, # Placeholder
    "⚙️ Impostazioni": None, # Placeholder
}

selected_page_name = st.sidebar.radio("Vai a:", list(pages.keys()))
selected_page_module = pages[selected_page_name]

# Dynamically import and run the selected page
if st.session_state.db_setup_done:
    if selected_page_module:
        selected_page_module.app()
    else:
        st.info("Pagina in costruzione.")
else:
    st.warning("Il database non è stato configurato correttamente. Alcune funzionalità potrebbero non essere disponibili.")
