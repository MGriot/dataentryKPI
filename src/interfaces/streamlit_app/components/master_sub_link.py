import streamlit as st
import pandas as pd
import json
from src.kpi_management import links as kpi_links_manager
from src import data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name

def app():
    st.title("🔗 Master/Sub Link Management")
    st.markdown("Define relationships between Master KPIs and their contributing Sub-KPIs.")

    # --- Fetch All Data ---
    all_kpis_detailed = db_retriever.get_all_kpis_detailed()
    kpi_map = {k['id']: k for k in all_kpis_detailed}
    
    # Pre-fetch roles for all KPIs to show in the tree
    kpi_roles = {}
    for k in all_kpis_detailed:
        kpi_roles[k['id']] = db_retriever.get_kpi_role_details(k['id'])

    # --- Sidebar: Hierarchical Selector ---
    st.sidebar.subheader("Select KPI to Manage")
    
    def get_role_icon(kpi_id):
        role_info = kpi_roles.get(kpi_id, {})
        role = role_info.get('role')
        if role == 'master': return "Ⓜ️"
        if role == 'sub': return "Ⓢ"
        return "📄"

    # Get full paths for hierarchical display
    def get_all_paths():
        paths = []
        def walk(parent_id=None, current_path=""):
            nodes = db_retriever.get_hierarchy_nodes(parent_id)
            for n in nodes:
                p = f"{current_path}/{n['name']}" if current_path else n['name']
                paths.append({"id": n['id'], "path": f"📁 {p}", "type": "folder"})
                walk(n['id'], p)
            
            inds = db_retriever.get_indicators_by_node(parent_id) if parent_id else []
            for i in inds:
                # Find the KPI spec ID for this indicator
                spec = next((k for k in all_kpis_detailed if k['actual_indicator_id'] == i['id']), None)
                if spec:
                    icon = get_role_icon(spec['id'])
                    p = f"{current_path}/{i['name']}" if current_path else i['name']
                    paths.append({"id": spec['id'], "path": f"{icon} {p}", "type": "kpi"})
        walk()
        return paths

    hierarchy_paths = get_all_paths()
    path_names = [p['path'] for p in hierarchy_paths]
    
    selected_path = st.sidebar.selectbox("Navigate Hierarchy:", path_names)
    selected_item = next(p for p in hierarchy_paths if p['path'] == selected_path)

    if selected_item['type'] == 'folder':
        st.info("Please select a KPI from the hierarchy to manage its links. Folders are indicated with 📁.")
        return

    # --- Main Content: Linkage Editor ---
    selected_kpi_id = selected_item['id']
    kpi = kpi_map[selected_kpi_id]
    role_info = kpi_roles[selected_kpi_id]
    
    st.subheader(f"KPI: {get_kpi_display_name(kpi)}")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric("Current Role", role_info['role'].capitalize())
    with col2:
        if role_info['role'] == 'sub':
            master_kpi = kpi_map.get(role_info['master_id'])
            if master_kpi:
                st.write(f"**Linked to Master:** {get_kpi_display_name(master_kpi)}")

    if role_info['role'] == 'master' or role_info['role'] is None:
        st.divider()
        st.subheader("Linked Sub-KPIs")
        
        links = db_retriever.get_linked_sub_kpis_detailed(selected_kpi_id)
        if links:
            # Table-like view with actions
            for link in links:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([0.5, 0.3, 0.2])
                    with c1:
                        st.write(f"Ⓢ **{link['indicator_name']}**")
                    with c2:
                        new_weight = st.number_input("Weight", value=float(link['distribution_weight']), key=f"w_{link['id']}", step=0.1)
                        if new_weight != float(link['distribution_weight']):
                            kpi_links_manager.update_link_weight(selected_kpi_id, link['id'], new_weight)
                            st.rerun()
                    with c3:
                        if st.button("Unlink", key=f"unl_{link['id']}"):
                            kpi_links_manager.unlink_sub_kpi(selected_kpi_id, link['id'])
                            st.rerun()
        else:
            st.info("No sub-KPIs currently linked.")

        # --- Link New Sub-KPI ---
        with st.expander("➕ Link new Sub-KPI"):
            # Available = any KPI that isn't this one, and isn't already a master or a sub of something else
            all_links = db_retriever.get_all_master_sub_kpi_links()
            used_ids = {l['master_kpi_spec_id'] for l in all_links} | {l['sub_kpi_spec_id'] for l in all_links}
            
            # Allow linking KPIs that are currently None (unlinked)
            available = [k for k in all_kpis_detailed if k['id'] != selected_kpi_id and k['id'] not in used_ids]
            
            if available:
                avail_names = [get_kpi_display_name(k) for k in available]
                to_link_name = st.selectbox("Select KPI to link:", avail_names)
                to_link_weight = st.number_input("Initial Weight", value=1.0, step=0.1)
                
                if st.button("Confirm Link"):
                    to_link_kpi = next(k for k in available if get_kpi_display_name(k) == to_link_name)
                    try:
                        kpi_links_manager.link_sub_kpi(selected_kpi_id, to_link_kpi['id'], to_link_weight)
                        st.success("Linked successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("No unlinked KPIs available to become sub-KPIs.")

    elif role_info['role'] == 'sub':
        st.info("This KPI is already a Sub-KPI. A KPI cannot be both a Master and a Sub.")
        if st.button("Unlink from Master"):
            kpi_links_manager.unlink_sub_kpi(role_info['master_id'], selected_kpi_id)
            st.success("Unlinked!")
            st.rerun()
