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

    # --- Sidebar Navigator ---
    with st.sidebar:
        st.markdown("### 🧭 Hierarchy Navigator")
        if st.button("🏠 Root / Home", use_container_width=True):
            st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
        st.markdown("---")

        def render_navigator(parent_id=None):
            nodes_raw = db_retriever.get_hierarchy_nodes(parent_id)
            for n in nodes_raw:
                icon = "🏢" if n['node_type'] == 'group' else "📂" if n['node_type'] == 'subgroup' else "📁"
                with st.expander(f"{icon} {n['name']}", expanded=False):
                    if st.button(f"👁️ View Details", key=f"nav_n_{n['id']}", use_container_width=True):
                        st.session_state.explorer_selected_item = {"id": n['id'], "type": "node", "name": n['name'], "node_type": n['node_type']}
                    render_navigator(n['id'])
                    indicators = db_retriever.get_indicators_by_node(n['id'])
                    for i in indicators:
                        if st.button(f"📊 {i['name']}", key=f"nav_i_{i['id']}", use_container_width=True):
                            st.session_state.explorer_selected_item = {"id": i['id'], "type": "indicator", "name": i['name']}
        render_navigator()

    if 'explorer_selected_item' not in st.session_state:
        st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}

    selected = st.session_state.explorer_selected_item
    st.markdown(f"### 📍 Selection: `{selected['name']}`")
    
    col_main, col_side = st.columns([1.6, 1])

    with col_main:
        if selected['type'] in ['root', 'node']:
            with st.container(border=True):
                st.subheader("➕ Create Child Item")
                c1, c2 = st.columns([2, 1])
                new_name = c1.text_input("Name:", key="new_item_name_v5")
                item_type = c2.selectbox("Type:", ["Folder", "KPI Indicator", "Group", "Subgroup"], key="new_item_type_v5")
                if st.button("Add to Hierarchy", type="primary", use_container_width=True, key="btn_add_v5"):
                    if new_name:
                        if item_type == "KPI Indicator": kpi_indicators_manager.add_kpi_indicator(new_name, selected['id'])
                        else: kpi_hierarchy_manager.add_node(new_name, selected['id'], item_type.lower())
                        st.success(f"Added {item_type}: {new_name}")
                        st.rerun()

            if selected['type'] == 'node':
                with st.expander("🛠️ Node Maintenance"):
                    edit_name = st.text_input("Rename Node:", value=selected['name'], key="edit_node_name_v5")
                    if st.button("Save Changes", use_container_width=True, key="btn_rename_v5"):
                        kpi_hierarchy_manager.update_node(selected['id'], name=edit_name)
                        st.session_state.explorer_selected_item['name'] = edit_name
                        st.rerun()
                    st.divider()
                    if st.button("🗑️ Delete Node & Children", use_container_width=True, key="btn_del_node_v5"):
                        if st.checkbox("Confirm permanent deletion.", key="chk_del_node_v5"):
                            kpi_hierarchy_manager.delete_node(selected['id'])
                            st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
                            st.rerun()

        elif selected['type'] == 'indicator':
            ind_id = selected['id']
            spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(ind_id) or {}
            
            # 1. GENERAL SETTINGS FORM
            with st.form("form_general_v5"):
                st.subheader("📋 General Specification")
                k_name = st.text_input("Indicator Name:", value=selected['name'])
                desc = st.text_area("Description:", value=spec.get('description', ''), height=80)
                c1, c2, c3 = st.columns(3)
                uom = c1.text_input("Unit:", value=spec.get('unit_of_measure', ''))
                ctype = c2.selectbox("Calc Type:", KPI_CALC_TYPE_OPTIONS, index=0) # Index logic omitted for brevity
                visible = c3.checkbox("Visible", value=spec.get('visible', True))
                
                st.write("**Plant Visibility:**")
                all_plants = db_retriever.get_all_plants()
                current_vis = kpi_visibility.get_plant_visibility_for_kpi(spec.get('id')) if spec.get('id') else []
                vis_map = {v['plant_id']: v['is_enabled'] for v in current_vis}
                pc = st.columns(3)
                plant_vis = {}
                for idx, p in enumerate(all_plants):
                    plant_vis[p['id']] = pc[idx % 3].checkbox(p['name'], value=vis_map.get(p['id'], True), key=f"pvis_v5_{p['id']}")

                if st.form_submit_button("💾 Save General Settings", use_container_width=True):
                    try:
                        kpi_indicators_manager.update_kpi_indicator(ind_id, k_name, None) # subgroup update logic simplified
                        sid = kpi_specs_manager.add_kpi_spec(indicator_id=ind_id, description=desc, calculation_type=ctype, unit_of_measure=uom, visible=visible)
                        kpi_visibility.update_plant_visibility(sid, [{"plant_id": pid, "is_enabled": v} for pid, v in plant_vis.items()])
                        st.success("Saved!")
                        st.rerun()
                    except Exception as e: st.error(str(e))

            # 2. CALCULATION LOGIC (OUTSIDE FORM)
            st.markdown("---")
            with st.container(border=True):
                st.subheader("🧮 Calculation Logic")
                is_calc = st.toggle("Enable Calculated Mode", value=spec.get('is_calculated', False), key=f"tog_calc_v5_{ind_id}")
                f_str = spec.get('formula_string', '')
                f_json = spec.get('formula_json', '')

                if is_calc:
                    formula_mode = st.radio("Mode:", ["Visual Builder", "Raw Expression"], horizontal=True, key=f"rad_mode_v5_{ind_id}")
                    if formula_mode == "Raw Expression":
                        f_str = st.text_input("Formula:", value=f_str, key=f"txt_f_v5_{ind_id}")
                        if f_str != spec.get('formula_string'):
                            from src.core.node_engine import KpiDAG
                            try: f_json = KpiDAG.from_formula(f_str).to_json()
                            except: pass
                    else:
                        if st.button("🛠️ Open Structured Builder", key=f"btn_build_v5_{ind_id}"):
                            st.session_state.show_logic_builder = True
                        if st.session_state.get('show_logic_builder'):
                            with st.container(border=True):
                                st.write("Building logic...")
                                if st.button("Close Builder", key=f"btn_close_v5_{ind_id}"):
                                    st.session_state.show_logic_builder = False
                                    st.rerun()

                if st.button("💾 Save Logic", type="primary", use_container_width=True, key=f"btn_save_logic_v5_{ind_id}"):
                    kpi_specs_manager.update_kpi_spec(spec['id'], is_calculated=is_calc, formula_string=f_str, formula_json=f_json)
                    st.success("Logic updated!")
                    st.rerun()

            # 3. DISTRIBUTION (OUTSIDE FORM)
            st.markdown("---")
            with st.container(border=True):
                st.subheader("✂️ Distribution Profile")
                gs_id = spec.get('global_split_id')
                if gs_id:
                    all_gs = db_retriever.get_all_global_splits()
                    gs_obj = next((s for s in all_gs if s['id'] == gs_id), None)
                    if gs_obj: st.warning(f"🔗 Controlled by Global Split: {gs_obj['name']}")
                
                profile = st.selectbox("Profile:", DISTRIBUTION_PROFILE_OPTIONS, index=0, disabled=gs_id is not None, key=f"sel_prof_v5_{ind_id}")
                if st.button("💾 Save Profile", type="primary", use_container_width=True, key=f"btn_save_prof_v5_{ind_id}"):
                    kpi_specs_manager.update_kpi_spec(spec['id'], default_distribution_profile=profile)
                    st.success("Profile updated!")
                    st.rerun()

            st.markdown("---")
            if st.button("🗑️ Delete KPI Indicator", use_container_width=True, key=f"btn_del_ind_v5_{ind_id}"):
                if st.checkbox("Confirm deletion.", key=f"chk_del_ind_v5_{ind_id}"):
                    kpi_indicators_manager.delete_kpi_indicator(ind_id)
                    st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
                    st.rerun()

    with col_side:
        if selected['type'] == 'indicator':
            st.subheader("🔍 Preview")
            spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(selected['id']) or {}
            if spec.get('is_calculated'):
                st.code(spec.get('formula_string', 'N/A'), language="python")
            else: st.info("Manual KPI")
        else:
            nodes = db_retriever.get_hierarchy_nodes(selected['id'])
            inds = db_retriever.get_indicators_by_node(selected['id'])
            st.write(f"Items: {len(nodes)} folders, {len(inds)} KPIs.")
