# your_project_root/target_management/annual.py
import sqlite3
import json
import traceback
import numpy # For _placeholder_safe_evaluate_formula if it uses numpy functions directly
from src.config import settings as app_config
from pathlib import Path
from src import data_retriever as db_retriever
from src.data_retriever import get_annual_target_entry, get_kpi_role_details, get_sub_kpis_for_master


# Configuration imports
from src.interfaces.common_ui.constants import (
    REPARTITION_LOGIC_YEAR,
    PROFILE_ANNUAL_PROGRESSIVE,
)

from src.target_management import repartition as repartition_module
from src.core.node_engine import KpiDAG


# --- Formula Evaluation (Placeholder - Needs Secure Implementation) ---
def _placeholder_safe_evaluate_formula(formula_str: str, context_vars: dict):
    """
    Evaluates a formula string. Supports [ID] syntax which is mapped to context_vars['kpi_ID'].
    """
    import re
    # print(f"DEBUG: Formula='{formula_str}', Context={context_vars}")
    try:
        # Replace [ID] with context_vars['kpi_ID']
        # e.g., [101] -> context_vars.get('kpi_101', 0.0)
        pattern = r'\[(\d+)\]'
        
        def replacer(match):
            kpi_id = match.group(1)
            var_name = f"kpi_{kpi_id}"
            val = context_vars.get(var_name, 0.0)
            return str(val)
            
        processed_formula = re.sub(pattern, replacer, formula_str)
        
        # Safe eval using a restricted context
        allowed_names = {"abs": abs, "min": min, "max": max, "round": round}
        # Add any remaining context vars that weren't [ID] based
        allowed_names.update({k: v for k, v in context_vars.items() if not k.startswith("kpi_")})
        
        return float(eval(processed_formula, {"__builtins__": None}, allowed_names))
    except Exception as e:
        print(f"ERROR: Formula evaluation failed: {e}")
        return 0.0


# --- Annual Target Management ---
def save_annual_targets(
    year: int,
    plant_id: int | list[int],
    targets_data_map: dict,
    initiator_kpi_spec_id: int = None,
):
    """
    Saves annual targets for one or more plants.
    """
    db_targets_path = app_config.get_database_path("db_kpi_targets.db")
    db_kpis_path = app_config.get_database_path("db_kpis.db")

    if not targets_data_map: return

    plant_ids = [plant_id] if isinstance(plant_id, int) else plant_id
    
    for pid in plant_ids:
        print(f"INFO: Saving annual targets for Year: {year}, Plant: {pid}...")
        _save_single_plant_annual_targets(year, pid, targets_data_map, initiator_kpi_spec_id)

def _save_single_plant_annual_targets(year, plant_id, targets_data_map, initiator_kpi_spec_id):
    db_targets_path = app_config.get_database_path("db_kpi_targets.db")
    
    kpis_needing_repartition_update = set()
    # Map of target_number -> list of kpi_ids
    kpis_with_formula = {} 

    # Phase 1: Save definitions
    with sqlite3.connect(db_targets_path) as conn:
        cursor = conn.cursor()
        for kpi_spec_id_str, data_dict_from_ui in targets_data_map.items():
            try:
                current_kpi_spec_id = int(kpi_spec_id_str)
            except: continue

            record_row = get_annual_target_entry(year, plant_id, current_kpi_spec_id)
            # record_row is enriched, so it contains 'target_values' and legacy fields
            record_dict = record_row if record_row else None

            # 1a. Update/Insert annual_targets (metadata)
            if record_dict:
                at_id = record_dict['id']
                # Update repartition settings if provided
                if "repartition_logic" in data_dict_from_ui:
                    cursor.execute(
                        "UPDATE annual_targets SET repartition_logic=?, repartition_values=?, distribution_profile=?, profile_params=?, global_split_id=? WHERE id=?",
                        (data_dict_from_ui.get("repartition_logic"),
                         data_dict_from_ui.get("repartition_values", "{}"),
                         data_dict_from_ui.get("distribution_profile"),
                         data_dict_from_ui.get("profile_params", "{}"),
                         data_dict_from_ui.get("global_split_id"),
                         at_id)
                    )
            else:
                cursor.execute(
                    "INSERT INTO annual_targets (year, plant_id, kpi_id, repartition_logic, repartition_values, distribution_profile, profile_params, global_split_id) VALUES (?,?,?,?,?,?,?,?)",
                    (year, plant_id, current_kpi_spec_id, 
                     data_dict_from_ui.get("repartition_logic", REPARTITION_LOGIC_YEAR),
                     data_dict_from_ui.get("repartition_values", "{}"),
                     data_dict_from_ui.get("distribution_profile", PROFILE_ANNUAL_PROGRESSIVE),
                     data_dict_from_ui.get("profile_params", "{}"),
                     data_dict_from_ui.get("global_split_id"))
                )
                at_id = cursor.lastrowid

            # 1b. Save target values
            # The UI might send 'targets': [{'target_number': 1, 'target_value': 100, ...}, ...]
            # or it might send legacy 'annual_target1', etc.
            targets_to_process = data_dict_from_ui.get('targets')
            if not targets_to_process:
                # Map legacy fields to target list
                targets_to_process = []
                for tn in [1, 2]:
                    if f'annual_target{tn}' in data_dict_from_ui or f'target{tn}_is_formula_based' in data_dict_from_ui:
                        targets_to_process.append({
                            'target_number': tn,
                            'target_value': data_dict_from_ui.get(f'annual_target{tn}'),
                            'is_manual': data_dict_from_ui.get(f'is_target{tn}_manual', True),
                            'is_formula_based': data_dict_from_ui.get(f'target{tn}_is_formula_based', False),
                            'formula': data_dict_from_ui.get(f'target{tn}_formula'),
                            'formula_inputs': data_dict_from_ui.get(f'target{tn}_formula_inputs', '[]')
                        })

            for t_data in targets_to_process:
                tn = t_data['target_number']
                t_val_raw = t_data.get('target_value', 0.0)
                t_val = float(t_val_raw) if t_val_raw is not None else 0.0
                is_man = 1 if t_data.get('is_manual', True) else 0
                is_form = 1 if t_data.get('is_formula_based', False) else 0
                form_str = t_data.get('formula')
                form_in_raw = t_data.get('formula_inputs', '[]')
                form_in = json.dumps(form_in_raw) if isinstance(form_in_raw, (list, dict)) else (form_in_raw or '[]')

                cursor.execute("""
                    INSERT INTO kpi_annual_target_values 
                    (annual_target_id, target_number, target_value, is_manual, is_formula_based, formula, formula_inputs)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(annual_target_id, target_number) DO UPDATE SET
                    target_value=excluded.target_value,
                    is_manual=excluded.is_manual,
                    is_formula_based=excluded.is_formula_based,
                    formula=excluded.formula,
                    formula_inputs=excluded.formula_inputs
                """, (at_id, tn, t_val, is_man, is_form, form_str, form_in))

                # Also update legacy columns for backward compatibility
                if tn in [1, 2]:
                    cursor.execute(f"UPDATE annual_targets SET annual_target{tn}=?, is_target{tn}_manual=?, target{tn}_is_formula_based=?, target{tn}_formula=?, target{tn}_formula_inputs=? WHERE id=?",
                                   (t_val, is_man, is_form, form_str, form_in, at_id))

                kpis_needing_repartition_update.add(current_kpi_spec_id)
                if is_form:
                    if tn not in kpis_with_formula: kpis_with_formula[tn] = []
                    kpis_with_formula[tn].append(current_kpi_spec_id)

        conn.commit()

    # Phase 2: Calculate formula-based targets
    print("  Phase 2: Calculating formula-based targets...")
    MAX_ITERATIONS_FORMULA = len(targets_data_map) + 5
    
    # Iterate over all target numbers that have formulas
    for target_num_to_calculate in sorted(kpis_with_formula.keys()):
        kpi_list_for_formula_calc = kpis_with_formula[target_num_to_calculate]
        print(f"    Calculating formulas for Target {target_num_to_calculate}. KPIs: {kpi_list_for_formula_calc}")
        
        kpis_pending_formula = list(kpi_list_for_formula_calc)
        calculated_this_pass_successfully = set()

        for iteration in range(MAX_ITERATIONS_FORMULA):
            if not kpis_pending_formula: break
            made_progress_in_iteration = False
            next_pending_list = []

            for kpi_id_to_calc in kpis_pending_formula:
                target_entry = get_annual_target_entry(year, plant_id, kpi_id_to_calc)
                if not target_entry: continue
                
                # Find the specific target value record
                t_val_rec = next((tv for tv in target_entry['target_values'] if tv['target_number'] == target_num_to_calculate), None)
                if not t_val_rec: continue

                # Fetch standardized formula from KPI definition
                kpi_details_row = db_retriever.get_kpi_detailed_by_id(kpi_id_to_calc)
                kpi_details = dict(kpi_details_row) if kpi_details_row else {}
                
                # Priority: 1. Standardized JSON, 2. Standardized String, 3. Per-target Formula
                formula_to_use = kpi_details.get("formula_json") or kpi_details.get("formula_string") or t_val_rec.get('formula')
                formula_inputs_json_db = t_val_rec.get('formula_inputs', '[]') or '[]'

                if not (t_val_rec['is_formula_based'] and formula_to_use): continue

                is_node_dag = False
                try:
                    dag_data = json.loads(formula_to_use)
                    if isinstance(dag_data, dict) and "nodes" in dag_data: is_node_dag = True
                except: pass

                try:
                    if is_node_dag:
                        dag = KpiDAG.from_json(formula_to_use)
                        deps = dag.find_all_kpi_dependencies()
                        formula_inputs_def_py = [
                            {"kpi_id": d["kpi_id"], "target_source": f"annual_target{d['target_num']}", "variable_name": f"kpi_{d['kpi_id']}_t{d['target_num']}"}
                            for d in deps
                        ]
                    else:
                        formula_inputs_def_py = json.loads(formula_inputs_json_db)
                except: continue

                context_vars = {}
                all_inputs_ready = True
                for f_input in formula_inputs_def_py:
                    input_kpi_id = f_input.get("kpi_id")
                    input_target_field = f_input.get("target_source") # e.g. "annual_target1"
                    var_name = f_input.get("variable_name")

                    if not all([input_kpi_id, input_target_field, var_name]):
                        all_inputs_ready = False; break

                    # Dependency check
                    if input_kpi_id in kpis_pending_formula and input_kpi_id not in calculated_this_pass_successfully:
                        # If target_source matches current target_num, it's a pending dependency in this pass
                        if input_target_field == f"annual_target{target_num_to_calculate}":
                            all_inputs_ready = False; break

                    # Fetch value
                    input_entry = get_annual_target_entry(year, plant_id, input_kpi_id)
                    if not input_entry or input_entry.get(input_target_field) is None:
                        all_inputs_ready = False; break
                    
                    try:
                        context_vars[var_name] = float(input_entry[input_target_field])
                    except:
                        all_inputs_ready = False; break

                if not all_inputs_ready:
                    next_pending_list.append(kpi_id_to_calc); continue

                # Calculate
                try:
                    if is_node_dag:
                        def kpi_resolver(k_id, t_n):
                            res = get_annual_target_entry(year, plant_id, k_id)
                            return float(res.get(f"annual_target{t_n}", 0.0) or 0.0) if res else 0.0
                        calculated_value = dag.evaluate(kpi_resolver, default_target_num=target_num_to_calculate)
                    else:
                        calculated_value = _placeholder_safe_evaluate_formula(formula_to_use, context_vars)

                    with sqlite3.connect(db_targets_path) as conn_upd:
                        # Update normalized table
                        conn_upd.execute(
                            "UPDATE kpi_annual_target_values SET target_value=?, is_manual=0 WHERE annual_target_id=? AND target_number=?",
                            (calculated_value, target_entry['id'], target_num_to_calculate)
                        )
                        # Backward compatibility
                        if target_num_to_calculate in [1, 2]:
                            conn_upd.execute(
                                f"UPDATE annual_targets SET annual_target{target_num_to_calculate}=?, is_target{target_num_to_calculate}_manual=0 WHERE id=?",
                                (calculated_value, target_entry['id'])
                            )
                        conn_upd.commit()
                    
                    calculated_this_pass_successfully.add(kpi_id_to_calc)
                    kpis_needing_repartition_update.add(kpi_id_to_calc)
                    made_progress_in_iteration = True
                except Exception as e_eval:
                    print(f"      ERROR: Formula failed for KPI {kpi_id_to_calc} T{target_num_to_calculate}: {e_eval}")
                    next_pending_list.append(kpi_id_to_calc)

            kpis_pending_formula = [k for k in next_pending_list if k not in calculated_this_pass_successfully]
            if not made_progress_in_iteration and kpis_pending_formula: break

    # Phase 3: Master/Sub KPI distribution
    print("  Phase 3: Handling Master/Sub KPI distribution...")
    masters_to_re_evaluate = set()
    all_kpis_touched = {int(k) for k in targets_data_map.keys()}
    for tn in kpis_with_formula:
        all_kpis_touched.update(kpis_with_formula[tn])
    
    for kid in all_kpis_touched:
        role_info = get_kpi_role_details(kid)
        if role_info["role"] == "master": masters_to_re_evaluate.add(kid)
        elif role_info["role"] == "sub" and role_info.get("master_id"): masters_to_re_evaluate.add(role_info["master_id"])

    for master_kpi_id in masters_to_re_evaluate:
        master_entry = get_annual_target_entry(year, plant_id, master_kpi_id)
        if not master_entry: continue
        
        sub_kpi_ids = get_sub_kpis_for_master(master_kpi_id)
        if not sub_kpi_ids: continue

        sub_kpis_with_weights = []
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_k:
            for sid in sub_kpi_ids:
                w_row = conn_k.execute("SELECT distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id=? AND sub_kpi_spec_id=?", (master_kpi_id, sid)).fetchone()
                sub_kpis_with_weights.append({'id': sid, 'weight': float(w_row[0]) if w_row else 1.0})

        # Dynamically find all target numbers present for this master
        target_nums = [tv['target_number'] for tv in master_entry['target_values']]
        for tn in target_nums:
            master_val = master_entry.get(f"annual_target{tn}", 0.0) or 0.0
            fixed_sum = 0.0
            distributable = []
            total_w = 0.0

            for sub in sub_kpis_with_weights:
                s_entry = get_annual_target_entry(year, plant_id, sub['id'])
                s_val_rec = next((v for v in s_entry['target_values'] if v['target_number'] == tn), None) if s_entry else None
                
                is_fixed = (s_val_rec['is_manual'] or s_val_rec['is_formula_based']) if s_val_rec else True
                if is_fixed:
                    fixed_sum += float(s_entry.get(f"annual_target{tn}", 0.0) or 0.0) if s_entry else 0.0
                else:
                    distributable.append(sub)
                    total_w += sub['weight']

            remaining = master_val - fixed_sum
            if distributable:
                with sqlite3.connect(db_targets_path) as conn_s:
                    for d in distributable:
                        val = (remaining * d['weight'] / total_w) if total_w > 0 else (remaining / len(distributable))
                        at_row = conn_s.execute("SELECT id FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?", (year, plant_id, d['id'])).fetchone()
                        if at_row:
                            # Formula based is set to 0 for Sub-KPIs being distributed
                            conn_s.execute("INSERT OR REPLACE INTO kpi_annual_target_values (annual_target_id, target_number, target_value, is_manual, is_formula_based) VALUES (?, ?, ?, 0, 0)",
                                           (at_row[0], tn, val))
                            if tn in [1, 2]:
                                conn_s.execute(f"UPDATE annual_targets SET annual_target{tn}=?, is_target{tn}_manual=0, target{tn}_is_formula_based=0 WHERE id=?", (val, at_row[0]))
                            kpis_needing_repartition_update.add(d['id'])
                    conn_s.commit()

    # Phase 4: Repartitions (Processed in dependency order)
    print("  Phase 4: Calculating periodic repartitions...")
    
    # Simple dependency sort for the set of kpis needing update
    sorted_kpis = []
    visited_kpis = set()
    
    def visit_kpi(kid):
        if kid in visited_kpis: return
        visited_kpis.add(kid)
        
        details = db_retriever.get_kpi_detailed_by_id(kid)
        if details and details.get('formula_json'):
            try:
                dag = KpiDAG.from_json(details['formula_json'])
                for dep in dag.find_all_kpi_dependencies():
                    if dep['kpi_id'] in kpis_needing_repartition_update:
                        visit_kpi(dep['kpi_id'])
            except: pass
        sorted_kpis.append(kid)

    for kid in list(kpis_needing_repartition_update):
        visit_kpi(kid)

    for kid in sorted_kpis:
        entry = get_annual_target_entry(year, plant_id, kid)
        if entry:
            for tv in entry['target_values']:
                if tv['target_value'] is not None:
                    repartition_module.calculate_and_save_all_repartitions(year, plant_id, kid, tv['target_number'])

    print(f"INFO: Finished save_annual_targets for Year: {year}, Plant: {plant_id}")
