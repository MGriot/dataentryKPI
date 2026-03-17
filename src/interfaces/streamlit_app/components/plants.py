import streamlit as st
from src import data_retriever
from src.plants_management import crud as plants_manager

def app():
    st.title("🏭 Plant Management Explorer")

    # --- Sidebar for Selection ---
    plants = data_retriever.get_all_plants()
    plant_names = [p['name'] for p in plants]
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Plants")
        selected_plant_name = st.radio("Select a Plant:", ["+ Add New Plant"] + plant_names)
        
    with col2:
        if selected_plant_name == "+ Add New Plant":
            st.subheader("🆕 Add New Plant")
            with st.form("add_plant_form"):
                name = st.text_input("Plant Name:")
                desc = st.text_area("Description:")
                visible = st.checkbox("Visible for Target Entry", value=True)
                color = st.color_picker("Brand Color:", "#000000")
                
                if st.form_submit_button("Create Plant"):
                    if name:
                        try:
                            plants_manager.add_plant(name, desc, visible, color)
                            st.success(f"Plant '{name}' added.")
                            st.experimental_rerun()
                        except Exception as e: st.error(str(e))
                    else: st.warning("Name is required.")
        else:
            plant = next(p for p in plants if p['name'] == selected_plant_name)
            st.subheader(f"🏭 {plant['name']}")
            
            # Display current info
            st.markdown(f"**Description:** {plant['description'] or 'N/A'}")
            st.markdown(f"**Visibility:** {'✅ Visible' if plant['visible'] else '❌ Hidden'}")
            st.markdown(f"**Color:** `{plant['color']}`")
            st.color_picker("Preview Color", value=plant['color'], disabled=True)
            
            with st.expander("✏️ Edit Plant Details"):
                with st.form("edit_plant_form"):
                    edit_name = st.text_input("Name:", value=plant['name'])
                    edit_desc = st.text_area("Description:", value=plant['description'] or "")
                    edit_visible = st.checkbox("Visible", value=bool(plant['visible']))
                    edit_color = st.color_picker("Color:", value=plant['color'])
                    
                    if st.form_submit_button("Save Changes"):
                        try:
                            plants_manager.update_plant(plant['id'], edit_name, edit_desc, edit_visible, edit_color)
                            st.success("Plant updated.")
                            st.experimental_rerun()
                        except Exception as e: st.error(str(e))
            
            if st.button("🗑️ Delete Plant"):
                if st.checkbox(f"Confirm deletion of {plant['name']}"):
                    try:
                        plants_manager.delete_plant(plant['id'])
                        st.success("Plant deleted.")
                        st.experimental_rerun()
                    except Exception as e: st.error(str(e))
