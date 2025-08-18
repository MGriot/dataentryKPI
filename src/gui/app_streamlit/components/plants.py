import streamlit as st
import data_retriever
from src.plants_management import crud as plants_manager

def app():
    st.title("🏭 Plant Management")

    # --- Add New Plant ---
    st.header("Add New Plant")
    with st.form(key='add_plant_form'):
        new_name = st.text_input("Plant Name:")
        new_description = st.text_area("Description:")
        new_visible = st.checkbox("Visible for Target Entry", value=True)
        new_color = st.color_picker("Color:", '#000000')
        add_button = st.form_submit_button("Add Plant")

        if add_button:
            if new_name:
                try:
                    plants_manager.add_plant(new_name, new_description, new_visible, new_color)
                    st.success(f"Plant '{new_name}' added successfully!")
                    st.experimental_rerun() # Rerun to refresh the list
                except Exception as e:
                    st.error(f"Error adding plant: {e}")
            else:
                st.warning("The plant name cannot be empty.")

    # --- Display Existing Plants ---
    st.header("Existing Plants")
    plants = data_retriever.get_all_plants()

    if plants:
        # Create a list of dictionaries for easier display
        display_data = []
        for s in plants:
            display_data.append({
                "ID": s['id'],
                "Name": s['name'],
                "Description": s['description'],
                "Visible": "Yes" if s['visible'] else "No",
                "Color": s['color'] # Display color hex
            })
        
        st.dataframe(display_data, use_container_width=True)

        # --- Edit/Delete Plant ---
        st.subheader("Edit or Delete Plant")
        
        # Create a mapping from name to ID for selection
        plant_names = {s['name']: s['id'] for s in plants}
        selected_plant_name = st.selectbox(
            "Select Plant:", 
            options=list(plant_names.keys()),
            key='edit_delete_select'
        )

        if selected_plant_name:
            selected_plant_id = plant_names[selected_plant_name]
            # Retrieve full data for the selected plant
            selected_plant = next((s for s in plants if s['id'] == selected_plant_id), None)

            if selected_plant:
                with st.form(key='edit_plant_form'):
                    edit_name = st.text_input("Name:", value=selected_plant['name'], key='edit_name')
                    edit_description = st.text_area("Description:", value=selected_plant['description'], key='edit_description')
                    edit_visible = st.checkbox("Visible for Target Entry", value=selected_plant['visible'], key='edit_visible')
                    edit_color = st.color_picker("Color:", value=selected_plant['color'], key='edit_color')

                    col1, col2 = st.columns(2)
                    with col1:
                        update_button = st.form_submit_button("Update Plant")
                    with col2:
                        delete_button = st.form_submit_button("Delete Plant")

                    if update_button:
                        if edit_name:
                            try:
                                plants_manager.update_plant(
                                    selected_plant_id, edit_name, edit_description, edit_visible, edit_color
                                )
                                st.success(f"Plant '{edit_name}' updated successfully!")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Error updating plant: {e}")
                        else:
                            st.warning("The plant name cannot be empty.")

                    if delete_button:
                        if st.checkbox(f"Confirm deletion of '{selected_plant_name}'", key='confirm_delete'):
                            try:
                                plants_manager.delete_plant(selected_plant_id)
                                st.success(f"Plant '{selected_plant_name}' deleted successfully!")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Error deleting plant: {e}")
            else:
                st.warning("Select a valid plant to edit or delete.")
    else:
        st.info("No plants configured. Add a new plant above.")
