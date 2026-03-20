import streamlit as st
import pandas as pd
import json
from src.kpi_management import hierarchy as kpi_hierarchy_manager
from src.kpi_management import indicators as kpi_indicators_manager
from src.kpi_management import specs as kpi_specs_manager
from src.kpi_management import visibility as kpi_visibility
from src import data_retriever as db_retriever
from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS, DISTRIBUTION_PROFILE_OPTIONS

def app():
    st.title("📁 KPI Management Explorer")

    # --- Sidebar Navigator (Recursive Nested Expanders) ---
    with st.sidebar:
        st.markdown("### 🧭 Hierarchy Navigator")
        
        if st.button("🏠 Root / Home", use_container_width=True):
            st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
        
        st.markdown("---")

        def render_navigator(parent_id=None):
            """Recursively renders nodes as nested expanders."""
            nodes_raw = db_retriever.get_hierarchy_nodes(parent_id)
            nodes = [dict(n) for n in nodes_raw]
            
            for n in nodes:
                icon = "🏢" if n['node_type'] == 'group' else "📂" if n['node_type'] == 'subgroup' else "📁"
                
                # IMPORTANT: Use st.expander (not st.sidebar.expander) while inside 'with st.sidebar'
                # to allow true recursive nesting within the sidebar.
                with st.expander(f"{icon} {n['name']}", expanded=False):
                    # Selection button to manage this specific node
                    if st.button(f"👁️ View Node Details", key=f"nav_n_{n['id']}", use_container_width=True):
                        st.session_state.explorer_selected_item = {
                            "id": n['id'], "type": "node", "name": n['name'], "node_type": n['node_type']
                        }
                    
                    # 1. Recurse for nested nodes (Folders/Subgroups)
                    render_navigator(n['id'])
                    
                    # 2. List KPIs (Indicators) inside this node
                    indicators = db_retriever.get_indicators_by_node(n['id'])
                    if indicators:
                        st.markdown("---")
                        for i in indicators:
                            if st.button(f"📊 {i['name']}", key=f"nav_i_{i['id']}", use_container_width=True):
                                st.session_state.explorer_selected_item = {
                                    "id": i['id'], "type": "indicator", "name": i['name']
                                }

        render_navigator()

    # --- Main Content Area ---
    if 'explorer_selected_item' not in st.session_state:
        st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}

    selected = st.session_state.explorer_selected_item
    
    # Header with Breadcrumb-style title
    st.markdown(f"### 📍 Selection: `{selected['name']}`")
    
    col_props, col_preview = st.columns([1.6, 1])

    with col_props:
        if selected['type'] in ['root', 'node']:
            # --- Node Management View ---
            with st.container(border=True):
                st.subheader("➕ Create Child Item")
                st.write(f"Add a new element inside **{selected['name']}**")
                
                c1, c2 = st.columns([2, 1])
                new_name = c1.text_input("Name:", key="new_item_name_v4")
                item_type = c2.selectbox("Type:", ["Folder", "KPI Indicator", "Group", "Subgroup"], key="new_item_type_v4")
                
                if st.button("Add to Hierarchy", type="primary", use_container_width=True):
                    if new_name:
                        try:
                            if item_type == "KPI Indicator":
                                kpi_indicators_manager.add_kpi_indicator(new_name, selected['id'])
                            else:
                                kpi_hierarchy_manager.add_node(new_name, selected['id'], item_type.lower())
                            st.success(f"Added {item_type}: {new_name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            if selected['type'] == 'node':
                with st.expander("🛠️ Node Maintenance"):
                    edit_name = st.text_input("Rename Node:", value=selected['name'], key="edit_node_name_v4")
                    if st.button("Save Changes", use_container_width=True):
                        kpi_hierarchy_manager.update_node(selected['id'], name=edit_name)
                        st.session_state.explorer_selected_item['name'] = edit_name
                        st.rerun()
                    
                    st.markdown("---")
                    st.warning("⚠️ **Danger Zone**")
                    if st.button("🗑️ Delete Node & All Children", use_container_width=True):
                        if st.checkbox("I understand this will permanently delete this node and all nested contents."):
                            kpi_hierarchy_manager.delete_node(selected['id'])
                            st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
                            st.rerun()

        elif selected['type'] == 'indicator':
            # --- KPI Specification Form ---
            ind_id = selected['id']
            spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(ind_id) or {}
            
            with st.form("kpi_property_sheet_v4"):
                st.subheader("📋 KPI Specification")
                
                k_name = st.text_input("Indicator Name:", value=selected['name'])
                desc = st.text_area("Description:", value=spec.get('description', ''), height=100)
                
                c1, c2, c3 = st.columns([1, 1, 1])
                uom = c1.text_input("Unit:", value=spec.get('unit_of_measure', ''))
                ctype = c2.selectbox("Calculation Type:", KPI_CALC_TYPE_OPTIONS, 
                                   index=KPI_CALC_TYPE_OPTIONS.index(spec.get('calculation_type', 'Manual') 
                                   if spec.get('calculation_type') in KPI_CALC_TYPE_OPTIONS else 0))
                visible = c3.checkbox("Is Visible", value=spec.get('visible', True))
                
                st.markdown("---")
                st.subheader("🧮 Logic")
                is_calc = st.toggle("Calculated via Formula", value=spec.get('is_calculated', False))
                f_str = st.text_input("Formula Expression:", value=spec.get('formula_string', ''), 
                                    disabled=not is_calc)
                
                st.markdown("---")
                st.subheader("🏭 Plant Visibility")
                all_plants = db_retriever.get_all_plants()
                current_vis = kpi_visibility.get_plant_visibility_for_kpi(spec.get('id')) if spec.get('id') else []
                vis_map = {v['plant_id']: v['is_enabled'] for v in current_vis}
                
                pc = st.columns(3)
                plant_vis = {}
                for idx, p in enumerate(all_plants):
                    plant_vis[p['id']] = pc[idx % 3].checkbox(p['name'], value=vis_map.get(p['id'], True), key=f"pvis_v4_{p['id']}")

                if st.form_submit_button("Update All Settings", type="primary", use_container_width=True):
                    try:
                        with kpi_indicators_manager.sqlite3.connect(kpi_indicators_manager.app_config.get_database_path("db_kpis.db")) as conn:
                            node_id = conn.execute("SELECT node_id FROM kpi_indicators WHERE id = ?", (ind_id,)).fetchone()[0]
                        kpi_indicators_manager.update_kpi_indicator(ind_id, k_name, node_id)
                        
                        sid = kpi_specs_manager.add_kpi_spec(
                            indicator_id=ind_id, description=desc, calculation_type=ctype,
                            unit_of_measure=uom, visible=visible, is_calculated=is_calc, formula_string=f_str
                        )
                        kpi_visibility.update_plant_visibility(sid, [{"plant_id": pid, "is_enabled": v} for pid, v in plant_vis.items()])
                        st.success("✅ Changes saved!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            if st.button("🗑️ Delete KPI", use_container_width=True):
                if st.checkbox("Confirm permanent deletion."):
                    kpi_indicators_manager.delete_kpi_indicator(ind_id)
                    st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
                    st.rerun()

    with col_preview:
        if selected['type'] == 'indicator':
            st.subheader("🔍 Formula Insight")
            spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(selected['id']) or {}
            if spec.get('is_calculated'):
                with st.container(border=True):
                    st.markdown("**Expression:**")
                    st.code(spec.get('formula_string', 'No formula defined'), language="python")
                    if spec.get('formula_json'):
                        with st.expander("Show Logic Schema"):
                            st.json(json.loads(spec.get('formula_json')))
            else:
                st.info("Manual Entry KPI.")
        else:
            st.subheader("📁 Content Summary")
            subnodes = db_retriever.get_hierarchy_nodes(selected['id'])
            indicators = db_retriever.get_indicators_by_node(selected['id'])
            st.write(f"Contains **{len(subnodes)}** child folders and **{len(indicators)}** KPIs.")
            if indicators:
                st.markdown("**Child KPIs:**")
                for i in indicators:
                    st.write(f"- 📊 {i['name']}")
