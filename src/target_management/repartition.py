# src/target_management/repartition.py
import sqlite3
import json
import datetime
import calendar
import numpy as np
import pandas as pd
import traceback
from src.config import settings as app_config

from src.data_retriever import (
    get_annual_target_entry, 
    get_kpi_detailed_by_id,
    get_daily_targets_for_kpi
)
from src.kpi_management.splits import get_global_split
from src.utils.repartition_utils import (
    get_weighted_proportions,
    get_parabolic_proportions,
    get_sinusoidal_proportions,
    get_date_ranges_for_quarters,
)
from src.interfaces.common_ui.helpers import get_kpi_display_name
from src.core.node_engine import KpiDAG

# --- Formula Evaluation Helper ---
def _evaluate_daily_formula(formula_to_use, context_vars, is_node_dag=False, kpi_resolver=None, default_tn=1):
    """Evaluates a formula for a specific day context."""
    if is_node_dag and kpi_resolver:
        dag = KpiDAG.from_json(formula_to_use)
        return dag.evaluate(kpi_resolver, default_target_num=default_tn)
    
    # Legacy string formula
    import re
    try:
        pattern = r'\[(\d+)\]'
        def replacer(match):
            kpi_id = match.group(1)
            val = context_vars.get(f"kpi_{kpi_id}", 0.0)
            return str(val)
        processed = re.sub(pattern, replacer, formula_to_use)
        allowed = {"abs": abs, "min": min, "max": max, "round": round}
        return float(eval(processed, {"__builtins__": None}, allowed))
    except:
        return 0.0

def _reconcile_and_adjust_daily_values(daily_values: np.ndarray, target_annual: float, kpi_calc_type: str):
    """Ensures sum/mean matches target_annual by distributing the difference."""
    if daily_values.size == 0: return daily_values
    
    current_val = np.sum(daily_values) if kpi_calc_type == app_config.CALC_TYPE_INCREMENTAL else np.mean(daily_values)
    diff = target_annual - current_val
    
    if abs(diff) < 1e-9: return daily_values
    
    # Split the difference across all days
    adjustment = diff / daily_values.size
    if kpi_calc_type == app_config.CALC_TYPE_INCREMENTAL:
        # For incremental, we add the adjustment so the sum matches
        daily_values += adjustment
    else:
        # For average, adding the same adjustment to every day shifts the mean by exactly that adjustment
        daily_values += adjustment
        
    return daily_values

# --- Repartition Logic and Calculation ---

def _get_period_allocations(
    annual_target: float,
    user_repartition_logic: str,
    user_repartition_values: dict,
    year: int,
    kpi_calc_type: str,
    all_dates_in_year: list,
) -> dict:
    period_allocations = {}

    if kpi_calc_type == app_config.CALC_TYPE_INCREMENTAL:
        if user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_MONTH"]:
            raw_proportions_list = [
                float(user_repartition_values.get(calendar.month_name[i + 1], 0.0) or 0.0)
                for i in range(12)
            ]
            total_user_prop_sum = sum(p for p in raw_proportions_list)
            if abs(total_user_prop_sum) < 1e-9:
                final_proportions = [1.0 / 12.0] * 12
            elif abs(total_user_prop_sum - 100.0) > 0.01:
                final_proportions = [(p / total_user_prop_sum) for p in raw_proportions_list]
            else:
                final_proportions = [p / 100.0 for p in raw_proportions_list]
            for i in range(12):
                period_allocations[i] = annual_target * final_proportions[i]

        elif user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_QUARTER"]:
            raw_proportions_list = [
                float(user_repartition_values.get(f"Q{i + 1}", 0.0) or 0.0)
                for i in range(4)
            ]
            total_user_prop_sum = sum(p for p in raw_proportions_list)
            if abs(total_user_prop_sum) < 1e-9:
                final_proportions = [1.0 / 4.0] * 4
            elif abs(total_user_prop_sum - 100.0) > 0.01:
                final_proportions = [(p / total_user_prop_sum) for p in raw_proportions_list]
            else:
                final_proportions = [p / 100.0 for p in raw_proportions_list]
            for i in range(4):
                period_allocations[i] = annual_target * final_proportions[i]

        elif user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_WEEK"]:
            sum_of_week_percentages = 0.0
            valid_week_props = {}
            for week_str, prop_val_maybe_str in user_repartition_values.items():
                try:
                    datetime.datetime.strptime(week_str + "-1", "%G-W%V-%u")
                    prop_val = float(prop_val_maybe_str or 0.0)
                    valid_week_props[week_str] = prop_val
                    sum_of_week_percentages += prop_val
                except: continue

            unique_iso_weeks = sorted(list(set(f"{d.isocalendar()[0]:04d}-W{d.isocalendar()[1]:02d}" for d in all_dates_in_year)))
            if not valid_week_props or abs(sum_of_week_percentages) < 1e-9:
                prop = 1.0 / len(unique_iso_weeks) if unique_iso_weeks else 0
                for wk in unique_iso_weeks: period_allocations[wk] = annual_target * prop
            else:
                factor = 100.0 / sum_of_week_percentages if sum_of_week_percentages != 0 else 0
                for wk, perc in valid_week_props.items():
                    period_allocations[wk] = annual_target * (perc * factor / 100.0)
                for wk in unique_iso_weeks:
                    if wk not in period_allocations: period_allocations[wk] = 0.0

    elif kpi_calc_type == app_config.CALC_TYPE_AVERAGE:
        if user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_MONTH"]:
            for i in range(12):
                period_allocations[i] = float(user_repartition_values.get(calendar.month_name[i+1], 100.0) or 100.0) / 100.0
        elif user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_QUARTER"]:
            for q in range(4):
                val = float(user_repartition_values.get(f"Q{q+1}", 100.0) or 100.0) / 100.0
                for m in range(q*3, (q+1)*3): period_allocations[m] = val
        elif user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_WEEK"]:
            unique_iso_weeks = sorted(list(set(f"{d.isocalendar()[0]:04d}-W{d.isocalendar()[1]:02d}" for d in all_dates_in_year)))
            for wk in unique_iso_weeks: period_allocations[wk] = 1.0
            for wk, mult in user_repartition_values.items():
                try: period_allocations[wk] = float(mult or 100.0) / 100.0
                except: pass
    return period_allocations


def _get_raw_daily_values_for_repartition(
    year: int,
    annual_target: float,
    kpi_calc_type: str,
    distribution_profile: str,
    profile_params: dict,
    user_repartition_logic: str,
    period_allocations_map: dict,
    all_dates_in_year: list,
) -> np.ndarray:
    days_in_year = len(all_dates_in_year)
    if days_in_year == 0: return np.array([])
    raw_daily_values = np.zeros(days_in_year)

    if kpi_calc_type == app_config.CALC_TYPE_INCREMENTAL:
        if distribution_profile == app_config.CALCULATION_CONSTANTS["PROFILE_EVEN"]:
            if user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_YEAR"] or not period_allocations_map:
                raw_daily_values.fill(annual_target / days_in_year)
            else:
                for d_idx, date_val in enumerate(all_dates_in_year):
                    if user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_MONTH"]:
                        month_sum = period_allocations_map.get(date_val.month - 1, 0.0)
                        _, days_in_month = calendar.monthrange(year, date_val.month)
                        raw_daily_values[d_idx] = month_sum / days_in_month
                    elif user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_QUARTER"]:
                        q_idx = (date_val.month - 1) // 3
                        q_sum = period_allocations_map.get(q_idx, 0.0)
                        q_ranges = get_date_ranges_for_quarters(year)
                        q_days = (q_ranges[q_idx+1][1] - q_ranges[q_idx+1][0]).days + 1
                        raw_daily_values[d_idx] = q_sum / q_days
                    elif user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_WEEK"]:
                        wk_key = f"{date_val.isocalendar()[0]:04d}-W{date_val.isocalendar()[1]:02d}"
                        wk_sum = period_allocations_map.get(wk_key, 0.0)
                        wk_days = sum(1 for d in all_dates_in_year if f"{d.isocalendar()[0]:04d}-W{d.isocalendar()[1]:02d}" == wk_key)
                        raw_daily_values[d_idx] = wk_sum / wk_days

        elif distribution_profile == app_config.CALCULATION_CONSTANTS["PROFILE_ANNUAL_PROGRESSIVE"]:
            if user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_YEAR"]:
                props = get_weighted_proportions(days_in_year, 0.8, 1.2, decreasing=True)
                raw_daily_values = np.array([annual_target * p for p in props])
            else: raw_daily_values.fill(annual_target / days_in_year)

        elif distribution_profile == app_config.CALCULATION_CONSTANTS["PROFILE_TRUE_ANNUAL_SINUSOIDAL"]:
            amp = float(profile_params.get("sine_amplitude", 0.1))
            phase = float(profile_params.get("sine_phase", 0.0))
            props = get_sinusoidal_proportions(days_in_year, amp, phase)
            raw_daily_values = np.array([annual_target * p for p in props])
        
        else: # Default
            raw_daily_values.fill(annual_target / days_in_year)

    elif kpi_calc_type == app_config.CALC_TYPE_AVERAGE:
        for d_idx, date_val in enumerate(all_dates_in_year):
            base_avg = annual_target
            if user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_MONTH"]:
                base_avg *= period_allocations_map.get(date_val.month - 1, 1.0)
            elif user_repartition_logic == app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_WEEK"]:
                wk_key = f"{date_val.isocalendar()[0]:04d}-W{date_val.isocalendar()[1]:02d}"
                base_avg *= period_allocations_map.get(wk_key, 1.0)
            
            if distribution_profile == app_config.CALCULATION_CONSTANTS["PROFILE_EVEN"]:
                raw_daily_values[d_idx] = base_avg
            elif distribution_profile == app_config.CALCULATION_CONSTANTS["PROFILE_ANNUAL_PROGRESSIVE"]:
                factor = np.linspace(0.8, 1.2, days_in_year)[d_idx]
                raw_daily_values[d_idx] = base_avg * (1 + (factor - 1.0) * 0.2)
            else:
                raw_daily_values[d_idx] = base_avg

    return raw_daily_values


def _apply_event_adjustments_to_daily_values(
    raw_daily_values_input: np.ndarray,
    event_data_list: list,
    kpi_calc_type: str,
    annual_target_for_normalization: float,
    all_dates_in_year: list,
) -> np.ndarray:
    if not event_data_list: return raw_daily_values_input
    adj = np.copy(raw_daily_values_input)
    for ev in event_data_list:
        try:
            start = datetime.datetime.strptime(ev["start_date"], "%Y-%m-%d").date()
            end = datetime.datetime.strptime(ev["end_date"], "%Y-%m-%d").date()
            mult = float(ev.get("multiplier", 1.0))
            add = float(ev.get("addition", 0.0))
            for d_idx, d_val in enumerate(all_dates_in_year):
                if start <= d_val <= end:
                    if kpi_calc_type == app_config.CALC_TYPE_AVERAGE:
                        adj[d_idx] = (adj[d_idx] * mult) + add
                    else:
                        adj[d_idx] = (adj[d_idx] * mult) + add
        except: continue
    
    if kpi_calc_type == app_config.CALC_TYPE_INCREMENTAL and abs(annual_target_for_normalization) > 1e-9:
        curr = np.sum(adj)
        if abs(curr) > 1e-9: adj *= (annual_target_for_normalization / curr)
    return adj


def _aggregate_and_save_periodic_targets(
    daily_targets_with_dates: list,
    year: int,
    plant_id: int,
    kpi_spec_id: int,
    target_number: int,
    kpi_calc_type: str,
):
    if not daily_targets_with_dates: return

    # --- Save Daily ---
    recs = [(year, plant_id, kpi_spec_id, target_number, d.isoformat(), float(v)) for d, v in daily_targets_with_dates]
    with sqlite3.connect(app_config.get_database_path("db_kpi_days.db")) as conn:
        conn.execute("DELETE FROM daily_targets WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=?", (year, plant_id, kpi_spec_id, target_number))
        conn.executemany("INSERT INTO daily_targets (year,plant_id,kpi_id,target_number,date_value,target_value) VALUES (?,?,?,?,?,?)", recs)
        conn.commit()

    # --- Aggregate Weekly ---
    weeks = {}
    for d, v in daily_targets_with_dates:
        wk = f"{d.isocalendar()[0]:04d}-W{d.isocalendar()[1]:02d}"
        if wk not in weeks: weeks[wk] = []
        weeks[wk].append(v)
    
    w_recs = []
    for wk, vals in weeks.items():
        val = sum(vals) if kpi_calc_type == app_config.CALC_TYPE_INCREMENTAL else np.mean(vals)
        w_recs.append((year, plant_id, kpi_spec_id, target_number, wk, float(val)))
    
    with sqlite3.connect(app_config.get_database_path("db_kpi_weeks.db")) as conn:
        conn.execute("DELETE FROM weekly_targets WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=?", (year, plant_id, kpi_spec_id, target_number))
        conn.executemany("INSERT INTO weekly_targets (year,plant_id,kpi_id,target_number,week_value,target_value) VALUES (?,?,?,?,?,?)", w_recs)
        conn.commit()

    # --- Aggregate Monthly ---
    months = {i: [] for i in range(1, 13)}
    for d, v in daily_targets_with_dates: months[d.month].append(v)
    
    m_recs = []
    for m, vals in months.items():
        if not vals: continue
        val = sum(vals) if kpi_calc_type == app_config.CALC_TYPE_INCREMENTAL else np.mean(vals)
        m_recs.append((year, plant_id, kpi_spec_id, target_number, calendar.month_name[m], float(val)))
    
    with sqlite3.connect(app_config.get_database_path("db_kpi_months.db")) as conn:
        conn.execute("DELETE FROM monthly_targets WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=?", (year, plant_id, kpi_spec_id, target_number))
        conn.executemany("INSERT INTO monthly_targets (year,plant_id,kpi_id,target_number,month_value,target_value) VALUES (?,?,?,?,?,?)", m_recs)
        conn.commit()

    # --- Aggregate Quarterly ---
    quarters = {1: [], 2: [], 3: [], 4: []}
    for d, v in daily_targets_with_dates: quarters[((d.month-1)//3)+1].append(v)
    
    q_recs = []
    for q, vals in quarters.items():
        if not vals: continue
        val = sum(vals) if kpi_calc_type == app_config.CALC_TYPE_INCREMENTAL else np.mean(vals)
        q_recs.append((year, plant_id, kpi_spec_id, target_number, f"Q{q}", float(val)))
    
    with sqlite3.connect(app_config.get_database_path("db_kpi_quarters.db")) as conn:
        conn.execute("DELETE FROM quarterly_targets WHERE year=? AND plant_id=? AND kpi_id=? AND target_number=?", (year, plant_id, kpi_spec_id, target_number))
        conn.executemany("INSERT INTO quarterly_targets (year,plant_id,kpi_id,target_number,quarter_value,target_value) VALUES (?,?,?,?,?,?)", q_recs)
        conn.commit()


def calculate_and_save_all_repartitions(year: int, plant_id: int, kpi_spec_id: int, target_number: int):
    """Orchestrates periodic repartition with support for On-the-fly formula logic."""
    target_info = get_annual_target_entry(year, plant_id, kpi_spec_id)
    if not target_info: return

    kpi_details = dict(get_kpi_detailed_by_id(kpi_spec_id) or {})
    kpi_calc_type = kpi_details.get("calculation_type", app_config.CALC_TYPE_INCREMENTAL)
    
    t_val_rec = next((tv for tv in target_info.get('target_values', []) if tv['target_number'] == target_number), None)
    annual_target_to_use = float(t_val_rec['target_value']) if t_val_rec and t_val_rec['target_value'] is not None else None
    
    if annual_target_to_use is None: return

    # --- Date Generation ---
    start_of_year = datetime.date(year, 1, 1)
    all_dates = [start_of_year + datetime.timedelta(days=i) for i in range((datetime.date(year, 12, 31) - start_of_year).days + 1)]

    final_daily_values = None
    
    # --- ON-THE-FLY FORMULA LOGIC ---
    formula_json = kpi_details.get("formula_json")
    formula_str = kpi_details.get("formula_string")
    is_formula = t_val_rec.get('is_formula_based', False)
    
    if is_formula and (formula_json or formula_str):
        print(f"    INFO: Calculating on-the-fly periodic values for KPI {kpi_spec_id}...")
        is_dag = False
        try:
            if formula_json:
                dj = json.loads(formula_json)
                if "nodes" in dj: is_dag = True
        except: pass
        
        dag = KpiDAG.from_json(formula_json) if is_dag else None
        deps = dag.find_all_kpi_dependencies() if is_dag else []
        
        if not is_dag and formula_str:
            import re
            dep_ids = list(set(re.findall(r'\[(\d+)\]', formula_str)))
            deps = [{"kpi_id": int(i), "target_num": target_number} for i in dep_ids]

        dep_daily_data = {}
        for d in deps:
            rows = get_daily_targets_for_kpi(year, plant_id, d['kpi_id'], d['target_num'])
            arr = np.zeros(len(all_dates))
            date_map = {r['date_value']: r['target_value'] for r in rows}
            for idx, dt in enumerate(all_dates):
                arr[idx] = date_map.get(dt.isoformat(), 0.0)
            dep_daily_data[d['kpi_id']] = arr

        calculated_days = np.zeros(len(all_dates))
        for idx in range(len(all_dates)):
            if is_dag:
                def daily_resolver(kid, tn):
                    return dep_daily_data.get(kid, np.zeros(len(all_dates)))[idx]
                calculated_days[idx] = dag.evaluate(daily_resolver, default_target_num=target_number)
            else:
                ctx = {f"kpi_{kid}": arr[idx] for kid, arr in dep_daily_data.items()}
                calculated_days[idx] = _evaluate_daily_formula(formula_str, ctx)
        
        final_daily_values = _reconcile_and_adjust_daily_values(calculated_days, annual_target_to_use, kpi_calc_type)

    # --- FALLBACK: RULE-BASED SPLIT ---
    if final_daily_values is None:
        global_split_id = target_info.get("global_split_id")
        gs = get_global_split(global_split_id) if global_split_id else None
        
        if gs:
            logic, profile, vals, params = gs['repartition_logic'], gs['distribution_profile'], gs['repartition_values'], gs['profile_params']
            
            # Check for per-indicator profile override within this global split
            try:
                from src.kpi_management.splits import get_indicators_for_global_split
                afflicted = get_indicators_for_global_split(global_split_id)
                ind_id = kpi_details.get('indicator_id')
                override = next((a for a in afflicted if a['indicator_id'] == ind_id), None)
                if override and override.get('override_distribution_profile'):
                    profile = override['override_distribution_profile']
                    print(f"      INFO: Using override profile '{profile}' for KPI {kpi_spec_id} in Global Split {global_split_id}")
            except Exception as e_gs:
                print(f"      WARNING: Could not check for Global Split override: {e_gs}")
        else:
            REPARTITION_LOGIC_YEAR = app_config.CALCULATION_CONSTANTS["REPARTITION_LOGIC_YEAR"]
            PROFILE_ANNUAL_PROGRESSIVE = app_config.CALCULATION_CONSTANTS["PROFILE_ANNUAL_PROGRESSIVE"]
            
            logic = target_info.get("repartition_logic", REPARTITION_LOGIC_YEAR)
            profile = target_info.get("distribution_profile") or kpi_details.get("default_distribution_profile") or PROFILE_ANNUAL_PROGRESSIVE
            vals = json.loads(target_info.get("repartition_values", "{}") or "{}")
            params = json.loads(target_info.get("profile_params", "{}") or "{}")

        allocs = _get_period_allocations(annual_target_to_use, logic, vals, year, kpi_calc_type, all_dates)
        raw_days = _get_raw_daily_values_for_repartition(year, annual_target_to_use, kpi_calc_type, profile, params, logic, allocs, all_dates)
        
        events = params.get("events", [])
        final_daily_values = _apply_event_adjustments_to_daily_values(raw_days, events, kpi_calc_type, annual_target_to_use, all_dates)
        final_daily_values = _reconcile_and_adjust_daily_values(final_daily_values, annual_target_to_use, kpi_calc_type)

    # --- Save ---
    _aggregate_and_save_periodic_targets(list(zip(all_dates, final_daily_values)), year, plant_id, kpi_spec_id, target_number, kpi_calc_type)
