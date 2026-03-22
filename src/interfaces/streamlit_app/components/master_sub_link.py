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

    # --- Sidebar: Hierarchical Selector (Aligned with KPI Explorer) ---
    with st.sidebar:
        st.markdown("### 🧭 Hierarchy Navigator")
        st.caption("Select a KPI to manage its links")
        
        def get_role_icon(kpi_id):
            role_info = kpi_roles.get(kpi_id, {})
            role = role_info.get('role')
            if role == 'master': return "Ⓜ️"
            if role == 'sub': return "Ⓢ"
            return "📄"

        def render_navigator(parent_id=None):
            nodes_raw = db_retriever.get_hierarchy_nodes(parent_id)
            nodes = [dict(n) for n in nodes_raw]
            
            for n in nodes:
                icon = "🏢" if n['node_type'] == 'group' else "📂" if n['node_type'] == 'subgroup' else "📁"
                with st.expander(f"{icon} {n['name']}", expanded=False):
                    # Recurse
                    render_navigator(n['id'])
                    
                    # List KPIs
                    indicators = db_retriever.get_indicators_by_node(n['id'])
                    if indicators:
                        st.markdown("---")
                        for i in indicators:
                            spec = next((k for k in all_kpis_detailed if k['indicator_id'] == i['id']), None)
                            if spec:
                                icon = get_role_icon(spec['id'])
                                if st.button(f"{icon} {i['name']}", key=f"ms_nav_i_{spec['id']}", use_container_width=True):
                                    st.session_state.ms_selected_kpi_id = spec['id']

        render_navigator()

    # --- Main Content: Linkage Editor ---
    if 'ms_selected_kpi_id' not in st.session_state:
        st.info("👈 Please select a KPI from the hierarchy in the sidebar to manage its links.")
        return

    selected_kpi_id = st.session_state.ms_selected_kpi_id
    if selected_kpi_id not in kpi_map:
        st.error("Selected KPI not found.")
        return

    kpi = kpi_map[selected_kpi_id]
    role_info = kpi_roles.get(selected_kpi_id, {'role': None})
    
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
