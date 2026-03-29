import streamlit as st
import json
import os
from src import data_retriever
from src.plants_management import crud as plants_manager
from src.config.settings import SETTINGS_FILE
from src import import_manager

def app():
    st.title("⚙️ Settings & Maintenance")

    # Load current settings
    settings = st.session_state.settings

    tabs = st.tabs(["🎯 Target Configuration", "📂 Database & Maintenance", "🎨 Plant Colors"])

    with tabs[0]:
        st.header("Target Configuration")
        st.caption("Define the targets available in the system. Changes will apply to Target Entry and Analysis.")
        
        # We'll use session state to track temporary changes before saving
        if "temp_targets" not in st.session_state:
            st.session_state.temp_targets = settings.get('targets', [{"id": 1, "name": "Target"}])

        targets = st.session_state.temp_targets
        
        updated_targets = []
        for i, t in enumerate(targets):
            col_id, col_name, col_del = st.columns([0.2, 0.6, 0.2])
            with col_id:
                new_id = st.number_input(f"ID", value=int(t['id']), min_value=1, key=f"t_id_{i}")
            with col_name:
                new_name = st.text_input(f"Name", value=t['name'], key=f"t_name_{i}")
            with col_del:
                st.write("") # Padding
                if st.button("🗑️", key=f"t_del_{i}"):
                    if len(targets) > 1:
                        st.session_state.temp_targets.pop(i)
                        st.rerun()
                    else:
                        st.warning("At least one target is required.")
            updated_targets.append({"id": new_id, "name": new_name})
        
        st.session_state.temp_targets = updated_targets

        if st.button("➕ Add Target"):
            next_id = max([t['id'] for t in updated_targets]) + 1 if updated_targets else 1
            st.session_state.temp_targets.append({"id": next_id, "name": f"Target {next_id}"})
            st.rerun()

    with tabs[1]:
        st.header("Database Path")
        db_path = st.text_input("Database Folder:", value=settings.get('database_path', ''))
        st.info("Current Path: " + str(settings.get('database_path', 'Not Set')))

        st.divider()
        st.header("Data Recovery")
        st.caption("Restore the system state from a previously generated ZIP backup.")
        
        uploaded_file = st.file_uploader("Upload Backup ZIP", type="zip")
        if uploaded_file is not None:
            if st.button("Restore Database from ZIP", type="primary"):
                # Save temp file
                temp_zip_path = "temp_restore.zip"
                with open(temp_zip_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                try:
                    with st.spinner("Restoring data..."):
                        # We need to know if we want to append or overwrite.
                        # Usually maintenance restore is Overwrite.
                        msg = import_manager.restore_from_backup(temp_zip_path, mode='overwrite')
                        st.success(msg)
                except Exception as e:
                    st.error(f"Restore failed: {e}")
                finally:
                    if os.path.exists(temp_zip_path):
                        os.remove(temp_zip_path)

    with tabs[2]:
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
                    except Exception as e:
                        st.error(f"Error saving color for {plant_name}: {e}")
        else:
            st.info("No plants configured. Add plants in the 'Plant Management' section.")

    # --- Global Save Button ---
    st.divider()
    if st.button("💾 Save All Settings", type="primary", use_container_width=True):
        # 1. Update session state settings
        settings['targets'] = st.session_state.temp_targets
        settings['database_path'] = db_path

        try:
            # 2. Persist to file
            current_settings = {}
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    current_settings = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

            current_settings['targets'] = settings['targets']
            current_settings['database_path'] = settings['database_path']
            
            # Remove legacy display_names if they exist
            if 'display_names' in current_settings:
                del current_settings['display_names']

            with open(SETTINGS_FILE, 'w') as f:
                json.dump(current_settings, f, indent=4)
            
            st.session_state.settings = settings
            st.success("Settings saved successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Could not save settings: {e}")
