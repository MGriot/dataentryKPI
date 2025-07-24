# your_project_root/target_management/annual.py
import sqlite3
import json
import traceback
import numpy # For _placeholder_safe_evaluate_formula if it uses numpy functions directly
import app_config
from pathlib import Path

# Configuration imports
from gui.shared.constants import (
    REPARTITION_LOGIC_ANNO,
    PROFILE_ANNUAL_PROGRESSIVE,
)

# Module availability flags & Mocks
_data_retriever_available = False
_repartition_module_available = False

try:
    from data_retriever import (
        get_annual_target_entry,
        get_kpi_role_details,
        get_sub_kpis_for_master,
        # Potentially get_kpi_detailed_by_id if needed here, though repartition uses it
    )

    _data_retriever_available = True
except ImportError:
    print(
        "WARNING: data_retriever not fully available for annual.py. Mocks being used."
    )

    def get_annual_target_entry(year, stabilimento_id, kpi_spec_id):
        return None

    def get_kpi_role_details(kpi_spec_id):
        return {"role": "none", "related_kpis": [], "master_id": None}

    def get_sub_kpis_for_master(master_kpi_spec_id):
        return []


try:
    from .repartition import calculate_and_save_all_repartitions

    _repartition_module_available = True
except ImportError:
    print(
        "WARNING: target_management.repartition not available for annual.py. Mock being used."
    )

    def calculate_and_save_all_repartitions(
        year, stabilimento_id, kpi_id_recalc, target_number
    ):
        print(
            f"MOCK: calculate_and_save_all_repartitions({year}, {stabilimento_id}, {kpi_id_recalc}, {target_number}) called."
        )
        pass


# --- Formula Evaluation (Placeholder - Needs Secure Implementation) ---
def _placeholder_safe_evaluate_formula(formula_str: str, context_vars: dict):
    """
    UNSAFE PLACEHOLDER for formula evaluation.
    In a real application, replace this with a secure and robust
    formula parsing and evaluation library (e.g., asteval, numexpr, or a custom parser).
    """
    print(f"DEBUG (UNSAFE EVAL): Formula='{formula_str}', Context={context_vars}")
    try:
        # VERY DANGEROUS: eval() is a security risk if formula_str is user-supplied.
        # Create a limited scope for eval, but this is still not truly safe.
        # Only allow names from context_vars and potentially safe math functions.
        allowed_names = {key: val for key, val in context_vars.items()}
        # Example of adding safe math functions from numpy if needed by formulas
        # allowed_names.update({
        #     'sqrt': numpy.sqrt, 'power': numpy.power, 'sin': numpy.sin, 'cos': numpy.cos,
        #     'log': numpy.log, 'log10': numpy.log10, 'exp': numpy.exp, 'abs': numpy.abs,
        #     'pi': numpy.pi
        # })
        # For builtins, provide an empty dict or a carefully curated one.
        # Using {"__builtins__": {}} makes it slightly safer by removing most builtins.
        code = compile(formula_str, "<string>", "eval")

        # Further security: analyze 'code.co_names' to ensure only allowed functions/variables are called.
        # For example:
        # for name in code.co_names:
        #     if name not in allowed_names and name not in ['None', 'True', 'False']: # Check against a list of allowed global names
        #         raise NameError(f"Usage of disallowed name '{name}' in formula")

        return eval(code, {"__builtins__": {}}, allowed_names)
    except NameError as ne:
        print(
            f"ERROR during (unsafe) formula evaluation (NameError): {ne}. Formula: '{formula_str}', Context: {context_vars}"
        )
        raise ValueError(f"Formula variable or function not defined: {ne}")
    except Exception as e:
        print(
            f"ERROR during (unsafe) formula evaluation: {e}. Formula: '{formula_str}', Context: {context_vars}"
        )
        print(traceback.format_exc())
        raise ValueError(f"Formula evaluation failed: {e}")


# --- Annual Target Management ---
def save_annual_targets(
    year: int,
    stabilimento_id: int,
    targets_data_map: dict,
    initiator_kpi_spec_id: int = None,
):
    """
    Saves annual targets, calculates formula-based targets, handles master/sub KPI
    distribution, and triggers repartition calculations.

    Args:
        year (int): The year for which targets are being saved.
        stabilimento_id (int): The ID of the stabilimento.
        targets_data_map (dict): A dictionary where keys are kpi_spec_id (as strings)
                                 and values are dictionaries containing target data from the UI/input.
                                 Expected keys in inner dict: 'annual_target1', 'annual_target2',
                                 'repartition_logic', 'distribution_profile', 'repartition_values' (py dict),
                                 'profile_params' (py dict), 'is_target1_manual', 'is_target2_manual',
                                 'target1_is_formula_based', 'target1_formula', 'target1_formula_inputs' (py list),
                                 'target2_is_formula_based', 'target2_formula', 'target2_formula_inputs' (py list).
        initiator_kpi_spec_id (int, optional): The kpi_spec_id that triggered the save,
                                               used to help identify master KPIs for re-evaluation.
    """
    db_targets_path = app_config.get_database_path("db_kpi_targets.db")
    db_kpis_path = app_config.get_database_path("db_kpis.db")

    if not isinstance(db_targets_path, Path) or not db_targets_path.parent.exists() or \
       not isinstance(db_kpis_path, Path) or not db_kpis_path.parent.exists():
        raise ConnectionError("DB_TARGETS or DB_KPIS is not properly configured. Cannot save annual targets.")

    if not _data_retriever_available or not _repartition_module_available:
        print(
            "CRITICAL ERROR: Missing data_retriever or repartition module. Cannot save annual targets."
        )
        # Depending on how critical this is, you might raise an ImportError or Exception.
        # For now, just printing and returning to avoid partial execution if mocks are active.
        return

    if not targets_data_map:
        print("INFO: No annual target data provided to save.")
        return

    print(
        f"INFO: Starting save_annual_targets for Year: {year}, Stab: {stabilimento_id}. Initiator: {initiator_kpi_spec_id}"
    )

    kpis_needing_repartition_update = set()
    kpis_with_formula_target1 = []
    kpis_with_formula_target2 = []

    # Phase 1: Save all definitions from UI, including formula structure and non-formula based targets
    print("  Phase 1: Saving initial target definitions...")
    with sqlite3.connect(db_targets_path) as conn:
        cursor = conn.cursor()
        for kpi_spec_id_str, data_dict_from_ui in targets_data_map.items():
            try:
                current_kpi_spec_id = int(kpi_spec_id_str)
            except ValueError:
                print(
                    f"    WARN: Skipping invalid kpi_spec_id string: '{kpi_spec_id_str}'"
                )
                continue

            # Fetch existing record to get current DB state or defaults if no record
            record = get_annual_target_entry(year, stabilimento_id, current_kpi_spec_id)

            # Initialize with defaults, then override with DB record, then override with UI data
            db_annual_t1, db_annual_t2 = 0.0, 0.0
            db_repart_logic = REPARTITION_LOGIC_ANNO
            db_repart_values_json = "{}"
            db_dist_profile = PROFILE_ANNUAL_PROGRESSIVE
            db_profile_params_json = "{}"
            db_is_manual1, db_is_manual2 = (
                True,
                True,
            )  # Default to manual if not specified
            db_t1_is_formula, db_t1_formula_str, db_t1_formula_inputs_json = (
                False,
                None,
                "[]",
            )
            db_t2_is_formula, db_t2_formula_str, db_t2_formula_inputs_json = (
                False,
                None,
                "[]",
            )

            if record:  # If record exists, load its values
                record_dict = dict(
                    record
                )  # Convert sqlite3.Row to dict for easier access
                db_annual_t1 = float(record_dict.get("annual_target1", 0.0) or 0.0)
                db_annual_t2 = float(record_dict.get("annual_target2", 0.0) or 0.0)
                db_repart_logic = (
                    record_dict.get("repartition_logic", REPARTITION_LOGIC_ANNO)
                    or REPARTITION_LOGIC_ANNO
                )
                db_repart_values_json = (
                    record_dict.get("repartition_values", "{}") or "{}"
                )
                db_dist_profile = (
                    record_dict.get("distribution_profile", PROFILE_ANNUAL_PROGRESSIVE)
                    or PROFILE_ANNUAL_PROGRESSIVE
                )
                db_profile_params_json = record_dict.get("profile_params", "{}") or "{}"
                db_is_manual1 = bool(record_dict.get("is_target1_manual", True))
                db_is_manual2 = bool(record_dict.get("is_target2_manual", True))
                db_t1_is_formula = bool(
                    record_dict.get("target1_is_formula_based", False)
                )
                db_t1_formula_str = record_dict.get("target1_formula")
                db_t1_formula_inputs_json = (
                    record_dict.get("target1_formula_inputs", "[]") or "[]"
                )
                db_t2_is_formula = bool(
                    record_dict.get("target2_is_formula_based", False)
                )
                db_t2_formula_str = record_dict.get("target2_formula")
                db_t2_formula_inputs_json = (
                    record_dict.get("target2_formula_inputs", "[]") or "[]"
                )

            # Get values from UI data_dict, falling back to DB values (or initial defaults)
            final_annual_t1 = (
                float(data_dict_from_ui.get("annual_target1", db_annual_t1))
                if data_dict_from_ui.get("annual_target1") is not None
                else None
            )
            final_annual_t2 = (
                float(data_dict_from_ui.get("annual_target2", db_annual_t2))
                if data_dict_from_ui.get("annual_target2") is not None
                else None
            )
            final_repart_logic = data_dict_from_ui.get(
                "repartition_logic", db_repart_logic
            )
            final_dist_profile = data_dict_from_ui.get(
                "distribution_profile", db_dist_profile
            )

            # For JSON fields, UI provides Python dict/list; convert to JSON string for DB.
            # If UI doesn't provide, use (JSON string loaded from) DB value.
            repart_values_py = data_dict_from_ui.get(
                "repartition_values", json.loads(db_repart_values_json)
            )
            final_repart_values_json = json.dumps(
                repart_values_py if repart_values_py is not None else {}
            )

            profile_params_py = data_dict_from_ui.get(
                "profile_params", json.loads(db_profile_params_json)
            )
            final_profile_params_json = json.dumps(
                profile_params_py if profile_params_py is not None else {}
            )

            final_t1_is_formula = bool(
                data_dict_from_ui.get("target1_is_formula_based", db_t1_is_formula)
            )
            final_t1_formula_str = data_dict_from_ui.get(
                "target1_formula", db_t1_formula_str
            )
            t1_formula_inputs_py = data_dict_from_ui.get(
                "target1_formula_inputs", json.loads(db_t1_formula_inputs_json)
            )
            final_t1_formula_inputs_json = json.dumps(
                t1_formula_inputs_py if t1_formula_inputs_py is not None else []
            )

            final_t2_is_formula = bool(
                data_dict_from_ui.get("target2_is_formula_based", db_t2_is_formula)
            )
            final_t2_formula_str = data_dict_from_ui.get(
                "target2_formula", db_t2_formula_str
            )
            t2_formula_inputs_py = data_dict_from_ui.get(
                "target2_formula_inputs", json.loads(db_t2_formula_inputs_json)
            )
            final_t2_formula_inputs_json = json.dumps(
                t2_formula_inputs_py if t2_formula_inputs_py is not None else []
            )

            # is_manual flag logic: if formula is used, it's not manual. Otherwise, take UI or DB value.
            final_is_manual1 = (
                False
                if final_t1_is_formula
                else bool(data_dict_from_ui.get("is_target1_manual", db_is_manual1))
            )
            final_is_manual2 = (
                False
                if final_t2_is_formula
                else bool(data_dict_from_ui.get("is_target2_manual", db_is_manual2))
            )

            # Persist to DB
            if record:
                cursor.execute(
                    """UPDATE annual_targets SET annual_target1=?, annual_target2=?,
                       repartition_logic=?, repartition_values=?, distribution_profile=?, profile_params=?,
                       is_target1_manual=?, is_target2_manual=?,
                       target1_is_formula_based=?, target1_formula=?, target1_formula_inputs=?,
                       target2_is_formula_based=?, target2_formula=?, target2_formula_inputs=?
                       WHERE id=?""",
                    (
                        final_annual_t1,
                        final_annual_t2,
                        final_repart_logic,
                        final_repart_values_json,
                        final_dist_profile,
                        final_profile_params_json,
                        1 if final_is_manual1 else 0,
                        1 if final_is_manual2 else 0,
                        1 if final_t1_is_formula else 0,
                        final_t1_formula_str,
                        final_t1_formula_inputs_json,
                        1 if final_t2_is_formula else 0,
                        final_t2_formula_str,
                        final_t2_formula_inputs_json,
                        record["id"],
                    ),
                )
            else:
                cursor.execute(
                    """INSERT INTO annual_targets (year,stabilimento_id,kpi_id,annual_target1,annual_target2,
                       repartition_logic,repartition_values,distribution_profile,profile_params,
                       is_target1_manual, is_target2_manual,
                       target1_is_formula_based, target1_formula, target1_formula_inputs,
                       target2_is_formula_based, target2_formula, target2_formula_inputs)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        year,
                        stabilimento_id,
                        current_kpi_spec_id,
                        final_annual_t1,
                        final_annual_t2,
                        final_repart_logic,
                        final_repart_values_json,
                        final_dist_profile,
                        final_profile_params_json,
                        1 if final_is_manual1 else 0,
                        1 if final_is_manual2 else 0,
                        1 if final_t1_is_formula else 0,
                        final_t1_formula_str,
                        final_t1_formula_inputs_json,
                        1 if final_t2_is_formula else 0,
                        final_t2_formula_str,
                        final_t2_formula_inputs_json,
                    ),
                )
            kpis_needing_repartition_update.add(current_kpi_spec_id)
            if final_t1_is_formula:
                kpis_with_formula_target1.append(current_kpi_spec_id)
            if final_t2_is_formula:
                kpis_with_formula_target2.append(current_kpi_spec_id)
        conn.commit()
    print("  Phase 1: Initial target definitions saved.")

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
                    year, stabilimento_id, kpi_id_to_calc
                )
                if not target_entry_row:
                    print(
                        f"      WARN: Target entry not found for KPI {kpi_id_to_calc} during formula calc T{target_num_to_calculate}. Skipping."
                    )
                    continue
                target_entry = dict(target_entry_row)

                is_formula_flag_db = bool(
                    target_entry.get(
                        f"target{target_num_to_calculate}_is_formula_based", False
                    )
                )
                formula_str_db = target_entry.get(
                    f"target{target_num_to_calculate}_formula"
                )
                formula_inputs_json_db = (
                    target_entry.get(
                        f"target{target_num_to_calculate}_formula_inputs", "[]"
                    )
                    or "[]"
                )

                if not (
                    is_formula_flag_db and formula_str_db
                ):  # JSON inputs can be empty if no vars
                    # This KPI was marked for formula calc but definition is missing/corrupt
                    print(
                        f"      WARN: KPI {kpi_id_to_calc} T{target_num_to_calculate} marked as formula but definition incomplete. Skipping."
                    )
                    continue

                try:
                    formula_inputs_def_py = json.loads(formula_inputs_json_db)
                    if not isinstance(formula_inputs_def_py, list):
                        formula_inputs_def_py = []
                except (json.JSONDecodeError, TypeError):
                    print(
                        f"      WARN: KPI {kpi_id_to_calc} T{target_num_to_calculate} has invalid JSON for formula_inputs ('{formula_inputs_json_db}'). Skipping."
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
                            year, stabilimento_id, input_kpi_id
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
                        year, stabilimento_id, input_kpi_id
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
                    calculated_value = _placeholder_safe_evaluate_formula(
                        formula_str_db, context_vars
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
                    kpis_needing_repartition_update.add(
                        kpi_id_to_calc
                    )  # Mark for repartition
                    made_progress_in_iteration = True
                except Exception as e_eval:
                    print(
                        f"      ERROR: Formula calculation failed for KPI {kpi_id_to_calc} T{target_num_to_calculate}: {e_eval}. Formula: '{formula_str_db}', Inputs: {context_vars}"
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
    if initiator_kpi_spec_id:  # If a specific KPI triggered this save
        role_info = get_kpi_role_details(initiator_kpi_spec_id)
        if role_info["role"] == "master":
            masters_to_re_evaluate.add(initiator_kpi_spec_id)
        elif role_info["role"] == "sub" and role_info.get("master_id"):
            masters_to_re_evaluate.add(role_info["master_id"])

    # Also check all KPIs involved in the current save operation (targets_data_map)
    # or those that had formulas calculated.
    all_kpi_ids_in_map_or_formula = (
        {int(k) for k in targets_data_map.keys()}
        .union(kpis_with_formula_target1)
        .union(kpis_with_formula_target2)
    )
    for kpi_id_eval in all_kpi_ids_in_map_or_formula:
        role_info = get_kpi_role_details(kpi_id_eval)
        if role_info["role"] == "master":
            masters_to_re_evaluate.add(kpi_id_eval)
        elif role_info["role"] == "sub" and role_info.get("master_id"):
            masters_to_re_evaluate.add(role_info["master_id"])

    print(
        f"    Identified Master KPIs for potential re-distribution: {masters_to_re_evaluate}"
    )

    for master_kpi_id in masters_to_re_evaluate:
        print(f"    Evaluating Master KPI {master_kpi_id} for weighted distribution...")
        master_target_entry_row = get_annual_target_entry(
            year, stabilimento_id, master_kpi_id
        )
        if not master_target_entry_row:
            print(
                f"      WARN: No annual target entry found for Master KPI {master_kpi_id}. Skipping its distribution."
            )
            continue
        master_target_entry = dict(master_target_entry_row)

        # Get sub-KPIs and their weights
        sub_kpi_links_with_weights = (
            []
        )  # List of dicts: {'sub_kpi_spec_id': id, 'weight': float}
        raw_sub_kpi_ids_for_master = get_sub_kpis_for_master(
            master_kpi_id
        )  # This just gets IDs

        if not raw_sub_kpi_ids_for_master:
            print(
                f"      Master KPI {master_kpi_id} has no linked sub-KPIs. No distribution needed."
            )
            continue

        with sqlite3.connect(app_config.get_database_path("db_kpis.db")) as conn_weights:  # Query db_kpis.db for weights
            conn_weights.row_factory = sqlite3.Row
            for sub_id_from_retriever in raw_sub_kpi_ids_for_master:
                link_row = conn_weights.execute(
                    "SELECT sub_kpi_spec_id, distribution_weight FROM kpi_master_sub_links WHERE master_kpi_spec_id = ? AND sub_kpi_spec_id = ?",
                    (master_kpi_id, sub_id_from_retriever),
                ).fetchone()
                if link_row:
                    sub_kpi_links_with_weights.append(
                        {
                            "sub_kpi_spec_id": link_row["sub_kpi_spec_id"],
                            "weight": float(link_row["distribution_weight"]),
                        }
                    )
                else:  # Should ideally not happen if data_retriever is consistent with db_kpis.db
                    print(
                        f"      WARN: Weight not found for link Master {master_kpi_id} to Sub {sub_id_from_retriever}. Assuming weight 1.0."
                    )
                    sub_kpi_links_with_weights.append(
                        {"sub_kpi_spec_id": sub_id_from_retriever, "weight": 1.0}
                    )

        if not sub_kpi_links_with_weights:  # Redundant check, but safe
            continue

        print(
            f"      Master KPI {master_kpi_id} has sub-links: {sub_kpi_links_with_weights}"
        )

        for target_num_to_distribute in [
            1,
            2,
        ]:  # Process for annual_target1 and annual_target2
            master_target_value = master_target_entry.get(
                f"annual_target{target_num_to_distribute}"
            )
            if master_target_value is None:
                print(
                    f"      Master KPI {master_kpi_id} Target {target_num_to_distribute} is not set. Skipping distribution for this target."
                )
                continue
            master_target_value = float(master_target_value)

            sum_of_fixed_sub_targets = (
                0.0  # Sum of sub-targets that are manual or formula-based
            )
            distributable_sub_kpis = (
                []
            )  # List of {'id': sub_id, 'weight': float} for subs eligible for distribution
            total_weight_for_distribution = 0.0

            for sub_link_info in sub_kpi_links_with_weights:
                sub_kpi_id = sub_link_info["sub_kpi_spec_id"]
                sub_kpi_weight = sub_link_info["weight"]
                if not (
                    isinstance(sub_kpi_weight, (int, float)) and sub_kpi_weight > 0
                ):
                    sub_kpi_weight = 1.0  # Ensure positive weight

                sub_target_entry_row = get_annual_target_entry(
                    year, stabilimento_id, sub_kpi_id
                )
                sub_target_value_this_target = (
                    0.0  # Default if no entry or target not set
                )
                is_sub_manual_this_target = (
                    False  # Default to not manual (i.e., eligible for derivation)
                )
                is_sub_formula_based_this_target = False

                if sub_target_entry_row:
                    sub_target_entry = dict(sub_target_entry_row)
                    sub_target_value_this_target = float(
                        sub_target_entry.get(
                            f"annual_target{target_num_to_distribute}", 0.0
                        )
                        or 0.0
                    )
                    is_sub_manual_this_target = bool(
                        sub_target_entry.get(
                            f"is_target{target_num_to_distribute}_manual", False
                        )
                    )
                    is_sub_formula_based_this_target = bool(
                        sub_target_entry.get(
                            f"target{target_num_to_distribute}_is_formula_based", False
                        )
                    )

                if (
                    is_sub_formula_based_this_target
                ):  # Formula-based subs are fixed contributors
                    sum_of_fixed_sub_targets += sub_target_value_this_target
                elif (
                    is_sub_manual_this_target
                ):  # Manually set subs are fixed contributors
                    sum_of_fixed_sub_targets += sub_target_value_this_target
                else:  # Eligible for derivation from master
                    distributable_sub_kpis.append(
                        {"id": sub_kpi_id, "weight": sub_kpi_weight}
                    )
                    total_weight_for_distribution += sub_kpi_weight

            remaining_target_for_distribution = (
                master_target_value - sum_of_fixed_sub_targets
            )
            print(
                f"        For Master {master_kpi_id} T{target_num_to_distribute} ({master_target_value}): Fixed subs sum to {sum_of_fixed_sub_targets}. Remaining for dist: {remaining_target_for_distribution}."
            )
            print(
                f"        Distributable subs: {distributable_sub_kpis}, total weight: {total_weight_for_distribution}"
            )

            if distributable_sub_kpis:
                with sqlite3.connect(db_targets_path) as conn_update_subs:
                    cursor_update_subs = conn_update_subs.cursor()
                    for sub_info_to_derive in distributable_sub_kpis:
                        sub_kpi_id_to_derive = sub_info_to_derive["id"]
                        sub_weight_for_derive = sub_info_to_derive["weight"]
                        value_for_this_sub = 0.0
                        if (
                            total_weight_for_distribution > 1e-9
                        ):  # Avoid division by zero
                            value_for_this_sub = (
                                sub_weight_for_derive / total_weight_for_distribution
                            ) * remaining_target_for_distribution
                        elif (
                            remaining_target_for_distribution != 0
                            and len(distributable_sub_kpis) > 0
                        ):  # If total weight is somehow zero, distribute evenly
                            value_for_this_sub = (
                                remaining_target_for_distribution
                                / len(distributable_sub_kpis)
                            )

                        # Update or Insert the derived value for the sub-KPI
                        sub_record_derive_row = get_annual_target_entry(
                            year, stabilimento_id, sub_kpi_id_to_derive
                        )
                        target_col_to_update = (
                            f"annual_target{target_num_to_distribute}"
                        )
                        manual_flag_col_to_update = (
                            f"is_target{target_num_to_distribute}_manual"
                        )
                        formula_flag_col_to_update = (
                            f"target{target_num_to_distribute}_is_formula_based"
                        )

                        if sub_record_derive_row:
                            # Update existing record: set target value, set manual=False, set formula=False
                            cursor_update_subs.execute(
                                f"""UPDATE annual_targets SET {target_col_to_update}=?, {manual_flag_col_to_update}=?, {formula_flag_col_to_update}=?
                                    WHERE id=?""",
                                (
                                    value_for_this_sub,
                                    False,
                                    False,
                                    sub_record_derive_row["id"],
                                ),
                            )
                        else:  # Insert new record for this sub-KPI
                            # Need to handle the *other* target field as well if inserting new
                            other_target_num = 1 if target_num_to_distribute == 2 else 2
                            default_val_other_target = 0.0
                            default_manual_other_target = (
                                True  # Or False, depending on desired default
                            )
                            default_formula_other_target = False

                            # Construct columns and placeholders carefully
                            cols_list = [
                                "year",
                                "stabilimento_id",
                                "kpi_id",
                                f"annual_target{target_num_to_distribute}",
                                f"is_target{target_num_to_distribute}_manual",
                                f"target{target_num_to_distribute}_is_formula_based",
                                f"annual_target{other_target_num}",
                                f"is_target{other_target_num}_manual",
                                f"target{other_target_num}_is_formula_based",
                                "repartition_logic",
                                "repartition_values",
                                "distribution_profile",
                                "profile_params",
                            ]
                            values_to_insert = [
                                year,
                                stabilimento_id,
                                sub_kpi_id_to_derive,
                                value_for_this_sub,
                                False,
                                False,  # Current target being derived
                                default_val_other_target,
                                default_manual_other_target,
                                default_formula_other_target,  # Other target defaults
                                REPARTITION_LOGIC_ANNO,
                                "{}",
                                PROFILE_ANNUAL_PROGRESSIVE,
                                "{}",  # Default repart/profile
                            ]
                            cols_str = ", ".join(cols_list)
                            placeholders_str = ", ".join(["?"] * len(cols_list))
                            cursor_update_subs.execute(
                                f"INSERT INTO annual_targets ({cols_str}) VALUES ({placeholders_str})",
                                tuple(values_to_insert),
                            )
                        kpis_needing_repartition_update.add(sub_kpi_id_to_derive)
                        print(
                            f"          SubKPI {sub_kpi_id_to_derive} T{target_num_to_distribute} derived (from master {master_kpi_id}, weight {sub_weight_for_derive}): {value_for_this_sub:.2f}"
                        )
                    conn_update_subs.commit()
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
                year, stabilimento_id, kpi_id_recalc
            )
            if target_entry_check_row:
                target_entry_check = dict(target_entry_check_row)
                # Check if target1 exists and is not None before calculating its repartition
                if target_entry_check.get("annual_target1") is not None:
                    print(
                        f"    Calculating repartitions for KPI {kpi_id_recalc}, Target 1..."
                    )
                    calculate_and_save_all_repartitions(
                        year, stabilimento_id, kpi_id_recalc, 1
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
                    calculate_and_save_all_repartitions(
                        year, stabilimento_id, kpi_id_recalc, 2
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
        f"INFO: Finished save_annual_targets for Year: {year}, Stab: {stabilimento_id}"
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
    # Overwrite global flags for the scope of this test
    _data_retriever_available_orig = _data_retriever_available
    _repartition_module_available_orig = _repartition_module_available
    _data_retriever_available = True
    _repartition_module_available = True

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
    _mock_annual_targets_db = {}  # {(year, stab_id, kpi_id): {data}}
    _mock_kpis_links_db = {}  # {master_id: [sub_ids]}
    _mock_kpis_roles_db = (
        {}
    )  # {kpi_id: {"role": "master/sub/none", "master_id": id, "related_kpis": [ids]}}
    _mock_kpis_link_weights = {}  # {(master_id, sub_id): weight}

    def _mock_get_annual_target_entry(year, stab_id, kpi_id):
        return _mock_annual_targets_db.get((year, stab_id, kpi_id))

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
    calculate_and_save_all_repartitions_orig = calculate_and_save_all_repartitions

    get_annual_target_entry = _mock_get_annual_target_entry
    get_kpi_role_details = _mock_get_kpi_role_details
    get_sub_kpis_for_master = _mock_get_sub_kpis_for_master
    # calculate_and_save_all_repartitions is already mocked if module isn't found,
    # but we can provide a more verbose mock for testing:
    _repartition_calls = []

    def _verbose_mock_repartition(year, stab_id, kpi_id, target_num):
        call_info = (year, stab_id, kpi_id, target_num)
        print(f"  MOCK REPARTITION CALLED: {call_info}")
        _repartition_calls.append(call_info)

    calculate_and_save_all_repartitions = _verbose_mock_repartition

    # Setup minimal DB_TARGETS table schema for the test
    with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn:
        conn.execute("DROP TABLE IF EXISTS annual_targets;")
        conn.execute(
            f"""
            CREATE TABLE annual_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER, stabilimento_id INTEGER, kpi_id INTEGER,
                annual_target1 REAL, annual_target2 REAL,
                repartition_logic TEXT, repartition_values TEXT, distribution_profile TEXT, profile_params TEXT,
                is_target1_manual BOOLEAN, is_target2_manual BOOLEAN,
                target1_is_formula_based BOOLEAN, target1_formula TEXT, target1_formula_inputs TEXT,
                target2_is_formula_based BOOLEAN, target2_formula TEXT, target2_formula_inputs TEXT,
                UNIQUE(year, stabilimento_id, kpi_id));
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
        test_stab_id = 1
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

        save_annual_targets(test_year, test_stab_id, targets_input_scenario1)

        # Verification for Scenario 1 (check the SQLite DB_TARGETS_TEST_FILE)
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn_verify:
            conn_verify.row_factory = sqlite3.Row
            c_target_row = conn_verify.execute(
                "SELECT annual_target1, is_target1_manual FROM annual_targets WHERE year=? AND stabilimento_id=? AND kpi_id=?",
                (test_year, test_stab_id, kpi_c_id),
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
        assert (test_year, test_stab_id, kpi_a_id, 1) in _repartition_calls
        assert (test_year, test_stab_id, kpi_b_id, 1) in _repartition_calls
        assert (test_year, test_stab_id, kpi_c_id, 1) in _repartition_calls
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
            test_stab_id,
            targets_input_scenario2,
            initiator_kpi_spec_id=master_id,
        )

        # Verification for Scenario 2
        with sqlite3.connect(app_config.get_database_path("db_kpi_targets.db")) as conn_verify:
            conn_verify.row_factory = sqlite3.Row
            sub2_target_row = conn_verify.execute(
                "SELECT annual_target1, is_target1_manual FROM annual_targets WHERE year=? AND stabilimento_id=? AND kpi_id=?",
                (test_year, test_stab_id, sub2_id),
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

        assert (test_year, test_stab_id, master_id, 1) in _repartition_calls
        assert (test_year, test_stab_id, sub1_id, 1) in _repartition_calls
        assert (test_year, test_stab_id, sub2_id, 1) in _repartition_calls
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
        _data_retriever_available = _data_retriever_available_orig
        _repartition_module_available = _repartition_module_available_orig

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