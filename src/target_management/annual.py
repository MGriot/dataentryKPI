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
    print(f"DEBUG: Formula='{formula_str}', Context={context_vars}")
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
    kpis_with_formula_target1 = []
    kpis_with_formula_target2 = []

    # Phase 1: Save definitions
    with sqlite3.connect(db_targets_path) as conn:
        cursor = conn.cursor()
        for kpi_spec_id_str, data_dict_from_ui in targets_data_map.items():
            try:
                current_kpi_spec_id = int(kpi_spec_id_str)
            except: continue

            record_row = get_annual_target_entry(year, plant_id, current_kpi_spec_id)
            record_dict = dict(record_row) if record_row else None

            # Values from UI or DB
            final_annual_t1 = data_dict_from_ui.get("annual_target1", record_dict.get("annual_target1", 0.0) if record_dict else 0.0)
            final_annual_t2 = data_dict_from_ui.get("annual_target2", record_dict.get("annual_target2", 0.0) if record_dict else 0.0)
            
            final_is_manual1 = data_dict_from_ui.get("is_target1_manual", record_dict.get("is_target1_manual", True) if record_dict else True)
            final_is_manual2 = data_dict_from_ui.get("is_target2_manual", record_dict.get("is_target2_manual", True) if record_dict else True)

            final_t1_is_formula = data_dict_from_ui.get("target1_is_formula_based", record_dict.get("target1_is_formula_based", False) if record_dict else False)
            final_t2_is_formula = data_dict_from_ui.get("target2_is_formula_based", record_dict.get("target2_is_formula_based", False) if record_dict else False)

            if record_dict:
                cursor.execute(
                    """UPDATE annual_targets SET annual_target1=?, annual_target2=?,
                       is_target1_manual=?, is_target2_manual=?,
                       target1_is_formula_based=?, target2_is_formula_based=?
                       WHERE id=?""",
                    (float(final_annual_t1), float(final_annual_t2), 
                     1 if final_is_manual1 else 0, 1 if final_is_manual2 else 0,
                     1 if final_t1_is_formula else 0, 1 if final_t2_is_formula else 0,
                     record_dict["id"])
                )
            else:
                cursor.execute(
                    """INSERT INTO annual_targets (year, plant_id, kpi_id, annual_target1, annual_target2, 
                       is_target1_manual, is_target2_manual, target1_is_formula_based, target2_is_formula_based)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (year, plant_id, current_kpi_spec_id, float(final_annual_t1), float(final_annual_t2),
                     1 if final_is_manual1 else 0, 1 if final_is_manual2 else 0,
                     1 if final_t1_is_formula else 0, 1 if final_t2_is_formula else 0)
                )
            
            kpis_needing_repartition_update.add(current_kpi_spec_id)
            if final_t1_is_formula: kpis_with_formula_target1.append(current_kpi_spec_id)
            if final_t2_is_formula: kpis_with_formula_target2.append(current_kpi_spec_id)
        conn.commit()

    # Phase 2: Formulas (Simplified evaluation)
    # ... (Keep existing iteration logic but call evaluate)
    # Phase 3: Master/Sub Distribution
    # ... (Ensuring weights are respected)
    
    # Trigger repartition at the end
    for kid in kpis_needing_repartition_update:
        repartition_module.calculate_and_save_all_repartitions(year, plant_id, kid, 1)
        repartition_module.calculate_and_save_all_repartitions(year, plant_id, kid, 2)

    # Phase 2: Calculate formula-based targets
    print("  Phase 2: Calculating formula-based targets...")
    MAX_ITERATIONS_FORMULA = (
        len(targets_data_map) + 5
    )  # Max attempts to resolve dependencies

    for target_num_idx, kpi_list_for_formula_calc in enumerate(
        [kpis_with_formula_target1, kpis_with_formula_target2]
    ):
        target_num_to_calculate = target_num_idx + 1  # 1 or 2
        if not kpi_list_for_formula_calc:
            print(f"    No KPIs with formulas for Target {target_num_to_calculate}.")
            continue

        print(
            f"    Calculating formulas for Target {target_num_to_calculate}. KPIs: {kpi_list_for_formula_calc}"
        )
        kpis_pending_formula = list(
            kpi_list_for_formula_calc
        )  # KPIs needing calculation in this pass
        calculated_this_pass_successfully = (
            set()
        )  # Track KPIs calculated in the current formula pass (T1 or T2)

        for iteration in range(MAX_ITERATIONS_FORMULA):
            if not kpis_pending_formula:
                print(
                    f"      All formulas for Target {target_num_to_calculate} resolved in iteration {iteration}."
                )
                break

            made_progress_in_iteration = False
            next_pending_list_for_this_target_num = (
                []
            )  # KPIs to retry in the next iteration for this specific target_num

            for kpi_id_to_calc in kpis_pending_formula:
                target_entry_row = get_annual_target_entry(
                    year, plant_id, kpi_id_to_calc
                )
                if not target_entry_row:
                    continue
                target_entry = dict(target_entry_row)

                # Fetch standardized formula from KPI definition
                kpi_details_row = db_retriever.get_kpi_detailed_by_id(kpi_id_to_calc)
                kpi_details = dict(kpi_details_row) if kpi_details_row else {}
                std_formula_json = kpi_details.get("formula_json")
                std_formula_str = kpi_details.get("formula_string")

                is_formula_flag_db = bool(
                    target_entry.get(
                        f"target{target_num_to_calculate}_is_formula_based", False
                    )
                )
                
                # Priority: 1. Standardized JSON, 2. Standardized String, 3. Per-target Formula
                formula_to_use = std_formula_json or std_formula_str or target_entry.get(f"target{target_num_to_calculate}_formula")
                
                formula_inputs_json_db = (
                    target_entry.get(
                        f"target{target_num_to_calculate}_formula_inputs", "[]"
                    )
                    or "[]"
                )

                if not (is_formula_flag_db and formula_to_use):
                    continue

                # Detect if formula is a Node-based DAG (JSON)
                is_node_dag = False
                try:
                    dag_data = json.loads(formula_to_use)
                    if isinstance(dag_data, dict) and "nodes" in dag_data:
                        is_node_dag = True
                except (json.JSONDecodeError, TypeError):
                    pass

                try:
                    if is_node_dag:
                        dag = KpiDAG.from_json(formula_to_use)
                        # Extract inputs from DAG nodes
                        deps = dag.find_all_kpi_dependencies()
                        # Map to expected format for iteration logic
                        formula_inputs_def_py = [
                            {
                                "kpi_id": d["kpi_id"], 
                                "target_source": f"annual_target{d['target_num']}", 
                                "variable_name": f"kpi_{d['kpi_id']}_t{d['target_num']}"
                            } for d in deps
                        ]
                    else:
                        formula_inputs_def_py = json.loads(formula_inputs_json_db)
                        if not isinstance(formula_inputs_def_py, list):
                            formula_inputs_def_py = []
                except (json.JSONDecodeError, TypeError):
                    print(
                        f"      WARN: KPI {kpi_id_to_calc} T{target_num_to_calculate} has invalid input definition. Skipping."
                    )
                    continue

                context_vars = {}
                all_inputs_ready = True
                for f_input in formula_inputs_def_py:
                    input_kpi_id = f_input.get("kpi_id")
                    input_target_field_name = f_input.get(
                        "target_source"
                    )  # e.g., "annual_target1" or "annual_target2"
                    var_name_in_formula = f_input.get("variable_name")

                    if not all(
                        [input_kpi_id, input_target_field_name, var_name_in_formula]
                    ):
                        print(
                            f"      WARN: Incomplete formula input definition for KPI {kpi_id_to_calc} T{target_num_to_calculate}. Input: {f_input}. Skipping formula."
                        )
                        all_inputs_ready = False
                        break

                    # Check for dependency within the same formula pass (e.g. T1 depends on another T1)
                    # If input_kpi_id is also in kpis_pending_formula for *this target number* and *not yet calculated in this pass*, it's a pending dependency.
                    if (
                        input_kpi_id in kpis_pending_formula
                        and input_kpi_id not in calculated_this_pass_successfully
                    ):
                        # This is a bit tricky: we need to ensure the source value ISN'T ITSELF a formula that's still pending for the SAME target_num
                        input_kpi_target_entry_check_row = get_annual_target_entry(
                            year, plant_id, input_kpi_id
                        )
                        if input_kpi_target_entry_check_row:
                            input_kpi_target_entry_check = dict(
                                input_kpi_target_entry_check_row
                            )
                            source_target_is_formula_pending_this_pass = False
                            if (
                                input_target_field_name
                                == f"annual_target{target_num_to_calculate}"
                                and bool(
                                    input_kpi_target_entry_check.get(
                                        f"target{target_num_to_calculate}_is_formula_based",
                                        False,
                                    )
                                )
                            ):
                                source_target_is_formula_pending_this_pass = True

                            if source_target_is_formula_pending_this_pass:
                                print(
                                    f"        Deferring KPI {kpi_id_to_calc} T{target_num_to_calculate}: input {var_name_in_formula} (from KPI {input_kpi_id}.{input_target_field_name}) is also a pending formula in this pass."
                                )
                                all_inputs_ready = False
                                break
                        else:  # Source KPI for formula input not found, critical issue
                            print(
                                f"      CRITICAL WARN: Source KPI {input_kpi_id} for formula input '{var_name_in_formula}' not found in annual_targets. KPI {kpi_id_to_calc} T{target_num_to_calculate} cannot be calculated."
                            )
                            all_inputs_ready = False
                            break

                    # Fetch the actual value for the input variable
                    input_kpi_target_entry_for_value_row = get_annual_target_entry(
                        year, plant_id, input_kpi_id
                    )
                    if (
                        not input_kpi_target_entry_for_value_row
                        or input_target_field_name
                        not in dict(input_kpi_target_entry_for_value_row).keys()
                        or dict(input_kpi_target_entry_for_value_row)[
                            input_target_field_name
                        ]
                        is None
                    ):
                        print(
                            f"        Deferring KPI {kpi_id_to_calc} T{target_num_to_calculate}: input value for {var_name_in_formula} (from KPI {input_kpi_id}.{input_target_field_name}) not yet available or null."
                        )
                        all_inputs_ready = False
                        break
                    try:
                        context_vars[var_name_in_formula] = float(
                            dict(input_kpi_target_entry_for_value_row)[
                                input_target_field_name
                            ]
                        )
                    except (TypeError, ValueError):
                        print(
                            f"      WARN: Non-numeric value for formula input {var_name_in_formula} (KPI {input_kpi_id}.{input_target_field_name}). Skipping formula for KPI {kpi_id_to_calc} T{target_num_to_calculate}."
                        )
                        all_inputs_ready = False
                        break

                if not all_inputs_ready:
                    next_pending_list_for_this_target_num.append(kpi_id_to_calc)
                    continue  # Try this kpi_id_to_calc again in the next iteration for this target_num

                # All inputs are ready, attempt to calculate
                try:
                    if is_node_dag:
                        # dag is already defined above
                        def kpi_resolver(kpi_id, target_num):
                            res_row = get_annual_target_entry(year, plant_id, kpi_id)
                            if res_row:
                                return float(dict(res_row).get(f"annual_target{target_num}", 0.0) or 0.0)
                            return 0.0
                            
                        calculated_value = dag.evaluate(kpi_resolver, default_target_num=target_num_to_calculate)
                    else:
                        # Legacy string-based formula
                        calculated_value = _placeholder_safe_evaluate_formula(
                            formula_to_use, context_vars
                        )

                    with sqlite3.connect(db_targets_path) as conn_update_formula:
                        update_cursor = conn_update_formula.cursor()
                        # Update the specific target field (annual_target1 or annual_target2)
                        # and set its corresponding 'is_manual' flag to False.
                        update_cursor.execute(
                            f"""UPDATE annual_targets
                                SET annual_target{target_num_to_calculate}=?, is_target{target_num_to_calculate}_manual=?
                                WHERE id=?""",
                            (calculated_value, False, target_entry["id"]),
                        )
                        conn_update_formula.commit()
                    print(
                        f"      SUCCESS: KPI {kpi_id_to_calc} T{target_num_to_calculate} calculated by formula: {calculated_value}"
                    )
                    calculated_this_pass_successfully.add(kpi_id_to_calc)
                    kpis_needing_repartition_update.add(kpi_id_to_calc)
                    made_progress_in_iteration = True
                except Exception as e_eval:
                    print(
                        f"      ERROR: Formula calculation failed for KPI {kpi_id_to_calc} T{target_num_to_calculate}: {e_eval}. Formula: '{formula_to_use}', Inputs: {context_vars}"
                    )
                    next_pending_list_for_this_target_num.append(
                        kpi_id_to_calc
                    )  # Retry if error during eval

            # Update kpis_pending_formula for the next iteration of this target_num calculation
            kpis_pending_formula = [
                kpi
                for kpi in next_pending_list_for_this_target_num
                if kpi not in calculated_this_pass_successfully
            ]

            if not made_progress_in_iteration and kpis_pending_formula:
                print(
                    f"    WARN: No progress in formula calculation for Target {target_num_to_calculate} in iteration {iteration + 1}. "
                    f"Pending KPIs: {kpis_pending_formula}. Possible circular dependency or missing data for these."
                )
                break  # Break from iterations for THIS target_num

        if kpis_pending_formula:  # After all iterations for this target_num
            print(
                f"  WARN: Formula calculation for Target {target_num_to_calculate} NOT completed for all KPIs after {MAX_ITERATIONS_FORMULA} iterations. "
                f"Still pending: {kpis_pending_formula}"
            )
            for unresolved_kpi_id in kpis_pending_formula:
                print(
                    f"    - KPI {unresolved_kpi_id} (Target {target_num_to_calculate}) remains unresolved."
                )
    print("  Phase 2: Formula-based target calculation finished.")

    # Phase 3: Master/Sub KPI distribution
    print("  Phase 3: Handling Master/Sub KPI distribution...")
    masters_to_re_evaluate = set()
    
    # Check all KPIs involved in the current save operation
    all_kpi_ids_in_pass = (
        {int(k) for k in targets_data_map.keys()}
        .union(kpis_with_formula_target1)
        .union(kpis_with_formula_target2)
    )
    
    for kpi_id_eval in all_kpi_ids_in_pass:
        role_info = get_kpi_role_details(kpi_id_eval)
        if role_info["role"] == "master":
            masters_to_re_evaluate.add(kpi_id_eval)
        elif role_info["role"] == "sub" and role_info.get("master_id"):
            masters_to_re_evaluate.add(role_info["master_id"])

    if initiator_kpi_spec_id:
        role_info = get_kpi_role_details(initiator_kpi_spec_id)
        if role_info["role"] == "master":
            masters_to_re_evaluate.add(initiator_kpi_spec_id)
        elif role_info["role"] == "sub" and role_info.get("master_id"):
            masters_to_re_evaluate.add(role_info["master_id"])

    print(f"    Identified Master KPIs for re-distribution: {masters_to_re_evaluate}")

    for master_kpi_id in masters_to_re_evaluate:
        master_target_entry_row = get_annual_target_entry(year, plant_id, master_kpi_id)
        if not master_target_entry_row: continue
        master_target_entry = dict(master_target_entry_row)

        sub_kpi_ids = get_sub_kpis_for_master(master_kpi_id)
        if not sub_kpi_ids: continue

        # Get weights from db_kpis
        sub_kpis_with_weights = []
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_k:
            conn_weights = conn_k.cursor()
            for sid in sub_kpi_ids:
                w_row = conn_weights.execute("SELECT distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id=? AND sub_kpi_spec_id=?", (master_kpi_id, sid)).fetchone()
                sub_kpis_with_weights.append({'id': sid, 'weight': float(w_row[0]) if w_row else 1.0})

        for tn in [1, 2]:
            master_val = master_target_entry.get(f"annual_target{tn}", 0.0)
            if master_val is None: master_val = 0.0
            
            fixed_sum = 0.0
            distributable = []
            total_w = 0.0

            for sub in sub_kpis_with_weights:
                sid = sub['id']
                s_row = get_annual_target_entry(year, plant_id, sid)
                s_dict = dict(s_row) if s_row else {}
                
                is_fixed = s_dict.get(f"is_target{tn}_manual", True) or s_dict.get(f"target{tn}_is_formula_based", False)
                if is_fixed:
                    fixed_sum += float(s_dict.get(f"annual_target{tn}", 0.0) or 0.0)
                else:
                    distributable.append(sub)
                    total_w += sub['weight']

            remaining = master_val - fixed_sum
            if distributable:
                with sqlite3.connect(db_targets_path) as conn_s:
                    for d in distributable:
                        val = (remaining * d['weight'] / total_w) if total_w > 0 else (remaining / len(distributable))
                        
                        # Update sub target (it's not manual, not formula, it's derived)
                        conn_s.execute(f"UPDATE annual_targets SET annual_target{tn}=?, is_target{tn}_manual=0, target{tn}_is_formula_based=0 WHERE year=? AND plant_id=? AND kpi_id=?", 
                                       (val, year, plant_id, d['id']))
                        kpis_needing_repartition_update.add(d['id'])
                    conn_s.commit()
    print("  Phase 3: Master/Sub KPI distribution finished.")

    # Phase 4: Calculate and save repartitions for all affected KPIs
    print(
        f"  Phase 4: Triggering repartition calculations for {len(kpis_needing_repartition_update)} KPIs: {kpis_needing_repartition_update}"
    )
    if not kpis_needing_repartition_update:
        print("    No KPIs require repartition calculation.")
    else:
        for kpi_id_recalc in kpis_needing_repartition_update:
            target_entry_check_row = get_annual_target_entry(
                year, plant_id, kpi_id_recalc
            )
            if target_entry_check_row:
                target_entry_check = dict(target_entry_check_row)
                # Check if target1 exists and is not None before calculating its repartition
                if target_entry_check.get("annual_target1") is not None:
                    print(
                        f"    Calculating repartitions for KPI {kpi_id_recalc}, Target 1..."
                    )
                    repartition_module.calculate_and_save_all_repartitions(
                        year, plant_id, kpi_id_recalc, 1
                    )
                else:
                    print(
                        f"    Skipping repartition for KPI {kpi_id_recalc}, Target 1 (value is None)."
                    )

                # Check if target2 exists and is not None
                if target_entry_check.get("annual_target2") is not None:
                    print(
                        f"    Calculating repartitions for KPI {kpi_id_recalc}, Target 2..."
                    )
                    repartition_module.calculate_and_save_all_repartitions(
                        year, plant_id, kpi_id_recalc, 2
                    )
                else:
                    print(
                        f"    Skipping repartition for KPI {kpi_id_recalc}, Target 2 (value is None)."
                    )
            else:
                print(
                    f"    WARN: Target entry for KPI {kpi_id_recalc} not found before repartition. Skipping."
                )
    print("  Phase 4: Repartition calculations finished.")

    print(
        f"INFO: Finished save_annual_targets for Year: {year}, Plant: {plant_id}"
    )


if __name__ == "__main__":
    print("--- Running target_management/annual.py for testing ---")
    # This test block is complex to set up fully due to dependencies on
    # DB_KPIS (for master/sub links), DB_TARGETS, data_retriever, and repartition module.
    # A full test would involve:
    # 1. Setting up mock DBs or using temporary test DBs.
    # 2. Populating DB_KPIS with master/sub kpi_specs and links.
    # 3. Populating DB_TARGETS with initial data if needed.
    # 4. Ensuring data_retriever and repartition mocks/implementations are available.

    # Simplified test focusing on the flow and structure:
    print("INFO: Mocking dependencies for a basic flow test of save_annual_targets.")

    # --- Mocking for test execution ---
    # This simulates that the necessary modules and DBs are "available"
    

    # Save original app_config settings for database paths
    original_db_base_dir = app_config.SETTINGS["database_base_dir"]

    DB_TARGETS_TEST_FILE = "test_annual_targets.sqlite"
    DB_KPIS_TEST_FILE_FOR_ANNUAL = "test_annual_kpis_links.sqlite"  # For master/sub

    # Create dummy DB files for testing if they don't exist
    if not Path(DB_TARGETS_TEST_FILE).exists():
        Path(DB_TARGETS_TEST_FILE).touch()
    if not Path(DB_KPIS_TEST_FILE_FOR_ANNUAL).exists():
        Path(DB_KPIS_TEST_FILE_FOR_ANNUAL).touch()

    # Temporarily set app_config to use the test files' directory
    app_config.SETTINGS["database_base_dir"] = str(Path(DB_TARGETS_TEST_FILE).parent)

    # Mocked data store for get_annual_target_entry and other retrievers
    _mock_annual_targets_db = {}  # {(year, plant_id, kpi_id): {data}}
    _mock_kpis_links_db = {}  # {master_id: [sub_ids]}
    _mock_kpis_roles_db = (
        {}
    )  # {kpi_id: {"role": "master/sub/none", "master_id": id, "related_kpis": [ids]}}
    _mock_kpis_link_weights = {}  # {(master_id, sub_id): weight}

    def _mock_get_annual_target_entry(year, plant_id, kpi_id):
        # Instead of just a dict, let's read from the test DB we just wrote to in Phase 1
        db_path = app_config.get_database_path("db_kpi_targets.db")
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    "SELECT * FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?",
                    (year, plant_id, kpi_id),
                ).fetchone()
        except Exception:
            return None

    def _mock_get_kpi_role_details(kpi_id):
        return _mock_kpis_roles_db.get(
            kpi_id, {"role": "none", "related_kpis": [], "master_id": None}
        )

    def _mock_get_sub_kpis_for_master(master_kpi_id):
        return _mock_kpis_links_db.get(master_kpi_id, [])

    # Replace actual functions with mocks for isolated testing
    get_annual_target_entry_orig = get_annual_target_entry
    get_kpi_role_details_orig = get_kpi_role_details
    get_sub_kpis_for_master_orig = get_sub_kpis_for_master
    calculate_and_save_all_repartitions_orig = repartition_module.calculate_and_save_all_repartitions

    get_annual_target_entry = _mock_get_annual_target_entry
    get_kpi_role_details = _mock_get_kpi_role_details
    get_sub_kpis_for_master = _mock_get_sub_kpis_for_master
    # calculate_and_save_all_repartitions is already mocked if module isn't found,
    # but we can provide a more verbose mock for testing:
    _repartition_calls = []

    def _verbose_mock_repartition(year, plant_id, kpi_id, target_num):
        call_info = (year, plant_id, kpi_id, target_num)
        print(f"  MOCK REPARTITION CALLED: {call_info}")
        _repartition_calls.append(call_info)

    calculate_and_save_all_repartitions = _verbose_mock_repartition

    # Setup minimal DB_TARGETS table schema for the test
    with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
        conn.execute("DROP TABLE IF EXISTS annual_targets;")
        conn.execute(
            f"""
            CREATE TABLE annual_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER, plant_id INTEGER, kpi_id INTEGER,
                annual_target1 REAL, annual_target2 REAL,
                repartition_logic TEXT, repartition_values TEXT, distribution_profile TEXT, profile_params TEXT,
                is_target1_manual BOOLEAN, is_target2_manual BOOLEAN,
                target1_is_formula_based BOOLEAN, target1_formula TEXT, target1_formula_inputs TEXT,
                target2_is_formula_based BOOLEAN, target2_formula TEXT, target2_formula_inputs TEXT,
                UNIQUE(year, plant_id, kpi_id));
        """
        )
        conn.commit()
    # Setup minimal DB_KPIS table for master/sub link weights
    with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_kpis_test:
        conn_kpis_test.execute("DROP TABLE IF EXISTS kpi_master_sub_links;")
        conn_kpis_test.execute(
            """
            CREATE TABLE kpi_master_sub_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                master_kpi_spec_id INTEGER NOT NULL, sub_kpi_spec_id INTEGER NOT NULL,
                distribution_weight REAL NOT NULL DEFAULT 1.0,
                UNIQUE (master_kpi_spec_id, sub_kpi_spec_id));
        """
        )
        conn_kpis_test.commit()

    try:
        print("\n--- Test Scenario 1: Basic Save & Formula ---")
        test_year = 2023
        test_plant_id = 1
        kpi_a_id, kpi_b_id, kpi_c_id = 10, 11, 12  # Formula C = A + B

        targets_input_scenario1 = {
            str(kpi_a_id): {"annual_target1": 100.0, "is_target1_manual": True},
            str(kpi_b_id): {"annual_target1": 50.0, "is_target1_manual": True},
            str(kpi_c_id): {
                "target1_is_formula_based": True,
                "target1_formula": "A_val + B_val",
                "target1_formula_inputs": [
                    {
                        "kpi_id": kpi_a_id,
                        "target_source": "annual_target1",
                        "variable_name": "A_val",
                    },
                    {
                        "kpi_id": kpi_b_id,
                        "target_source": "annual_target1",
                        "variable_name": "B_val",
                    },
                ],
            },
        }
        # Populate mock DB for formula inputs to be found by get_annual_target_entry
        # This happens *after* Phase 1 save, so the actual save_annual_targets will write these first.
        # For the mock to work during formula eval, we can pre-populate the _mock_annual_targets_db
        # as if phase 1 already ran for A and B.

        save_annual_targets(test_year,             test_plant_id, targets_input_scenario1)

        # Verification for Scenario 1 (check the SQLite DB_TARGETS_TEST_FILE)
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn_verify:
            conn_verify.row_factory = sqlite3.Row
            c_target_row = conn_verify.execute(
                "SELECT annual_target1, is_target1_manual FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?",
                (test_year, test_plant_id, kpi_c_id),
            ).fetchone()
            assert c_target_row is not None, f"KPI C target not found for scenario 1"
            assert (
                abs(c_target_row["annual_target1"] - 150.0) < 0.01
            ), f"KPI C formula incorrect: got {c_target_row['annual_target1']}"
            assert not c_target_row[
                "is_target1_manual"
            ], "KPI C should not be manual after formula calculation."
            print(
                "  Scenario 1 (Basic Save & Formula): KPI C calculated correctly (150.0)."
            )
        assert (test_year, test_plant_id, kpi_a_id, 1) in _repartition_calls
        assert (test_year, test_plant_id, kpi_b_id, 1) in _repartition_calls
        assert (test_year, test_plant_id, kpi_c_id, 1) in _repartition_calls
        print("  Scenario 1: Repartition calls verified.")

        print("\n--- Test Scenario 2: Master/Sub Distribution ---")
        master_id, sub1_id, sub2_id = 20, 21, 22
        _repartition_calls.clear()  # Clear for next verification
        _mock_annual_targets_db.clear()  # Clear for next scenario

        # Setup master/sub relationships in mocks and test DB_KPIS
        _mock_kpis_roles_db[master_id] = {
            "role": "master",
            "related_kpis": [sub1_id, sub2_id],
        }
        _mock_kpis_roles_db[sub1_id] = {"role": "sub", "master_id": master_id}
        _mock_kpis_roles_db[sub2_id] = {"role": "sub", "master_id": master_id}
        _mock_kpis_links_db[master_id] = [sub1_id, sub2_id]
        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_kpis_test:
            conn_kpis_test.execute(
                "INSERT INTO kpi_master_sub_links (master_kpi_spec_id, sub_kpi_spec_id, distribution_weight) VALUES (?,?,?)",
                (master_id, sub1_id, 1.0),
            )
            conn_kpis_test.execute(
                "INSERT INTO kpi_master_sub_links (master_kpi_spec_id, sub_kpi_spec_id, distribution_weight) VALUES (?,?,?)",
                (master_id, sub2_id, 3.0),
            )  # Weight 1:3
            conn_kpis_test.commit()

        targets_input_scenario2 = {
            str(master_id): {"annual_target1": 1000.0, "is_target1_manual": True},
            # Sub1 is manual, Sub2 will be derived
            str(sub1_id): {"annual_target1": 100.0, "is_target1_manual": True},
        }
        save_annual_targets(
            test_year,
            test_plant_id,
            targets_input_scenario2,
            initiator_kpi_spec_id=master_id,
        )

        # Verification for Scenario 2
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn_verify:
            conn_verify.row_factory = sqlite3.Row
            sub2_target_row = conn_verify.execute(
                "SELECT annual_target1, is_target1_manual FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?",
                (test_year, test_plant_id, sub2_id),
            ).fetchone()
            assert (
                sub2_target_row is not None
            ), "KPI Sub2 target not found for scenario 2"
            # Master (1000) - Sub1_manual (100) = 900 remaining.
            # Sub2 weight 3 / (Sub1 implicit weight 1 + Sub2 weight 3 from link) = 3/4 if sub1 was also derived
            # But sub1 is manual. So remaining 900 is for sub2.
            # Total weight for derived is just sub2's weight (3.0)
            # Sub2 gets (3.0 / 3.0) * 900 = 900.
            # RETHINK: the logic from original code was sum_of_manual_or_formula_sub_targets,
            # then remaining_target_for_distribution.
            # For derived, it used total_weight_for_distribution of *only the derived* subs.
            # So, if only Sub2 is derived, total_weight_for_distribution is Sub2's weight (3.0).
            # Sub2 gets (3.0 / 3.0) * (1000 - 100) = 900.
            assert (
                abs(sub2_target_row["annual_target1"] - 900.0) < 0.01
            ), f"KPI Sub2 derived value incorrect: got {sub2_target_row['annual_target1']}, expected 900"
            assert not sub2_target_row[
                "is_target1_manual"
            ], "KPI Sub2 should not be manual after derivation."
            print("  Scenario 2 (Master/Sub): KPI Sub2 derived correctly (900.0).")

        assert (test_year, test_plant_id, master_id, 1) in _repartition_calls
        assert (test_year, test_plant_id, sub1_id, 1) in _repartition_calls
        assert (test_year, test_plant_id, sub2_id, 1) in _repartition_calls
        print("  Scenario 2: Repartition calls verified.")

        print("\n--- All target_management.annual basic tests passed ---")

    except Exception as e:
        print(f"\n--- AN ERROR OCCURRED DURING TESTING (target_management.annual) ---")
        print(str(e))
        print(traceback.format_exc())
    finally:
        # Restore original functions and DB paths
        get_annual_target_entry = get_annual_target_entry_orig
        get_kpi_role_details = get_kpi_role_details_orig
        get_sub_kpis_for_master = get_sub_kpis_for_master_orig
        calculate_and_save_all_repartitions = calculate_and_save_all_repartitions_orig

        import os

        for test_db_file in [DB_TARGETS_TEST_FILE, DB_KPIS_TEST_FILE_FOR_ANNUAL]:
            if os.path.exists(test_db_file):
                try:
                    os.remove(test_db_file)
                    print(f"INFO: Cleaned up test file: {test_db_file}")
                except OSError as e_clean:
                    print(
                        f"ERROR: Could not clean up test file {test_db_file}: {e_clean}"
                    )
        # Restore original app_config setting
        app_config.SETTINGS["database_base_dir"] = original_db_base_dir