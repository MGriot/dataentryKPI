import streamlit as st
from src.kpi_management import groups as kpi_groups_manager
from src.kpi_management import subgroups as kpi_subgroups_manager
from src.kpi_management import indicators as kpi_indicators_manager
from src import data_retriever as db_retriever


def app():
    st.title("🗂️ KPI Hierarchy Management")

    # Initialize session state variables
    if 'selected_group_id' not in st.session_state:
        st.session_state.selected_group_id = None
    if 'selected_subgroup_id' not in st.session_state:
        st.session_state.selected_subgroup_id = None

    col1, col2, col3 = st.columns(3)

    # --- Groups Column ---
    with col1:
        st.header("Groups")
        groups = db_retriever.get_kpi_groups()
        group_names = [g['name'] for g in groups]
        
        selected_group_name = st.radio("Select a Group:", group_names, key='group_selector')
        
        if selected_group_name:
            st.session_state.selected_group_id = next((g['id'] for g in groups if g['name'] == selected_group_name), None)

        with st.form("new_group_form"):
            new_group_name = st.text_input("New Group Name:")
            submitted = st.form_submit_button("Add Group")
            if submitted and new_group_name:
                try:
                    kpi_groups_manager.add_kpi_group(new_group_name)
                    st.success(f"Group '{new_group_name}' added.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error adding group: {e}")

        edit_group_name = st.text_input("Edit Group Name:", key='edit_group_name')
        if st.button("Update Group"):
            if st.session_state.selected_group_id and edit_group_name:
                try:
                    kpi_groups_manager.update_kpi_group(st.session_state.selected_group_id, edit_group_name)
                    st.success(f"Group updated to '{edit_group_name}'.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error updating group: {e}")

        if st.button("Delete Group"):
            if st.session_state.selected_group_id:
                try:
                    # Confirmation dialog is tricky in Streamlit. Using a checkbox for now.
                    if st.checkbox(f"Confirm deletion of group '{selected_group_name}'"):
                        kpi_groups_manager.delete_kpi_group(st.session_state.selected_group_id)
                        st.success(f"Group '{selected_group_name}' deleted.")
                        st.session_state.selected_group_id = None
                        st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error deleting group: {e}")

    # --- Subgroups Column ---
    with col2:
        st.header("Subgroups")
        if st.session_state.selected_group_id:
            subgroups = db_retriever.get_kpi_subgroups_by_group_revised(st.session_state.selected_group_id)
            subgroup_names = [sg['name'] for sg in subgroups]
            
            selected_subgroup_name = st.radio("Select a Subgroup:", subgroup_names, key='subgroup_selector')

            if selected_subgroup_name:
                st.session_state.selected_subgroup_id = next((sg['id'] for sg in subgroups if sg['name'] == selected_subgroup_name), None)
            
            with st.form("new_subgroup_form"):
                new_subgroup_name = st.text_input("New Subgroup Name:")
                templates = db_retriever.get_kpi_indicator_templates()
                template_names = [t['name'] for t in templates]
                selected_template_name = st.selectbox("Link to Template:", ["None"] + template_names)
                
                submitted = st.form_submit_button("Add Subgroup")
                if submitted and new_subgroup_name:
                    template_id = next((t['id'] for t in templates if t['name'] == selected_template_name), None)
                    try:
                        kpi_subgroups_manager.add_kpi_subgroup(new_subgroup_name, st.session_state.selected_group_id, template_id)
                        st.success(f"Subgroup '{new_subgroup_name}' added.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Error adding subgroup: {e}")

    # --- Indicators Column ---
    with col3:
        st.header("Indicators")
        if st.session_state.selected_subgroup_id:
            indicators = db_retriever.get_kpi_indicators_by_subgroup(st.session_state.selected_subgroup_id)
            indicator_names = [i['name'] for i in indicators]
            
            selected_indicator_name = st.radio("Select an Indicator:", indicator_names, key='indicator_selector')

            with st.form("new_indicator_form"):
                new_indicator_name = st.text_input("New Indicator Name:")
                submitted = st.form_submit_button("Add Indicator")
                if submitted and new_indicator_name:
                    try:
                        kpi_indicators_manager.add_kpi_indicator(new_indicator_name, st.session_state.selected_subgroup_id)
                        st.success(f"Indicator '{new_indicator_name}' added.")
                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Error adding indicator: {e}")