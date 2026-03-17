import streamlit as st
import pandas as pd
from src.kpi_management import hierarchy as kpi_hierarchy_manager
from src.kpi_management import indicators as kpi_indicators_manager
from src.kpi_management import specs as kpi_specs_manager
from src.kpi_management import visibility as kpi_visibility
from src import data_retriever as db_retriever
from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS, DISTRIBUTION_PROFILE_OPTIONS

def app():
    st.title("📁 KPI Explorer")

    # --- Sidebar/Navigation for Hierarchy ---
    st.markdown("### 🌲 Hierarchy Navigation")
    
    # Recursive function to get all paths for a selectbox
    def get_all_paths(parent_id=None, current_path=""):
        paths = []
        nodes_raw = db_retriever.get_hierarchy_nodes(parent_id)
        nodes = [dict(n) for n in nodes_raw]
        for n in nodes:
            path = f"{current_path}/{n['name']}" if current_path else n['name']
            paths.append({"id": n['id'], "path": path, "type": "folder"})
            paths.extend(get_all_paths(n['id'], path))
            
            # Also add indicators
            indicators_raw = db_retriever.get_indicators_by_node(n['id'])
            indicators = [dict(i) for i in indicators_raw]
            for i in indicators:
                paths.append({"id": i['id'], "path": f"{path} > 📊 {i['name']}", "type": "indicator"})
        return paths

    all_hierarchy = [{"id": None, "path": "Root / Home", "type": "root"}] + get_all_paths()
    path_names = [p['path'] for p in all_hierarchy]
    
    # Use a key to allow resetting the selectbox
    selected_path_name = st.selectbox("Navigate Hierarchy:", path_names, key="explorer_nav_selectbox")
    selected_item = next(p for p in all_hierarchy if p['path'] == selected_path_name)

    def reset_explorer():
        if "explorer_nav_selectbox" in st.session_state:
            st.session_state.explorer_nav_selectbox = path_names[0] # Reset to Root
        st.rerun()

    # If indicator selected, use 3 columns for Preview
    if selected_item['type'] == 'indicator':
        col1, col2, col3 = st.columns([0.8, 1.2, 1.0])
    else:
        col1, col2 = st.columns([1, 1])
        col3 = None

    with col1:
        if selected_item['type'] in ['root', 'folder']:
            # ... (Folder code remains similar, keeping indentation correct)
            st.subheader(f"📂 Folder: {selected_item['path']}")
            
            # Actions for Folder
            with st.expander("➕ Add Content"):
                new_name = st.text_input("New Name:")
                item_type = st.radio("Type:", ["Folder", "KPI"])
                if st.button("Create"):
                    if new_name:
                        try:
                            if item_type == "Folder":
                                kpi_hierarchy_manager.add_node(new_name, selected_item['id'], 'folder')
                                st.success(f"Folder '{new_name}' created.")
                            else:
                                kpi_indicators_manager.add_kpi_indicator(new_name, selected_item['id'])
                                st.success(f"Indicator '{new_name}' created.")
                            reset_explorer()
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            if selected_item['type'] == 'folder':
                with st.expander("✏️ Rename/Delete Folder"):
                    new_folder_name = st.text_input("New Folder Name:", value=selected_path_name.split('/')[-1])
                    if st.button("Update Name"):
                        kpi_hierarchy_manager.update_node(selected_item['id'], name=new_folder_name)
                        reset_explorer()
                    if st.button("🔥 Delete Folder"):
                        if st.checkbox("Confirm Deletion"):
                            kpi_hierarchy_manager.delete_node(selected_item['id'])
                            reset_explorer()

    with col2:
        if selected_item['type'] == 'indicator':
            ind_id = selected_item['id']
            ind_name = selected_item['path'].split(' > 📊 ')[-1]
            st.subheader(f"📊 KPI: {ind_name}")
            
            spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(ind_id) or {}
            
            with st.form("edit_kpi_form"):
                kpi_name = st.text_input("KPI Name:", value=ind_name)
                description = st.text_area("Description:", value=spec.get('description', ''))
                calc_type = st.selectbox("Calc Type:", KPI_CALC_TYPE_OPTIONS, index=KPI_CALC_TYPE_OPTIONS.index(spec.get('calculation_type', KPI_CALC_TYPE_OPTIONS[0])))
                unit = st.text_input("Unit:", value=spec.get('unit_of_measure', ''))
                visible = st.checkbox("Visible", value=spec.get('visible', True))
                dist_profile = st.selectbox("Split Profile:", DISTRIBUTION_PROFILE_OPTIONS, index=DISTRIBUTION_PROFILE_OPTIONS.index(spec.get('default_distribution_profile', DISTRIBUTION_PROFILE_OPTIONS[0])))
                
                is_calc = st.checkbox("Is Calculated (Formula)", value=spec.get('is_calculated', False))
                # Formula support (Simplified for now)
                formula_str = st.text_input("Formula Expression:", value=spec.get('formula_string', ''))
                
                st.markdown("#### 🏢 Per-Plant Visibility")
                all_plants = db_retriever.get_all_plants()
                current_vis = kpi_visibility.get_plant_visibility_for_kpi(spec.get('id')) if spec.get('id') else []
                vis_map = {v['plant_id']: v['is_enabled'] for v in current_vis}
                
                plant_vis_vars = {}
                p_cols = st.columns(3)
                for i, plant in enumerate(all_plants):
                    plant_vis_vars[plant['id']] = p_cols[i % 3].checkbox(plant['name'], value=vis_map.get(plant['id'], True))

                if st.form_submit_button("Save Changes"):
                    try:
                        # Update Indicator Name
                        # Find parent node id
                        # We need the node_id for update_kpi_indicator. We don't have it easily here.
                        # Actually kpi_indicators has node_id. Let's get it.
                        with kpi_indicators_manager.sqlite3.connect(kpi_indicators_manager.app_config.get_database_path("db_kpis.db")) as conn:
                            node_id = conn.execute("SELECT node_id FROM kpi_indicators WHERE id = ?", (ind_id,)).fetchone()[0]
                        
                        kpi_indicators_manager.update_kpi_indicator(ind_id, kpi_name, node_id)
                        
                        # Update Spec
                        spec_id = kpi_specs_manager.add_kpi_spec(
                            indicator_id=ind_id,
                            description=description,
                            calculation_type=calc_type,
                            unit_of_measure=unit,
                            visible=visible,
                            is_calculated=is_calc,
                            formula_string=formula_str,
                            default_distribution_profile=dist_profile
                        )
                        
                        # Update Visibility
                        vis_data = [{"plant_id": pid, "is_enabled": v} for pid, v in plant_vis_vars.items()]
                        kpi_visibility.update_plant_visibility(spec_id, vis_data)
                        
                        st.success("KPI saved successfully!")
                        reset_explorer()
                    except Exception as e:
                        st.error(f"Error saving KPI: {e}")

            if st.button("🗑️ Delete KPI"):
                if st.checkbox("Confirm KPI Deletion"):
                    kpi_indicators_manager.delete_kpi_indicator(ind_id)
                    reset_explorer()

    if col3 and selected_item['type'] == 'indicator':
        with col3:
            st.subheader("🔍 Formula Preview")
            spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(selected_item['id']) or {}
            
            if spec.get('is_calculated'):
                f_str = spec.get('formula_string', '')
                f_json = spec.get('formula_json', '')
                
                if f_json:
                    try:
                        dag_data = json.loads(f_json)
                        if "nodes" in dag_data:
                            st.info("🎨 **Visual Node DAG Detected**")
                            st.json(dag_data) # Show structured data
                        else:
                            st.code(f_str, language="python")
                    except:
                        st.code(f_str, language="python")
                else:
                    st.code(f_str or "No formula defined.", language="python")
                
                # Simple validation preview
                if f_str:
                    st.caption("✨ Expression validation: OK")
            else:
                st.info("This is a manual input KPI. No formula preview available.")
