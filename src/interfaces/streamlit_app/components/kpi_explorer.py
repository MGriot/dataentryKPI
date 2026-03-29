import streamlit as st
import pandas as pd
import json
import uuid
from src.kpi_management import hierarchy as kpi_hierarchy_manager
from src.kpi_management import indicators as kpi_indicators_manager
from src.kpi_management import specs as kpi_specs_manager
from src.kpi_management import visibility as kpi_visibility
from src import data_retriever as db_retriever
from src.interfaces.common_ui.constants import KPI_CALC_TYPE_OPTIONS, DISTRIBUTION_PROFILE_OPTIONS

def app():
    st.title("📁 KPI Management Explorer")

    # --- Session State Initialization ---
    if 'explorer_selected_item' not in st.session_state:
        st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
    if 'show_logic_builder' not in st.session_state:
        st.session_state.show_logic_builder = False

    # --- Sidebar Navigator ---
    with st.sidebar:
        st.markdown("### 🧭 Hierarchy Navigator")
        if st.button("🏠 Root / Home", use_container_width=True):
            st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
            st.session_state.show_logic_builder = False
        st.markdown("---")

        def render_navigator(parent_id=None):
            nodes_raw = db_retriever.get_hierarchy_nodes(parent_id)
            for n in nodes_raw:
                icon = "🏢" if n['node_type'] == 'group' else "📂" if n['node_type'] == 'subgroup' else "📁"
                with st.expander(f"{icon} {n['name']}", expanded=False):
                    if st.button(f"👁️ View Details", key=f"nav_n_{n['id']}", use_container_width=True):
                        st.session_state.explorer_selected_item = {"id": n['id'], "type": "node", "name": n['name'], "node_type": n['node_type']}
                        st.session_state.show_logic_builder = False
                    render_navigator(n['id'])
                    indicators = db_retriever.get_indicators_by_node(n['id'])
                    for i in indicators:
                        if st.button(f"📊 {i['name']}", key=f"nav_i_{i['id']}", use_container_width=True):
                            st.session_state.explorer_selected_item = {"id": i['id'], "type": "indicator", "name": i['name']}
                            st.session_state.show_logic_builder = False
        render_navigator()

    selected = st.session_state.explorer_selected_item
    st.markdown(f"### 📍 Selection: `{selected['name']}`")
    
    col_main, col_side = st.columns([1.6, 1])

    with col_main:
        if selected['type'] in ['root', 'node']:
            with st.container(border=True):
                st.subheader("➕ Create Child Item")
                c1, c2 = st.columns([2, 1])
                new_name = c1.text_input("Name:", key="new_item_name_v6")
                item_type = c2.selectbox("Type:", ["Folder", "KPI Indicator", "Group", "Subgroup"], key="new_item_type_v6")
                if st.button("Add to Hierarchy", type="primary", use_container_width=True, key="btn_add_v6"):
                    if new_name:
                        if item_type == "KPI Indicator": kpi_indicators_manager.add_kpi_indicator(new_name, selected['id'])
                        else: kpi_hierarchy_manager.add_node(new_name, selected['id'], item_type.lower())
                        st.success(f"Added {item_type}: {new_name}")
                        st.rerun()

            if selected['type'] == 'node':
                with st.expander("🛠️ Node Maintenance"):
                    edit_name = st.text_input("Rename Node:", value=selected['name'], key="edit_node_name_v6")
                    if st.button("Save Changes", use_container_width=True, key="btn_rename_v6"):
                        kpi_hierarchy_manager.update_node(selected['id'], name=edit_name)
                        st.session_state.explorer_selected_item['name'] = edit_name
                        st.rerun()
                    st.divider()
                    if st.button("🗑️ Delete Node & Children", use_container_width=True, key="btn_del_node_v6"):
                        if st.checkbox("Confirm permanent deletion.", key="chk_del_node_v6"):
                            kpi_hierarchy_manager.delete_node(selected['id'])
                            st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
                            st.rerun()

        elif selected['type'] == 'indicator':
            ind_id = selected['id']
            spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(ind_id) or {}
            
            with st.form("form_general_v6"):
                st.subheader("📋 General Specification")
                k_name = st.text_input("Indicator Name:", value=selected['name'])
                desc = st.text_area("Description:", value=spec.get('description', ''), height=80)
                c1, c2, c3 = st.columns(3)
                uom = c1.text_input("Unit:", value=spec.get('unit_of_measure', ''))
                ctype = c2.selectbox("Calc Type:", KPI_CALC_TYPE_OPTIONS, index=0)
                visible = c3.checkbox("Visible", value=spec.get('visible', True))
                
                st.write("**Plant Visibility:**")
                all_plants = db_retriever.get_all_plants()
                current_vis = kpi_visibility.get_plant_visibility_for_kpi(spec.get('id')) if spec.get('id') else []
                vis_map = {v['plant_id']: v['is_enabled'] for v in current_vis}
                pc = st.columns(3)
                plant_vis = {}
                for idx, p in enumerate(all_plants):
                    plant_vis[p['id']] = pc[idx % 3].checkbox(p['name'], value=vis_map.get(p['id'], True), key=f"pvis_v6_{p['id']}")

                if st.form_submit_button("💾 Save General Settings", use_container_width=True):
                    try:
                        # Find node_id for this indicator to avoid unlinking
                        all_inds = db_retriever.get_all_kpi_indicators()
                        this_ind = next((i for i in all_inds if i['id'] == ind_id), None)
                        node_id = this_ind['node_id'] if this_ind else None
                        
                        kpi_indicators_manager.update_kpi_indicator(ind_id, k_name, node_id)
                        sid = kpi_specs_manager.add_kpi_spec(indicator_id=ind_id, description=desc, calculation_type=ctype, unit_of_measure=uom, visible=visible)
                        kpi_visibility.update_plant_visibility(sid, [{"plant_id": pid, "is_enabled": v} for pid, v in plant_vis.items()])
                        st.success("General settings saved!")
                        st.rerun()
                    except Exception as e: st.error(str(e))

            # --- CALCULATION LOGIC (OUTSIDE FORM) ---
            st.markdown("---")
            with st.container(border=True):
                st.subheader("🧮 Calculation Logic")
                is_calc = st.toggle("Enable Calculated Mode", value=spec.get('is_calculated', False), key=f"tog_calc_v6_{ind_id}")
                
                # These variables store the "in-flight" formula before saving
                if f"temp_f_str_{ind_id}" not in st.session_state:
                    st.session_state[f"temp_f_str_{ind_id}"] = spec.get('formula_string', '')
                if f"temp_f_json_{ind_id}" not in st.session_state:
                    st.session_state[f"temp_f_json_{ind_id}"] = spec.get('formula_json', '')

                if is_calc:
                    formula_mode = st.radio("Editor Mode:", ["Visual Builder", "Raw Expression"], horizontal=True, key=f"rad_mode_v6_{ind_id}")
                    
                    if formula_mode == "Raw Expression":
                        f_input = st.text_input("Formula Expression:", value=st.session_state[f"temp_f_str_{ind_id}"], key=f"txt_f_v6_{ind_id}")
                        if f_input != st.session_state[f"temp_f_str_{ind_id}"]:
                            st.session_state[f"temp_f_str_{ind_id}"] = f_input
                            from src.core.node_engine import KpiDAG
                            try:
                                dag = KpiDAG.from_formula(f_input)
                                st.session_state[f"temp_f_json_{ind_id}"] = dag.to_json()
                            except: pass
                    else:
                        # --- Structured Visual Builder ---
                        st.info("Structured Formula Builder")
                        if st.session_state[f"temp_f_str_{ind_id}"]:
                            st.success(f"Logic: `{st.session_state[f'temp_f_str_{ind_id}']}`")
                        
                        if st.button("🛠️ Open Logic Builder", key=f"btn_open_builder_{ind_id}", use_container_width=True):
                            st.session_state.show_logic_builder = True
                        
                        if st.session_state.show_logic_builder:
                            with st.container(border=True):
                                st.markdown("#### 🔧 Build Logic")
                                all_kpis = db_retriever.get_all_kpis_detailed(only_visible=True)
                                kpi_options = {f"{k['indicator_name']} [ID:{k['id']}]": k['id'] for k in all_kpis if k['id'] != spec.get('id')}
                                
                                c1, c2 = st.columns(2)
                                with c1:
                                    sel_kpi = st.selectbox("Insert KPI Reference:", ["Select..."] + list(kpi_options.keys()), key=f"build_kpi_{ind_id}")
                                    if sel_kpi != "Select...":
                                        ref_id = kpi_options[sel_kpi]
                                        st.session_state[f"temp_f_str_{ind_id}"] += f"[{ref_id}]"
                                        st.rerun()
                                with c2:
                                    sel_op = st.selectbox("Insert Operator:", ["Select...", "+", "-", "*", "/", "(", ")", "min(", "max(", "avg(", ","], key=f"build_op_{ind_id}")
                                    if sel_op != "Select...":
                                        st.session_state[f"temp_f_str_{ind_id}"] += sel_op
                                        st.rerun()
                                
                                if st.button("🗑️ Clear Formula", key=f"build_clear_{ind_id}"):
                                    st.session_state[f"temp_f_str_{ind_id}"] = ""
                                    st.session_state[f"temp_f_json_{ind_id}"] = ""
                                    st.rerun()
                                
                                if st.button("✅ Done Building", key=f"build_done_{ind_id}", use_container_width=True):
                                    st.session_state.show_logic_builder = False
                                    from src.core.node_engine import KpiDAG
                                    try:
                                        dag = KpiDAG.from_formula(st.session_state[f"temp_f_str_{ind_id}"])
                                        st.session_state[f"temp_f_json_{ind_id}"] = dag.to_json()
                                    except: pass
                                    st.rerun()

                if st.button("💾 Save Calculation Logic", type="primary", use_container_width=True, key=f"save_logic_{ind_id}"):
                    try:
                        kpi_specs_manager.update_kpi_spec(
                            spec['id'], 
                            is_calculated=is_calc, 
                            formula_string=st.session_state[f"temp_f_str_{ind_id}"], 
                            formula_json=st.session_state[f"temp_f_json_{ind_id}"]
                        )
                        st.success("Calculation logic updated!")
                        st.rerun()
                    except Exception as e: st.error(str(e))

            # --- DISTRIBUTION (OUTSIDE FORM) ---
            st.markdown("---")
            with st.container(border=True):
                st.subheader("✂️ Distribution Profile")
                gs_id = spec.get('global_split_id')
                if gs_id:
                    all_gs = db_retriever.get_all_global_splits()
                    gs_obj = next((s for s in all_gs if s['id'] == gs_id), None)
                    if gs_obj: st.warning(f"🔗 Controlled by Global Split: {gs_obj['name']}")
                
                profile = st.selectbox("Profile:", DISTRIBUTION_PROFILE_OPTIONS, index=0, disabled=gs_id is not None, key=f"sel_prof_v6_{ind_id}")
                if st.button("💾 Save Profile", type="primary", use_container_width=True, key=f"save_prof_v6_{ind_id}"):
                    kpi_specs_manager.update_kpi_spec(spec['id'], default_distribution_profile=profile)
                    st.success("Profile updated!")
                    st.rerun()

            st.markdown("---")
            if st.button("🗑️ Delete KPI Indicator", use_container_width=True, key=f"del_ind_v6_{ind_id}"):
                if st.checkbox("Confirm deletion.", key=f"chk_del_ind_v6_{ind_id}"):
                    kpi_indicators_manager.delete_kpi_indicator(ind_id)
                    st.session_state.explorer_selected_item = {"id": None, "type": "root", "name": "Root"}
                    st.rerun()

    with col_side:
        if selected['type'] == 'indicator':
            st.subheader("🔍 Preview")
            spec = kpi_specs_manager.get_kpi_spec_by_indicator_id(selected['id']) or {}
            if spec.get('is_calculated'):
                st.code(spec.get('formula_string', 'N/A'), language="python")
                if spec.get('formula_json'):
                    with st.expander("Logic Schema"):
                        st.json(json.loads(spec['formula_json']))
            else: st.info("Manual KPI")
        else:
            nodes = db_retriever.get_hierarchy_nodes(selected['id'])
            inds = db_retriever.get_indicators_by_node(selected['id'])
            st.write(f"Items: {len(nodes)} folders, {len(inds)} KPIs.")
