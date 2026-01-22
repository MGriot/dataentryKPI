import streamlit as st
import pandas as pd
from src.kpi_management import templates as kpi_templates_manager
from src import data_retriever as db_retriever
from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS

def app():
    st.title("📋 Indicator Template Management")

    # Initialize session state
    if 'selected_template_id' not in st.session_state:
        st.session_state.selected_template_id = None

    col1, col2 = st.columns([1, 2])

    # --- Templates Column ---
    with col1:
        st.header("Templates")
        templates = db_retriever.get_kpi_indicator_templates()
        template_names = [t['name'] for t in templates]
        
        selected_template_name = st.selectbox("Select a Template:", ["None"] + template_names, key='template_selector')

        if selected_template_name and selected_template_name != "None":
            st.session_state.selected_template_id = next((t['id'] for t in templates if t['name'] == selected_template_name), None)
        else:
            st.session_state.selected_template_id = None

        # --- Add/Edit Template Form ---
        with st.expander("Add/Edit Template"):
            with st.form("template_form"):
                template_name_to_edit = st.text_input("Template Name:", value=selected_template_name if selected_template_name != "None" else "")
                template_desc_to_edit = st.text_area("Description:", value=next((t['description'] for t in templates if t['id'] == st.session_state.selected_template_id), "") if st.session_state.selected_template_id else "")
                
                submitted = st.form_submit_button("Save Template")
                if submitted:
                    if st.session_state.selected_template_id:
                        # Update
                        try:
                            kpi_templates_manager.update_kpi_indicator_template(st.session_state.selected_template_id, template_name_to_edit, template_desc_to_edit)
                            st.success(f"Template '{template_name_to_edit}' updated.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Error updating template: {e}")
                    else:
                        # Add
                        try:
                            kpi_templates_manager.add_kpi_indicator_template(template_name_to_edit, template_desc_to_edit)
                            st.success(f"Template '{template_name_to_edit}' added.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Error adding template: {e}")

        if st.session_state.selected_template_id:
            if st.button("Delete Selected Template"):
                try:
                    kpi_templates_manager.delete_kpi_indicator_template(st.session_state.selected_template_id)
                    st.success(f"Template '{selected_template_name}' deleted.")
                    st.session_state.selected_template_id = None
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error deleting template: {e}")

    # --- Definitions Column ---
    with col2:
        st.header("Definitions in Template")
        if st.session_state.selected_template_id:
            definitions = db_retriever.get_template_defined_indicators(st.session_state.selected_template_id)
            if definitions:
                df = pd.DataFrame(definitions)
                st.dataframe(df[['indicator_name_in_template', 'default_calculation_type', 'default_unit_of_measure', 'default_visible', 'default_description']])
            else:
                st.info("No definitions in this template.")

            # --- Add/Edit Definition Form ---
            with st.expander("Add/Edit Definition"):
                with st.form("definition_form"):
                    def_name = st.text_input("Indicator Name in Template:")
                    def_desc = st.text_area("Default Description:")
                    def_calc_type = st.selectbox("Default Calculation Type:", KPI_CALC_TYPE_OPTIONS)
                    def_unit = st.text_input("Default Unit of Measure:")
                    def_visible = st.checkbox("Default Visible", value=True)

                    submitted = st.form_submit_button("Save Definition")
                    if submitted and def_name:
                        try:
                            kpi_templates_manager.add_indicator_definition_to_template(
                                st.session_state.selected_template_id, def_name, def_calc_type, def_unit, def_visible, def_desc
                            )
                            st.success(f"Definition '{def_name}' saved.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Error saving definition: {e}")
        else:
            st.info("Select a template to see its definitions.")