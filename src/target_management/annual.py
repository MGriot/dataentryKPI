# your_project_root/target_management/annual.py
import sqlite3
import json
import traceback
import numpy # For _placeholder_safe_evaluate_formula if it uses numpy functions directly
from src.config import settings as app_config
from pathlib import Path
from src import data_retriever as db_retriever
from src.data_retriever import get_annual_target_entry


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
    try:
        pattern = r'\[(\d+)\]'
        
        def replacer(match):
            kpi_id = match.group(1)
            var_name = f"kpi_{kpi_id}"
            val = context_vars.get(var_name, 0.0)
            return str(val)
            
        processed_formula = re.sub(pattern, replacer, formula_str)
        
        allowed_names = {"abs": abs, "min": min, "max": max, "round": round}
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
            record_dict = record_row if record_row else None

            # 1a. Update/Insert annual_targets (metadata)
            if record_dict:
                at_id = record_dict['id']
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
                
                t_val_rec = next((tv for tv in target_entry['target_values'] if tv['target_number'] == target_num_to_calculate), None)
                if not t_val_rec: continue

                kpi_details_row = db_retriever.get_kpi_detailed_by_id(kpi_id_to_calc)
                kpi_details = dict(kpi_details_row) if kpi_details_row else {}
                
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
                            {"kpi_id": d["kpi_id"], "target_num": d["target_num"], "variable_name": f"kpi_{d['kpi_id']}_t{d['target_num']}"}
                            for d in deps
                        ]
                    else:
                        formula_inputs_def_py = json.loads(formula_inputs_json_db)
                except: continue

                context_vars = {}
                all_inputs_ready = True
                for f_input in formula_inputs_def_py:
                    input_kpi_id = f_input.get("kpi_id")
                    input_target_num = f_input.get("target_num") or int(f_input.get("target_source", "annual_target1")[-1])
                    var_name = f_input.get("variable_name")

                    if not all([input_kpi_id, input_target_num, var_name]):
                        all_inputs_ready = False; break

                    if input_kpi_id in kpis_pending_formula and input_kpi_id not in calculated_this_pass_successfully:
                        if input_target_num == target_num_to_calculate:
                            all_inputs_ready = False; break

                    input_entry = get_annual_target_entry(year, plant_id, input_kpi_id)
                    if not input_entry:
                        all_inputs_ready = False; break
                    
                    input_val_rec = next((v for v in input_entry['target_values'] if v['target_number'] == input_target_num), None)
                    if input_val_rec is None or input_val_rec['target_value'] is None:
                        all_inputs_ready = False; break
                    
                    context_vars[var_name] = float(input_val_rec['target_value'])

                if not all_inputs_ready:
                    next_pending_list.append(kpi_id_to_calc); continue

                try:
                    if is_node_dag:
                        def kpi_resolver(k_id, t_n):
                            res = get_annual_target_entry(year, plant_id, k_id)
                            if not res: return 0.0
                            val_rec = next((v for v in res['target_values'] if v['target_number'] == t_n), None)
                            return float(val_rec['target_value']) if val_rec else 0.0
                        calculated_value = dag.evaluate(kpi_resolver, default_target_num=target_num_to_calculate)
                    else:
                        calculated_value = _placeholder_safe_evaluate_formula(formula_to_use, context_vars)

                    with sqlite3.connect(db_targets_path) as conn_upd:
                        conn_upd.execute(
                            "UPDATE kpi_annual_target_values SET target_value=?, is_manual=0 WHERE annual_target_id=? AND target_number=?",
                            (calculated_value, target_entry['id'], target_num_to_calculate)
                        )
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

    # Phase 3: (Removed) Master/Sub distribution

    # Phase 4: Repartitions (Processed in dependency order)
    print("  Phase 4: Calculating periodic repartitions...")
    
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
