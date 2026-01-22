import streamlit as st
import json
from src import data_retriever
from src.plants_management import crud as plants_manager
from src.config.settings import SETTINGS_FILE

def app():
    st.title("⚙️ Settings")

    # Load current settings
    settings = st.session_state.settings

    # --- Display Names ---
    st.header("Display Names")
    target1_name = st.text_input("Target 1:", value=settings.get('display_names', {}).get('target1', 'Target 1'))
    target2_name = st.text_input("Target 2:", value=settings.get('display_names', {}).get('target2', 'Target 2'))

    # --- Database Path ---
    st.header("Database Path")
    db_path = st.text_input("Database Folder:", value=settings.get('database_path', ''))
    st.info("To change the database path, update the field and click 'Save Settings'.")

    # --- Plant Colors ---
    st.header("Plant Colors")
    plants = data_retriever.get_all_plants()
    if plants:
        for plant in plants:
            plant_id = plant['id']
            plant_name = plant['name']
            current_color = plant['color'] if 'color' in plant else '#000000'

            new_color = st.color_picker(f"Select color for {plant_name}", current_color, key=f"color_picker_{plant_id}")
            if new_color != current_color:
                try:
                    plants_manager.update_plant_color(plant_id, new_color)
                    st.success(f"Color for {plant_name} updated successfully!")
                    # Refresh plants data in session state if needed by other components
                    # This might require a more sophisticated state management or a full app rerun
                except Exception as e:
                    st.error(f"Error saving color for {plant_name}: {e}")
    else:
        st.info("No plants configured. Add plants in the 'Plant Management' section.")

    # --- Save Button ---
    if st.button("Save Settings"):
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
            
            # Remove plant_colors from settings.json if it exists (now handled directly in DB)
            if 'plant_colors' in current_settings:
                del current_settings['plant_colors']

            with open(SETTINGS_FILE, 'w') as f:
                json.dump(current_settings, f, indent=4)
            st.success("Settings saved successfully!")
            st.session_state.settings = settings # Update session state
            # Optionally, trigger a rerun to reflect changes immediately
            st.experimental_rerun()
        except Exception as e:
            st.error(f"Could not save settings: {e}")