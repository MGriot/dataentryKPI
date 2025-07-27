import streamlit as st
import json
import data_retriever
from stabilimenti_management import crud as stabilimenti_manager
from app_config import SETTINGS_FILE

def app():
    st.title("⚙️ Impostazioni")

    # Load current settings
    settings = st.session_state.settings

    # --- Display Names ---
    st.header("Nomi Visualizzati")
    target1_name = st.text_input("Target 1:", value=settings.get('display_names', {}).get('target1', 'Target 1'))
    target2_name = st.text_input("Target 2:", value=settings.get('display_names', {}).get('target2', 'Target 2'))

    # --- Database Path ---
    st.header("Percorso Database")
    db_path = st.text_input("Cartella Database:", value=settings.get('database_path', ''))
    st.info("Per modificare il percorso del database, aggiorna il campo e clicca su 'Salva Impostazioni'.")

    # --- Stabilimento Colors ---
    st.header("Colori Stabilimenti")
    stabilimenti = data_retriever.get_all_stabilimenti()
    if stabilimenti:
        for stabilimento in stabilimenti:
            stabilimento_id = stabilimento['id']
            stabilimento_name = stabilimento['name']
            current_color = stabilimento['color'] if 'color' in stabilimento else '#000000'

            new_color = st.color_picker(f"Seleziona colore per {stabilimento_name}", current_color, key=f"color_picker_{stabilimento_id}")
            if new_color != current_color:
                try:
                    stabilimenti_manager.update_stabilimento_color(stabilimento_id, new_color)
                    st.success(f"Colore per {stabilimento_name} aggiornato con successo!")
                    # Refresh stabilimenti data in session state if needed by other components
                    # This might require a more sophisticated state management or a full app rerun
                except Exception as e:
                    st.error(f"Errore nel salvare il colore per {stabilimento_name}: {e}")
    else:
        st.info("Nessuno stabilimento configurato. Aggiungi stabilimenti nella sezione 'Gestione Stabilimenti'.")

    # --- Save Button ---
    if st.button("Salva Impostazioni"):
        settings['display_names'] = {
            'target1': target1_name,
            'target2': target2_name
        }
        settings['database_path'] = db_path

        try:
            # Load existing settings to merge, then update
            current_settings = {}
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    current_settings = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass # File doesn't exist or is empty, start with empty dict

            # Update only the sections managed by this tab
            current_settings['display_names'] = settings['display_names']
            current_settings['database_path'] = settings['database_path']
            
            # Remove stabilimento_colors from settings.json if it exists (now handled directly in DB)
            if 'stabilimento_colors' in current_settings:
                del current_settings['stabilimento_colors']

            with open(SETTINGS_FILE, 'w') as f:
                json.dump(current_settings, f, indent=4)
            st.success("Impostazioni salvate con successo!")
            st.session_state.settings = settings # Update session state
            # Optionally, trigger a rerun to reflect changes immediately
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Impossibile salvare le impostazioni: {e}")
