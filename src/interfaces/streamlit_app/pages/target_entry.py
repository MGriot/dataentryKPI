import streamlit as st
import datetime
import json

from src.target_management import annual as annual_targets_manager
import src.data_retriever as db_retriever
from src.interfaces.common_ui.helpers import get_kpi_display_name
from src.interfaces.common_ui.constants import (
    REPARTITION_LOGIC_YEAR,
    REPARTITION_LOGIC_MONTH,
    REPARTITION_LOGIC_QUARTER,
    REPARTITION_LOGIC_WEEK,
    PROFILE_EVEN,
    PROFILE_ANNUAL_PROGRESSIVE,
    PROFILE_TRUE_ANNUAL_SINUSOIDAL,
    PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
    PROFILE_MONTHLY_SINUSOIDAL,
    PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
    PROFILE_QUARTERLY_PROGRESSIVE,
    PROFILE_QUARTERLY_SINUSOIDAL,
)

# --- Helper Functions ---
def _get_repartition_profiles():
    return [
        PROFILE_EVEN,
        PROFILE_ANNUAL_PROGRESSIVE,
        PROFILE_TRUE_ANNUAL_SINUSOIDAL,
        PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS,
        PROFILE_MONTHLY_SINUSOIDAL,
        PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE,
        PROFILE_QUARTERLY_PROGRESSIVE,
        PROFILE_QUARTERLY_SINUSOIDAL,
    ]

def _get_repartition_logics():
    return [
        REPARTITION_LOGIC_YEAR,
        REPARTITION_LOGIC_MONTH,
        REPARTITION_LOGIC_QUARTER,
        REPARTITION_LOGIC_WEEK,
    ]

def load_kpi_targets_for_entry_target():
    if not st.session_state.selected_year_target or not st.session_state.selected_plant_name_target:
        st.session_state.kpis_for_entry = []
        st.session_state.targets_map_for_entry = {}
        st.session_state.hist1_map_for_entry = {}
        st.session_state.hist2_map_for_entry = {}
        return

    year = int(st.session_state.selected_year_target)
    plant_id = st.session_state.plants_map_target.get(st.session_state.selected_plant_name_target)

    if plant_id is None:
        st.error("Plant ID not found.")
        st.session_state.kpis_for_entry = []
        st.session_state.targets_map_for_entry = {}
        st.session_state.hist1_map_for_entry = {}
        st.session_state.hist2_map_for_entry = {}
        return

    st.session_state.kpis_for_entry = [dict(row) for row in db_retriever.get_all_kpis_detailed(only_visible=True, plant_id=plant_id)]
    
    # Current year
    targets = [dict(row) for row in db_retriever.get_annual_targets(plant_id, year)]
    st.session_state.targets_map_for_entry = {t['kpi_id']: t for t in targets}
    
    # Historical years
    hist1 = [dict(row) for row in db_retriever.get_annual_targets(plant_id, year - 1)]
    st.session_state.hist1_map_for_entry = {t['kpi_id']: t for t in hist1}
    
    hist2 = [dict(row) for row in db_retriever.get_annual_targets(plant_id, year - 2)]
    st.session_state.hist2_map_for_entry = {t['kpi_id']: t for t in hist2}

    # Initialize input values in session state for each KPI
    target_config = st.session_state.settings.get('targets', [{"id": 1, "name": "Target"}])
    
    for kpi in st.session_state.kpis_for_entry:
        kpi_id = kpi['id']
        target_data = st.session_state.targets_map_for_entry.get(kpi_id, {})
        target_values = target_data.get('target_values', [])
        
        # We always use the global config for targets
        st.session_state[f'target_numbers_{kpi_id}'] = [t['id'] for t in target_config]

        # Initialize each target
        for tn in st.session_state[f'target_numbers_{kpi_id}']:
            tv_rec = next((tv for tv in target_values if tv['target_number'] == tn), {})
            
            st.session_state[f'target_{kpi_id}_{tn}'] = tv_rec.get('target_value')
            st.session_state[f'manual_{kpi_id}_{tn}'] = bool(tv_rec.get('is_manual', True))

        # Repartition profile and values (shared for all targets of this KPI)
        st.session_state[f'distribution_profile_{kpi_id}'] = target_data.get('distribution_profile', PROFILE_EVEN)
        st.session_state[f'repartition_logic_{kpi_id}'] = target_data.get('repartition_logic', REPARTITION_LOGIC_YEAR)
        st.session_state[f'repartition_values_{kpi_id}'] = json.loads(target_data.get('repartition_values', '{}') or '{}')
        st.session_state[f'profile_params_{kpi_id}'] = json.loads(target_data.get('profile_params', '{}') or '{}')
        st.session_state[f'global_split_id_{kpi_id}'] = target_data.get('global_split_id')

def save_all_targets_entry():
    year_str = st.session_state.selected_year_target
    plant_name = st.session_state.selected_plant_name_target

    if not year_str or not plant_name:
        st.error("Year and plant must be selected.")
        return

    year = int(year_str)
    plant_id = st.session_state.plants_map_target.get(plant_name)

    targets_data_map = {}
    for kpi in st.session_state.kpis_for_entry:
        kpi_id = kpi['id']
        
        target_list_to_save = []
        target_nums = st.session_state.get(f'target_numbers_{kpi_id}', [1, 2])
        
        for tn in target_nums:
            try:
                t_val = st.session_state.get(f'target_{kpi_id}_{tn}')
                # Convert empty strings to None, attempt float conversion
                t_val = float(t_val) if t_val is not None and str(t_val).strip() != '' else 0.0
            except ValueError:
                st.error(f"Invalid value for KPI {get_kpi_display_name(kpi)} Target {tn}. Please enter a number.")
                return

            target_list_to_save.append({
                'target_number': tn,
                'target_value': t_val,
                'is_manual': st.session_state.get(f'manual_{kpi_id}_{tn}', True),
            })

        distribution_profile = st.session_state.get(f'distribution_profile_{kpi_id}', PROFILE_EVEN)
        repartition_logic = st.session_state.get(f'repartition_logic_{kpi_id}', REPARTITION_LOGIC_YEAR)
        repartition_values = st.session_state.get(f'repartition_values_{kpi_id}', {})
        profile_params = st.session_state.get(f'profile_params_{kpi_id}', {})
        global_split_id = st.session_state.get(f'global_split_id_{kpi_id}')

        targets_data = {
            'targets': target_list_to_save,
            'distribution_profile': distribution_profile,
            'repartition_logic': repartition_logic,
            'repartition_values': json.dumps(repartition_values),
            'profile_params': json.dumps(profile_params),
            'global_split_id': global_split_id
        }
        targets_data_map[str(kpi_id)] = targets_data

    try:
        annual_targets_manager.save_annual_targets(
            year=year,
            plant_id=plant_id,
            targets_data_map=targets_data_map
        )
        st.success("All targets have been saved.")
        load_kpi_targets_for_entry_target() # Reload data to show updated state
    except Exception as e:
        st.error(f"Error saving targets: {e}")
        st.exception(e)

def _on_manual_toggle(kpi_id, target_num):
    pass

def _update_repartition_input_area_streamlit(kpi_id):
    # This function will be called on profile/logic change to re-render the dynamic inputs
    pass # Logic will be implemented directly in the main app() function

def app():
    st.title("🎯 Target Entry")

    # Fetch Global Splits for the selector
    global_splits = db_retriever.get_all_global_splits()
    gs_options = {f"{s['year']} - {s['name']}": s['id'] for s in global_splits}
    gs_names = ["None (Custom)"] + list(gs_options.keys())

    # Initialize session state variables if they don't exist
    if 'selected_year_target' not in st.session_state:
        st.session_state.selected_year_target = str(datetime.datetime.now().year)
    if 'selected_plant_name_target' not in st.session_state:
        st.session_state.selected_plant_name_target = None
    if 'plants_map_target' not in st.session_state:
        st.session_state.plants_map_target = {}
    if 'kpis_for_entry' not in st.session_state:
        st.session_state.kpis_for_entry = []
    if 'targets_map_for_entry' not in st.session_state:
        st.session_state.targets_map_for_entry = {}
    if 'hist1_map_for_entry' not in st.session_state:
        st.session_state.hist1_map_for_entry = {}
    if 'hist2_map_for_entry' not in st.session_state:
        st.session_state.hist2_map_for_entry = {}
    if 'target_search_query' not in st.session_state:
        st.session_state.target_search_query = ""

    # --- Top Bar Filters ---
    with st.container(border=True):
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            current_year = datetime.datetime.now().year
            years = [str(y) for y in range(current_year - 5, current_year + 5)]
            st.session_state.selected_year_target = st.selectbox(
                "📅 Year:",
                years,
                index=years.index(st.session_state.selected_year_target) if st.session_state.selected_year_target in years else 0,
                key="year_select_target",
                on_change=load_kpi_targets_for_entry_target
            )

        with col2:
            plants_all = db_retriever.get_all_plants(visible_only=True)
            st.session_state.plants_map_target = {s['name']: s['id'] for s in plants_all}
            plant_names = list(st.session_state.plants_map_target.keys())

            if not plant_names:
                st.warning("No plants available.")
                st.session_state.selected_plant_name_target = None
            else:
                if st.session_state.selected_plant_name_target not in plant_names:
                    st.session_state.selected_plant_name_target = plant_names[0]
                
                st.session_state.selected_plant_name_target = st.selectbox(
                    "🏭 Plant:",
                    plant_names,
                    index=plant_names.index(st.session_state.selected_plant_name_target),
                    key="plant_select_target",
                    on_change=load_kpi_targets_for_entry_target
                )
        
        with col3:
            st.markdown("<br>", unsafe_allow_html=True) # Spacer
            if st.button("💾 SAVE ALL", use_container_width=True, type="primary"):
                save_all_targets_entry()

    # Initial load of data
    if st.session_state.selected_plant_name_target is not None and not st.session_state.kpis_for_entry:
        load_kpi_targets_for_entry_target()

    # --- Main Layout with Sidebar Navigation ---
    main_col, side_col = st.columns([3, 1])

    with side_col:
        st.subheader("🔍 Quick Find")
        st.session_state.target_search_query = st.text_input("Search KPI:", value=st.session_state.target_search_query, placeholder="e.g. OEE, Yield...")
        
        st.subheader("🌲 KPI List")
        filtered_kpis = [k for k in st.session_state.kpis_for_entry if st.session_state.target_search_query.lower() in get_kpi_display_name(k).lower()]
        
        for kpi in filtered_kpis:
            kpi_id = kpi['id']
            if st.button(f"📍 {get_kpi_display_name(kpi)}", key=f"nav_{kpi_id}", use_container_width=True):
                # Anchor scrolling is hard in basic Streamlit, but we can at least show it first or filter it
                pass

    with main_col:
        target_config = st.session_state.settings.get('targets', [{"id": 1, "name": "Target"}])
        repartition_profiles = _get_repartition_profiles()
        repartition_logics = _get_repartition_logics()

        if not filtered_kpis:
            st.info("No visible KPIs found matching your criteria.")
        else:
            for kpi in filtered_kpis:
                kpi_id = kpi['id']
                kpi_display_name = get_kpi_display_name(kpi)
                is_sub_kpi = kpi.get('master_kpi_id') is not None
                
                with st.expander(f"📊 {kpi_display_name}", expanded=True):
                    # History Context Row
                    hist1_map = st.session_state.hist1_map_for_entry.get(kpi_id, {})
                    hist2_map = st.session_state.hist2_map_for_entry.get(kpi_id, {})
                    cur_year = int(st.session_state.selected_year_target)
                    
                    st.info(f"💡 {kpi.get('description', 'No description available.')}")

                    # Render all active targets for this KPI from config
                    for t_cfg in target_config:
                        tn = t_cfg['id']
                        t_label = t_cfg['name']
                        
                        h1_val = hist1_map.get(f'annual_target{tn}', '-')
                        h2_val = hist2_map.get(f'annual_target{tn}', '-')
                        
                        cols_t = st.columns([0.4, 0.3, 0.3])
                        with cols_t[0]:
                            st.number_input(
                                f"{t_label}:",
                                key=f'target_{kpi_id}_{tn}',
                                format="%.2f",
                                disabled=(is_sub_kpi and not st.session_state.get(f'manual_{kpi_id}_{tn}', True))
                            )
                        with cols_t[1]:
                            st.caption(f"📅 **History**")
                            st.caption(f"{cur_year-1}: `{h1_val}`")
                            st.caption(f"{cur_year-2}: `{h2_val}`")
                        with cols_t[2]:
                            # Logic toggles in a small area
                            if is_sub_kpi:
                                st.checkbox("Manual", key=f'manual_{kpi_id}_{tn}', on_change=_on_manual_toggle, args=(kpi_id, tn))

                    # Distribution Settings
                    with st.container(border=True):
                        st.markdown("**⚙️ Distribution & Split Settings**")
                        
                        # Global Split Template Link
                        cur_gs_id = st.session_state.get(f'global_split_id_{kpi_id}')
                        cur_gs_name = next((name for name, sid in gs_options.items() if sid == cur_gs_id), "None (Custom)")
                        
                        selected_gs_name = st.selectbox(
                            "Standardized Split Template:",
                            gs_names,
                            index=gs_names.index(cur_gs_name) if cur_gs_name in gs_names else 0,
                            key=f"gs_select_{kpi_id}"
                        )
                        st.session_state[f'global_split_id_{kpi_id}'] = gs_options.get(selected_gs_name)
                        
                        is_using_template = selected_gs_name != "None (Custom)"
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            st.selectbox("Logic:", repartition_logics, key=f'repartition_logic_{kpi_id}', disabled=is_using_template)
                        with c2:
                            st.selectbox("Profile:", repartition_profiles, key=f'distribution_profile_{kpi_id}', disabled=is_using_template)
                        
                        if is_using_template:
                            st.caption("ℹ️ Settings are controlled by the selected template.")
                        else:
                            _render_repartition_input_area(kpi_id)


# --- Dynamic Repartition Input Area Rendering ---
def _render_repartition_input_area(kpi_id):
    repartition_logic = st.session_state.get(f'repartition_logic_{kpi_id}', REPARTITION_LOGIC_YEAR)
    distribution_profile = st.session_state.get(f'distribution_profile_{kpi_id}', PROFILE_EVEN)
    repartition_values = st.session_state.get(f'repartition_values_{kpi_id}', {})
    profile_params = st.session_state.get(f'profile_params_{kpi_id}', {})

    if repartition_logic == REPARTITION_LOGIC_MONTH:
        st.markdown("**Monthly Repartition Values (percentage of annual)**")
        cols_months = st.columns(3)
        month_names = [datetime.date(2000, m, 1).strftime('%B') for m in range(1, 13)] # English month names
        for i, month_name in enumerate(month_names):
            with cols_months[i % 3]:
                st.number_input(
                    f"{month_name}:",
                    key=f'repart_month_{kpi_id}_{i+1}',
                    value=float(repartition_values.get(month_name, 0.0)),
                    format="%.2f",
                    help="Percentage of the annual target for this month."
                )
    elif repartition_logic == REPARTITION_LOGIC_QUARTER:
        st.markdown("**Quarterly Repartition Values (percentage of annual)**")
        cols_quarters = st.columns(2)
        for i in range(1, 5):
            quarter_name = f"Q{i}"
            with cols_quarters[i % 2]:
                st.number_input(
                    f"{quarter_name}:",
                    key=f'repart_quarter_{kpi_id}_{i}',
                    value=float(repartition_values.get(quarter_name, 0.0)),
                    format="%.2f",
                    help="Percentage of the annual target for this quarter."
                )
    elif repartition_logic == REPARTITION_LOGIC_WEEK:
        st.markdown("**Weekly Repartition Values (JSON)**")
        st.text_area(
            "Weekly Weights (JSON):",
            key=f'repart_weeks_json_{kpi_id}',
            value=json.dumps(repartition_values, indent=2),
            height=150,
            help="Enter a JSON object with ISO weeks (YYYY-Www) and percentages."
        )
    
    if distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL or distribution_profile == PROFILE_MONTHLY_SINUSOIDAL:
        st.markdown("**Sinusoidal Profile Parameters**")
        cols_sine_params = st.columns(2)
        with cols_sine_params[0]:
            st.number_input(
                "Wave Amplitude:",
                key=f'profile_param_amplitude_{kpi_id}',
                value=float(profile_params.get('sine_amplitude', 0.0)),
                format="%.2f",
                help="Amplitude of the sine wave."
            )
        with cols_sine_params[1]:
            st.number_input(
                "Wave Phase:",
                key=f'profile_param_phase_{kpi_id}',
                value=float(profile_params.get('sine_phase', 0.0)),
                format="%.2f",
                help="Phase of the sine wave."
            )
    
    if distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
        st.markdown("**Weekday Bias Parameters**")
        st.number_input(
            "Weekend Bias Factor:",
            key=f'profile_param_weekday_bias_{kpi_id}',
            value=float(profile_params.get('weekday_bias_factor', 1.0)),
            format="%.2f",
            help="Multiplication factor for weekend days."
        )

    if distribution_profile == PROFILE_EVEN:
        st.info("The 'Uniform' profile does not require additional parameters.")

    if distribution_profile == PROFILE_ANNUAL_PROGRESSIVE:
        st.info("The 'Annual Progressive' profile does not require additional parameters.")

    if distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
        st.info("The 'Annual Sinusoidal' profile requires amplitude and phase parameters.")

    if distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
        st.info("The 'Annual Progressive with Weekday Bias' profile requires a bias factor.")

    if distribution_profile == PROFILE_MONTHLY_SINUSOIDAL:
        st.info("The 'Monthly Sinusoidal' profile requires amplitude and phase parameters.")

    if distribution_profile == PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE:
        st.info("The 'Intra-Period Progressive' profile requires initial and final factors.")

    if distribution_profile == PROFILE_QUARTERLY_PROGRESSIVE:
        st.info("The 'Quarterly Progressive' profile requires initial and final factors.")

    if distribution_profile == PROFILE_QUARTERLY_SINUSOIDAL:
        st.info("The 'Quarterly Sinusoidal' profile requires amplitude and phase parameters.")

    if distribution_profile == 'event_based':
        st.markdown("**Events (JSON)**")
        st.text_area(
            "Event Definitions (JSON):",
            key=f'profile_params_events_json_{kpi_id}',
            value=json.dumps(profile_params.get('events', []), indent=2),
            height=200,
            help="Enter a JSON array of event objects (e.g., [{'start_date': 'YYYY-MM-DD', 'end_date': 'YYYY-MM-DD', 'multiplier': 1.2, 'addition': 100}])."
        )