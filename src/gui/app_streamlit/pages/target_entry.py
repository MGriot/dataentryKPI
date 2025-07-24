import streamlit as st
import datetime
import json

from target_management import annual as annual_targets_manager
import data_retriever as db_retriever
from gui.shared.helpers import get_kpi_display_name
from gui.shared.constants (
    REPARTITION_LOGIC_ANNO,
    REPARTITION_LOGIC_MESE,
    REPARTITION_LOGIC_TRIMESTRE,
    REPARTITION_LOGIC_SETTIMANA,
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
def _get_target_display_names():
    # Access settings from session_state
    settings = st.session_state.settings
    return settings.get('display_names', {}).get('target1', 'Target 1'), \
           settings.get('display_names', {}).get('target2', 'Target 2')

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
        REPARTITION_LOGIC_ANNO,
        REPARTITION_LOGIC_MESE,
        REPARTITION_LOGIC_TRIMESTRE,
        REPARTITION_LOGIC_SETTIMANA,
    ]

def load_kpi_targets_for_entry_target():
    if not st.session_state.selected_year_target or not st.session_state.selected_stabilimento_name_target:
        st.session_state.kpis_for_entry = []
        st.session_state.targets_map_for_entry = {}
        return

    year = int(st.session_state.selected_year_target)
    stabilimento_id = st.session_state.stabilimenti_map_target.get(st.session_state.selected_stabilimento_name_target)

    if stabilimento_id is None:
        st.error("ID Stabilimento non trovato.")
        st.session_state.kpis_for_entry = []
        st.session_state.targets_map_for_entry = {}
        return

    st.session_state.kpis_for_entry = [dict(row) for row in db_retriever.get_all_kpis_detailed(only_visible=True)]
    targets = [dict(row) for row in db_retriever.get_annual_targets(stabilimento_id, year)]
    st.session_state.targets_map_for_entry = {t['kpi_id']: t for t in targets}

    # Initialize input values in session state for each KPI
    for kpi in st.session_state.kpis_for_entry:
        kpi_id = kpi['id']
        target_data = st.session_state.targets_map_for_entry.get(kpi_id, {})
        
        # Target 1 & 2 values
        st.session_state[f'target_{kpi_id}_1'] = target_data.get('annual_target1')
        st.session_state[f'target_{kpi_id}_2'] = target_data.get('annual_target2')

        # Manual flags
        st.session_state[f'manual_{kpi_id}_1'] = bool(target_data.get('is_target1_manual', True))
        st.session_state[f'manual_{kpi_id}_2'] = bool(target_data.get('is_target2_manual', True))

        # Formula flags and strings
        st.session_state[f'formula_based_{kpi_id}_1'] = bool(target_data.get('target1_is_formula_based', False))
        st.session_state[f'formula_str_{kpi_id}_1'] = target_data.get('target1_formula', '')
        st.session_state[f'formula_inputs_{kpi_id}_1'] = json.loads(target_data.get('target1_formula_inputs', '[]') or '[]')

        st.session_state[f'formula_based_{kpi_id}_2'] = bool(target_data.get('target2_is_formula_based', False))
        st.session_state[f'formula_str_{kpi_id}_2'] = target_data.get('target2_formula', '')
        st.session_state[f'formula_inputs_{kpi_id}_2'] = json.loads(target_data.get('target2_formula_inputs', '[]') or '[]')

        # Repartition profile and values
        st.session_state[f'distribution_profile_{kpi_id}'] = target_data.get('distribution_profile', PROFILE_EVEN)
        st.session_state[f'repartition_logic_{kpi_id}'] = target_data.get('repartition_logic', REPARTITION_LOGIC_ANNO)
        st.session_state[f'repartition_values_{kpi_id}'] = json.loads(target_data.get('repartition_values', '{}') or '{}')
        st.session_state[f'profile_params_{kpi_id}'] = json.loads(target_data.get('profile_params', '{}') or '{}')

def save_all_targets_entry():
    year_str = st.session_state.selected_year_target
    stabilimento_name = st.session_state.selected_stabilimento_name_target

    if not year_str or not stabilimento_name:
        st.error("Anno e stabilimento devono essere selezionati.")
        return

    year = int(year_str)
    stabilimento_id = st.session_state.stabilimenti_map_target.get(stabilimento_name)

    targets_data_map = {}
    for kpi in st.session_state.kpis_for_entry:
        kpi_id = kpi['id']
        try:
            t1_val = st.session_state.get(f'target_{kpi_id}_1')
            t2_val = st.session_state.get(f'target_{kpi_id}_2')

            # Convert empty strings to None, attempt float conversion
            t1_val = float(t1_val) if t1_val is not None and str(t1_val).strip() != '' else None
            t2_val = float(t2_val) if t2_val is not None and str(t2_val).strip() != '' else None

        except ValueError:
            st.error(f"Valore non valido per KPI {get_kpi_display_name(kpi)}. Inserire un numero.")
            return

        # Get states from session_state
        is_target1_manual = st.session_state.get(f'manual_{kpi_id}_1', True)
        is_target2_manual = st.session_state.get(f'manual_{kpi_id}_2', True)
        target1_is_formula_based = st.session_state.get(f'formula_based_{kpi_id}_1', False)
        target2_is_formula_based = st.session_state.get(f'formula_based_{kpi_id}_2', False)
        target1_formula = st.session_state.get(f'formula_str_{kpi_id}_1', '')
        target2_formula = st.session_state.get(f'formula_str_{kpi_id}_2', '')
        target1_formula_inputs = st.session_state.get(f'formula_inputs_{kpi_id}_1', [])
        target2_formula_inputs = st.session_state.get(f'formula_inputs_{kpi_id}_2', [])
        distribution_profile = st.session_state.get(f'distribution_profile_{kpi_id}', PROFILE_EVEN)
        repartition_logic = st.session_state.get(f'repartition_logic_{kpi_id}', REPARTITION_LOGIC_ANNO)
        repartition_values = st.session_state.get(f'repartition_values_{kpi_id}', {})
        profile_params = st.session_state.get(f'profile_params_{kpi_id}', {})

        targets_data = {
            'annual_target1': t1_val,
            'annual_target2': t2_val,
            'is_target1_manual': is_target1_manual,
            'is_target2_manual': is_target2_manual,
            'target1_is_formula_based': target1_is_formula_based,
            'target2_is_formula_based': target2_is_formula_based,
            'target1_formula': target1_formula,
            'target2_formula': target2_formula,
            'target1_formula_inputs': json.dumps(target1_formula_inputs),
            'target2_formula_inputs': json.dumps(target2_formula_inputs),
            'distribution_profile': distribution_profile,
            'repartition_logic': repartition_logic,
            'repartition_values': json.dumps(repartition_values),
            'profile_params': json.dumps(profile_params)
        }
        targets_data_map[str(kpi_id)] = targets_data

    try:
        annual_targets_manager.save_annual_targets(
            year=year,
            stabilimento_id=stabilimento_id,
            targets_data_map=targets_data_map
        )
        st.success("Tutti i target sono stati salvati.")
        load_kpi_targets_for_entry_target() # Reload data to show updated state
    except Exception as e:
        st.error(f"Errore nel salvataggio dei target: {e}")
        st.exception(e)

# --- Callbacks for dynamic behavior ---
def _on_manual_toggle(kpi_id, target_num):
    # If manual is checked, uncheck formula and disable formula inputs
    if st.session_state[f'manual_{kpi_id}_{target_num}']:
        st.session_state[f'formula_based_{kpi_id}_{target_num}'] = False

def _on_formula_toggle(kpi_id, target_num):
    # If formula is checked, uncheck manual
    if st.session_state[f'formula_based_{kpi_id}_{target_num}']:
        st.session_state[f'manual_{kpi_id}_{target_num}'] = False

def _update_repartition_input_area_streamlit(kpi_id):
    # This function will be called on profile/logic change to re-render the dynamic inputs
    pass # Logic will be implemented directly in the main app() function

def app():
    st.title("🎯 Inserimento Target")

    # Initialize session state variables if they don't exist
    if 'selected_year_target' not in st.session_state:
        st.session_state.selected_year_target = str(datetime.datetime.now().year)
    if 'selected_stabilimento_name_target' not in st.session_state:
        st.session_state.selected_stabilimento_name_target = None
    if 'stabilimenti_map_target' not in st.session_state:
        st.session_state.stabilimenti_map_target = {}
    if 'kpis_for_entry' not in st.session_state:
        st.session_state.kpis_for_entry = []
    if 'targets_map_for_entry' not in st.session_state:
        st.session_state.targets_map_for_entry = {}

    # --- Filters ---
    col1, col2 = st.columns([1, 2])

    with col1:
        current_year = datetime.datetime.now().year
        years = [str(y) for y in range(current_year - 5, current_year + 5)]
        st.session_state.selected_year_target = st.selectbox(
            "Anno:",
            years,
            index=years.index(st.session_state.selected_year_target) if st.session_state.selected_year_target in years else 0,
            key="year_select_target",
            on_change=load_kpi_targets_for_entry_target # Trigger data load on change
        )

    with col2:
        stabilimenti_all = db_retriever.get_all_stabilimenti(visible_only=True)
        st.session_state.stabilimenti_map_target = {s['name']: s['id'] for s in stabilimenti_all}
        stabilimento_names = list(st.session_state.stabilimenti_map_target.keys())

        if not stabilimento_names:
            st.warning("Nessuno stabilimento disponibile. Si prega di configurare gli stabilimenti nella sezione 'Gestione Stabilimenti'.")
            st.session_state.selected_stabilimento_name_target = None
        else:
            if st.session_state.selected_stabilimento_name_target not in stabilimento_names:
                st.session_state.selected_stabilimento_name_target = stabilimento_names[0]
            
            st.session_state.selected_stabilimento_name_target = st.selectbox(
                "Stabilimento:",
                stabilimento_names,
                index=stabilimento_names.index(st.session_state.selected_stabilimento_name_target),
                key="stabilimento_select_target",
                on_change=load_kpi_targets_for_entry_target # Trigger data load on change
            )

    # Initial load of data when page loads or filters change
    if st.session_state.selected_stabilimento_name_target is not None and not st.session_state.kpis_for_entry:
        load_kpi_targets_for_entry_target()

    # --- KPI Input Boxes ---
    st.markdown("### Inserimento Target KPI")
    target1_display_name, target2_display_name = _get_target_display_names()
    repartition_profiles = _get_repartition_profiles()
    repartition_logics = _get_repartition_logics()

    if not st.session_state.kpis_for_entry:
        st.info("Nessun KPI visibile trovato per l'inserimento target.")
    else:
        for kpi in st.session_state.kpis_for_entry:
            kpi_id = kpi['id']
            kpi_display_name = get_kpi_display_name(kpi)
            is_sub_kpi = kpi.get('master_kpi_id') is not None
            
            with st.container(border=True):
                st.markdown(f"**{kpi_display_name}**")
                
                # Target 1 & 2 Inputs
                cols_target_input = st.columns([0.3, 0.1, 0.3, 0.3]) # Value, Manual, Formula, Formula String
                
                # Target 1
                with cols_target_input[0]:
                    st.number_input(
                        f"{target1_display_name}:",
                        key=f'target_{kpi_id}_1',
                        value=st.session_state.get(f'target_{kpi_id}_1'),
                        format="%.2f",
                        help=f"Inserisci il valore per {target1_display_name}",
                        disabled=st.session_state.get(f'formula_based_{kpi_id}_1', False) or (is_sub_kpi and not st.session_state.get(f'manual_{kpi_id}_1', True))
                    )
                with cols_target_input[1]:
                    if is_sub_kpi:
                        st.checkbox(
                            "Man.",
                            key=f'manual_{kpi_id}_1',
                            value=st.session_state.get(f'manual_{kpi_id}_1', True),
                            on_change=_on_manual_toggle, args=(kpi_id, 1),
                            help="Seleziona per inserire manualmente il target per questo sub-KPI."
                        )
                with cols_target_input[2]:
                    st.checkbox(
                        "Usa Formula",
                        key=f'formula_based_{kpi_id}_1',
                        value=st.session_state.get(f'formula_based_{kpi_id}_1', False),
                        on_change=_on_formula_toggle, args=(kpi_id, 1),
                        help="Seleziona per calcolare il target tramite formula."
                    )
                with cols_target_input[3]:
                    st.text_input(
                        "Formula T1:",
                        key=f'formula_str_{kpi_id}_1',
                        value=st.session_state.get(f'formula_str_{kpi_id}_1', ''),
                        disabled=not st.session_state.get(f'formula_based_{kpi_id}_1', False),
                        help="Inserisci la formula per il calcolo del Target 1."
                    )
                    # Formula Inputs button - for now, just a placeholder or direct JSON input
                    # st.button("Input...", key=f'formula_btn_{kpi_id}_1', disabled=not st.session_state.get(f'formula_based_{kpi_id}_1', False))

                # Target 2 (similar structure)
                cols_target_input_2 = st.columns([0.3, 0.1, 0.3, 0.3])
                with cols_target_input_2[0]:
                    st.number_input(
                        f"{target2_display_name}:",
                        key=f'target_{kpi_id}_2',
                        value=st.session_state.get(f'target_{kpi_id}_2'),
                        format="%.2f",
                        help=f"Inserisci il valore per {target2_display_name}",
                        disabled=st.session_state.get(f'formula_based_{kpi_id}_2', False) or (is_sub_kpi and not st.session_state.get(f'manual_{kpi_id}_2', True))
                    )
                with cols_target_input_2[1]:
                    if is_sub_kpi:
                        st.checkbox(
                            "Man.",
                            key=f'manual_{kpi_id}_2',
                            value=st.session_state.get(f'manual_{kpi_id}_2', True),
                            on_change=_on_manual_toggle, args=(kpi_id, 2),
                            help="Seleziona per inserire manualmente il target per questo sub-KPI."
                        )
                with cols_target_input_2[2]:
                    st.checkbox(
                        "Usa Formula",
                        key=f'formula_based_{kpi_id}_2',
                        value=st.session_state.get(f'formula_based_{kpi_id}_2', False),
                        on_change=_on_formula_toggle, args=(kpi_id, 2),
                        help="Seleziona per calcolare il target tramite formula."
                    )
                with cols_target_input_2[3]:
                    st.text_input(
                        "Formula T2:",
                        key=f'formula_str_{kpi_id}_2',
                        value=st.session_state.get(f'formula_str_{kpi_id}_2', ''),
                        disabled=not st.session_state.get(f'formula_based_{kpi_id}_2', False),
                        help="Inserisci la formula per il calcolo del Target 2."
                    )
                    # st.button("Input...", key=f'formula_btn_{kpi_id}_2', disabled=not st.session_state.get(f'formula_based_{kpi_id}_2', False))

                # Repartition Profile
                st.markdown("**Profilo di Distribuzione**")
                cols_repart = st.columns([0.5, 0.5])
                with cols_repart[0]:
                    st.selectbox(
                        "Logica di Riparto:",
                        repartition_logics,
                        key=f'repartition_logic_{kpi_id}',
                        index=repartition_logics.index(st.session_state.get(f'repartition_logic_{kpi_id}', REPARTITION_LOGIC_ANNO)),
                        on_change=_update_repartition_input_area_streamlit, args=(kpi_id,),
                        help="Seleziona la logica di riparto annuale (es. per mese, trimestre)."
                    )
                with cols_repart[1]:
                    st.selectbox(
                        "Profilo di Distribuzione:",
                        repartition_profiles,
                        key=f'distribution_profile_{kpi_id}',
                        index=repartition_profiles.index(st.session_state.get(f'distribution_profile_{kpi_id}', PROFILE_EVEN)),
                        on_change=_update_repartition_input_area_streamlit, args=(kpi_id,),
                        help="Seleziona il profilo di distribuzione dei target."
                    )

                # Dynamic Repartition Input Area
                _render_repartition_input_area(kpi_id)

    # --- Save Button ---
    st.button("SALVA TUTTI I TARGET", key="save_all_targets_button", on_click=save_all_targets_entry)


# --- Dynamic Repartition Input Area Rendering ---
def _render_repartition_input_area(kpi_id):
    repartition_logic = st.session_state.get(f'repartition_logic_{kpi_id}', REPARTITION_LOGIC_ANNO)
    distribution_profile = st.session_state.get(f'distribution_profile_{kpi_id}', PROFILE_EVEN)
    repartition_values = st.session_state.get(f'repartition_values_{kpi_id}', {})
    profile_params = st.session_state.get(f'profile_params_{kpi_id}', {})

    if repartition_logic == REPARTITION_LOGIC_MESE:
        st.markdown("**Valori di Riparto Mensili (percentuale dell'annuale)**")
        cols_months = st.columns(3)
        month_names = [datetime.date(2000, m, 1).strftime('%B') for m in range(1, 13)] # English month names
        for i, month_name in enumerate(month_names):
            with cols_months[i % 3]:
                st.number_input(
                    f"{month_name}:",
                    key=f'repart_month_{kpi_id}_{i+1}',
                    value=float(repartition_values.get(month_name, 0.0)),
                    format="%.2f",
                    help="Percentuale del target annuale per questo mese."
                )
    elif repartition_logic == REPARTITION_LOGIC_TRIMESTRE:
        st.markdown("**Valori di Riparto Trimestrali (percentuale dell'annuale)**")
        cols_quarters = st.columns(2)
        for i in range(1, 5):
            quarter_name = f"Q{i}"
            with cols_quarters[i % 2]:
                st.number_input(
                    f"{quarter_name}:",
                    key=f'repart_quarter_{kpi_id}_{i}',
                    value=float(repartition_values.get(quarter_name, 0.0)),
                    format="%.2f",
                    help="Percentuale del target annuale per questo trimestre."
                )
    elif repartition_logic == REPARTITION_LOGIC_SETTIMANA:
        st.markdown("**Valori di Riparto Settimanali (JSON)**")
        st.text_area(
            "Pesi Settimanali (JSON):",
            key=f'repart_weeks_json_{kpi_id}',
            value=json.dumps(repartition_values, indent=2),
            height=150,
            help="Inserisci un oggetto JSON con le settimane ISO (YYYY-Www) e le percentuali."
        )
    
    if distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL or distribution_profile == PROFILE_MONTHLY_SINUSOIDAL:
        st.markdown("**Parametri Profilo Sinusoidale**")
        cols_sine_params = st.columns(2)
        with cols_sine_params[0]:
            st.number_input(
                "Ampiezza Onda:",
                key=f'profile_param_amplitude_{kpi_id}',
                value=float(profile_params.get('sine_amplitude', 0.0)),
                format="%.2f",
                help="Ampiezza dell'onda sinusoidale."
            )
        with cols_sine_params[1]:
            st.number_input(
                "Fase Onda:",
                key=f'profile_param_phase_{kpi_id}',
                value=float(profile_params.get('sine_phase', 0.0)),
                format="%.2f",
                help="Fase dell'onda sinusoidale."
            )
    
    if distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
        st.markdown("**Parametri Bias Giorni Settimana**")
        st.number_input(
            "Fattore Bias Weekend:",
            key=f'profile_param_weekday_bias_{kpi_id}',
            value=float(profile_params.get('weekday_bias_factor', 1.0)),
            format="%.2f",
            help="Fattore moltiplicativo per i giorni del fine settimana."
        )

    if distribution_profile == PROFILE_EVEN:
        st.info("Il profilo 'Uniforme' non richiede parametri aggiuntivi.")

    if distribution_profile == PROFILE_ANNUAL_PROGRESSIVE:
        st.info("Il profilo 'Progressivo Annuale' non richiede parametri aggiuntivi.")

    if distribution_profile == PROFILE_TRUE_ANNUAL_SINUSOIDAL:
        st.info("Il profilo 'Sinusoidale Annuale' richiede parametri di ampiezza e fase.")

    if distribution_profile == PROFILE_ANNUAL_PROGRESSIVE_WEEKDAY_BIAS:
        st.info("Il profilo 'Progressivo Annuale con Bias Giorni Settimana' richiede un fattore di bias.")

    if distribution_profile == PROFILE_MONTHLY_SINUSOIDAL:
        st.info("Il profilo 'Sinusoidale Mensile' richiede parametri di ampiezza e fase.")

    if distribution_profile == PROFILE_LEGACY_INTRA_PERIOD_PROGRESSIVE:
        st.info("Il profilo 'Progressivo Intra-Periodo' richiede fattori iniziale e finale.")

    if distribution_profile == PROFILE_QUARTERLY_PROGRESSIVE:
        st.info("Il profilo 'Progressivo Trimestrale' richiede fattori iniziale e finale.")

    if distribution_profile == PROFILE_QUARTERLY_SINUSOIDAL:
        st.info("Il profilo 'Sinusoidale Trimestrale' richiede parametri di ampiezza e fase.")

    if distribution_profile == 'event_based':
        st.markdown("**Eventi (JSON)**")
        st.text_area(
            "Definizione Eventi (JSON):",
            key=f'profile_params_events_json_{kpi_id}',
            value=json.dumps(profile_params.get('events', []), indent=2),
            height=200,
            help="Inserisci un array JSON di oggetti evento (es. [{'start_date': 'YYYY-MM-DD', 'end_date': 'YYYY-MM-DD', 'multiplier': 1.2, 'addition': 100}])."
        )


