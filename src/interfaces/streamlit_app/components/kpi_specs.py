import streamlit as st
import pandas as pd
from src.kpi_management import specs as kpi_specs_manager
from src.kpi_management import indicators as kpi_indicators_manager
from src.kpi_management import visibility as kpi_visibility
from src import data_retriever as db_retriever
from src import data_retriever
from src.kpi_management import specs as kpi_specs_manager
from src.kpi_management import indicators as kpi_indicators_manager
from src.kpi_management import visibility as kpi_visibility
from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS

def app():
    st.title("⚙️ KPI Specification Management")

    # Initialize session state
    if 'spec_to_edit' not in st.session_state:
        st.session_state.spec_to_edit = None

    # --- Display Existing KPI Specifications ---
    st.header("Existing KPI Specifications")
    all_kpis_data = db_retriever.get_all_kpis_detailed()
    if all_kpis_data:
        df = pd.DataFrame(all_kpis_data)
        st.dataframe(df[['id', 'group_name', 'subgroup_name', 'indicator_name', 'description', 'calculation_type', 'unit_of_measure', 'visible']])

        col1, col2 = st.columns(2)
        with col1:
            edit_id = st.number_input("Enter KPI Spec ID to Edit or Delete", min_value=1, format="%d")
        with col2:
            if st.button("Load for Editing"):
                st.session_state.spec_to_edit = db_retriever.get_kpi_detailed_by_id(edit_id)
                if not st.session_state.spec_to_edit:
                    st.error(f"KPI Specification with ID {edit_id} not found.")
            if st.button("Delete"):
                if edit_id:
                    try:
                        kpi_spec_details = db_retriever.get_kpi_detailed_by_id(edit_id)
                        if kpi_spec_details:
                            kpi_indicators_manager.delete_kpi_indicator(kpi_spec_details['actual_indicator_id'])
                            st.success(f"KPI Specification with ID {edit_id} deleted.")
                            st.session_state.spec_to_edit = None
                            st.experimental_rerun()
                        else:
                            st.error(f"KPI Specification with ID {edit_id} not found.")
                    except Exception as e:
                        st.error(f"Error deleting KPI: {e}")

    # --- Add/Edit Form ---
    st.header("Add or Edit KPI Specification")
    
    spec_data = st.session_state.spec_to_edit
    
    with st.form("spec_form"):
        st.write("Editing Spec ID: " + str(spec_data['id']) if spec_data else "Adding New Spec")

        groups = db_retriever.get_kpi_groups()
        group_names = [g['name'] for g in groups]
        selected_group_name = st.selectbox("Group", group_names, index=group_names.index(spec_data['group_name']) if spec_data else 0)

        selected_group_id = next((g['id'] for g in groups if g['name'] == selected_group_name), None)
        subgroups = db_retriever.get_kpi_subgroups_by_group_revised(selected_group_id) if selected_group_id else []
        subgroup_names = [sg['name'] for sg in subgroups]
        selected_subgroup_name = st.selectbox("Subgroup", subgroup_names, index=subgroup_names.index(spec_data['subgroup_name']) if spec_data and spec_data['subgroup_name'] in subgroup_names else 0)

        selected_subgroup_id = next((sg['id'] for sg in subgroups if sg['name'] == selected_subgroup_name), None)
        indicators = db_retriever.get_kpi_indicators_by_subgroup(selected_subgroup_id) if selected_subgroup_id else []
        indicator_names = [i['name'] for i in indicators]
        selected_indicator_name = st.selectbox("Indicator", indicator_names, index=indicator_names.index(spec_data['indicator_name']) if spec_data and spec_data['indicator_name'] in indicator_names else 0)
        
        selected_indicator_id = next((i['id'] for i in indicators if i['name'] == selected_indicator_name), None)

        description = st.text_area("Description", value=spec_data['description'] if spec_data else "")
        calculation_type = st.selectbox("Calculation Type", KPI_CALC_TYPE_OPTIONS, index=KPI_CALC_TYPE_OPTIONS.index(spec_data['calculation_type']) if spec_data else 0)
        unit_of_measure = st.text_input("Unit of Measure", value=spec_data['unit_of_measure'] if spec_data else "")
        visible = st.checkbox("Visible", value=spec_data['visible'] if spec_data else True)

        st.subheader("Per-Plant Visibility")
        all_plants = db_retriever.get_all_plants()
        plant_visibility_states = {}
        for plant in all_plants:
            default_visibility = True
            if spec_data:
                default_visibility = kpi_visibility.get_kpi_plant_visibility(spec_data['id'], plant['id'])
            plant_visibility_states[plant['id']] = st.checkbox(plant['name'], value=default_visibility, key=f"plant_vis_{plant['id']}")

        submitted = st.form_submit_button("Save")
        if submitted:
            if selected_indicator_id:
                try:
                    if spec_data: # Update
                        kpi_specs_manager.update_kpi_spec(spec_data['id'], selected_indicator_id, description, calculation_type, unit_of_measure, visible)
                        kpi_id_to_update = spec_data['id']
                    else: # Add
                        kpi_id_to_update = kpi_specs_manager.add_kpi_spec(selected_indicator_id, description, calculation_type, unit_of_measure, visible)
                    
                    for plant_id, is_enabled in plant_visibility_states.items():
                        kpi_visibility.set_kpi_plant_visibility(kpi_id_to_update, plant_id, is_enabled)
                    
                    st.success("KPI Specification saved.")
                    st.session_state.spec_to_edit = None
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error saving specification: {e}")
            else:
                st.warning("Please select a valid indicator.")
