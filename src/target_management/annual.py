# src/target_management/annual.py
"""
Annual target saving and the recalculation pipeline.

A save (or a split/formula change) runs, inside ONE transaction spanning the targets,
periodic and history databases:
  1. write the entered annual values (+ audit rows),
  2. recompute calculated (formula) KPIs that depend -- directly or transitively -- on what
     changed, in dependency order,
  3. repartition every affected KPI into day/week/month/quarter targets.
If anything fails, nothing is committed.

Formulas live on the KPI (KPI Explorer): `formula_string` like "[12] / [13]" (target N of a
calculated KPI is computed from target N of its inputs) or a `formula_json` DAG whose input
nodes may pin a specific target number. Calculated KPIs can't be entered manually.
"""
import json
import logging
from typing import Dict, Iterable, List, Optional, Set

import numpy as np

from src import data_retriever
from src.config.constants import is_additive
from src.core.formula import FormulaError, compile_formula, referenced_kpis
from src.core.node_engine import KpiDAG
from src.data_access import db
from src.kpi_management import splits as splits_crud
from src.services import history_service
from src.target_management import repartition

log = logging.getLogger(__name__)

_CONFIG_COLUMNS = ("repartition_logic", "repartition_values", "distribution_profile", "profile_params", "global_split_id")


class TargetValidationError(ValueError):
    """Bad input for a target save (unknown KPI/plant, manual value for a calculated KPI, ...)."""


# --- Formula dependency graph ---

def _dag_for(spec: dict) -> Optional[KpiDAG]:
    raw = spec.get("formula_json")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return KpiDAG.from_json(raw) if isinstance(parsed, dict) and parsed.get("nodes") else None


def kpi_dependencies(spec: dict) -> Set[int]:
    dag = _dag_for(spec)
    if dag is not None:
        return {int(d["kpi_id"]) for d in dag.find_all_kpi_dependencies() if d.get("kpi_id") is not None}
    return referenced_kpis(spec.get("formula_string") or "")


def formula_graph(specs: Dict[int, dict]) -> Dict[int, Set[int]]:
    """{calculated kpi id: {ids it depends on}}"""
    return {kid: kpi_dependencies(s) for kid, s in specs.items() if s.get("is_calculated")}


def find_cycle(graph: Dict[int, Set[int]], start: Optional[int] = None) -> Optional[List[int]]:
    """A dependency cycle (as a list of KPI ids) reachable in graph, or None."""
    visiting, done = [], set()

    def visit(node) -> Optional[List[int]]:
        if node in visiting:
            return visiting[visiting.index(node):] + [node]
        if node in done:
            return None
        visiting.append(node)
        for dep in graph.get(node, ()):
            cycle = visit(dep)
            if cycle:
                return cycle
        visiting.pop()
        done.add(node)
        return None

    for node in ([start] if start is not None else list(graph)):
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def _dependents_closure(graph: Dict[int, Set[int]], seeds: Iterable[int]) -> Set[int]:
    affected = set(seeds)
    changed = True
    while changed:
        changed = False
        for kid, deps in graph.items():
            if kid not in affected and deps & affected:
                affected.add(kid)
                changed = True
    return affected


def _topo_order(graph: Dict[int, Set[int]], nodes: Set[int]) -> List[int]:
    """Dependencies first. KPIs that are part of a cycle are skipped (and logged)."""
    order, state = [], {}

    def visit(node) -> bool:
        if state.get(node) == "done":
            return True
        if state.get(node) == "visiting":
            return False
        state[node] = "visiting"
        ok = all(visit(dep) for dep in graph.get(node, ()) if dep in nodes)
        state[node] = "done" if ok else "cycle"
        if ok:
            order.append(node)
        else:
            log.warning("KPI %s is part of a formula cycle; skipped", node)
        return ok

    for node in sorted(nodes):
        visit(node)
    return order


def validate_formula(kpi_id: int, formula_string: Optional[str], specs: Optional[Dict[int, dict]] = None):
    """Raises FormulaError if formula_string is invalid, references unknown KPIs, or creates a cycle."""
    if not (formula_string or "").strip():
        return
    compiled = compile_formula(formula_string)
    specs = specs if specs is not None else {k["id"]: k for k in data_retriever.get_all_kpis_detailed()}
    unknown = sorted(i for i in compiled.kpi_ids if i not in specs)
    if unknown:
        raise FormulaError(f"Formula references unknown KPI id(s): {unknown}")
    if kpi_id in compiled.kpi_ids:
        raise FormulaError("A KPI's formula can't reference itself")
    graph = formula_graph(specs)
    graph[kpi_id] = set(compiled.kpi_ids)
    cycle = find_cycle(graph, kpi_id)
    if cycle:
        raise FormulaError(f"Formula would create a dependency cycle: {' -> '.join(f'[{c}]' for c in cycle)}")


# --- Save ---

def _parse_inputs(targets_data_map: dict, specs: Dict[int, dict]) -> Dict[int, dict]:
    parsed = {}
    for key, data in (targets_data_map or {}).items():
        try:
            kpi_id = int(key)
        except (TypeError, ValueError):
            raise TargetValidationError(f"Invalid KPI id '{key}'") from None
        spec = specs.get(kpi_id)
        if not spec:
            raise TargetValidationError(f"KPI {kpi_id} not found (or deleted)")
        data = data or {}

        targets = list(data.get("targets") or [])
        for tn in (1, 2):  # legacy flat fields: annual_target1 / annual_target2
            if f"annual_target{tn}" in data and not any(t.get("target_number") == tn for t in targets):
                targets.append({"target_number": tn, "target_value": data[f"annual_target{tn}"]})

        values = {}
        max_targets = max(int(spec.get("target_count") or 1), 1)
        for t in targets:
            if t.get("is_formula_based") or t.get("formula"):
                raise TargetValidationError(
                    "Per-target formulas are no longer supported; set the formula on the KPI in KPI Explorer."
                )
            try:
                tn = int(t.get("target_number", 1))
            except (TypeError, ValueError):
                raise TargetValidationError("target_number must be an integer") from None
            if not 1 <= tn <= max_targets:
                raise TargetValidationError(f"KPI {kpi_id} has {max_targets} target(s); target_number {tn} is out of range")
            value = t.get("target_value")
            if value is None or value == "":
                continue  # left blank -> keep whatever is stored
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise TargetValidationError(f"Target value for KPI {kpi_id} must be a number") from None
            if not np.isfinite(value):
                raise TargetValidationError(f"Target value for KPI {kpi_id} must be finite")
            if spec.get("is_calculated"):
                raise TargetValidationError(
                    f"'{spec['indicator_name']}' is calculated from its formula; its targets can't be entered manually."
                )
            values[tn] = value

        config = {}
        for col in _CONFIG_COLUMNS:
            if data.get(col) is not None:
                config[col] = data[col]
        if config:
            values_obj = config.get("repartition_values")
            params_obj = config.get("profile_params")
            if isinstance(values_obj, str):
                values_obj = data_retriever.parse_json_field(values_obj, {})
            if isinstance(params_obj, str):
                params_obj = data_retriever.parse_json_field(params_obj, {})
            splits_crud._validate(config.get("repartition_logic"), config.get("distribution_profile"),
                                  values_obj if "repartition_values" in config else None,
                                  params_obj if "profile_params" in config else None)
            if "repartition_values" in config:
                config["repartition_values"] = json.dumps(values_obj)
            if "profile_params" in config:
                config["profile_params"] = json.dumps(params_obj)
        parsed[kpi_id] = {"values": values, "config": config}
    return parsed


def _ensure_annual_row(conn, year: int, plant_id: int, kpi_id: int, config: Optional[dict] = None) -> int:
    row = conn.execute(
        "SELECT id FROM annual_targets WHERE year=? AND plant_id=? AND kpi_id=?", (year, plant_id, kpi_id)
    ).fetchone()
    config = config or {}
    if row:
        if config:
            sets = ", ".join(f"{db.ident(c)} = ?" for c in config)
            conn.execute(f"UPDATE annual_targets SET {sets} WHERE id = ?", (*config.values(), row["id"]))
        return row["id"]
    cols = ["year", "plant_id", "kpi_id", *config.keys()]
    return conn.execute(
        f"INSERT INTO annual_targets ({', '.join(db.ident(c) for c in cols)}) VALUES ({', '.join('?' * len(cols))})",
        (year, plant_id, kpi_id, *config.values()),
    ).lastrowid


def _upsert_value(conn, annual_id: int, kpi_id: int, year: int, plant_id: int, tn: int, value: float,
                  is_formula: bool, changed_by: str):
    old = conn.execute(
        "SELECT target_value FROM kpi_annual_target_values WHERE annual_target_id=? AND target_number=?", (annual_id, tn)
    ).fetchone()
    conn.execute(
        """INSERT INTO kpi_annual_target_values
           (annual_target_id, target_number, target_value, is_manual, is_formula_based, formula, formula_inputs)
           VALUES (?, ?, ?, ?, ?, NULL, '[]')
           ON CONFLICT(annual_target_id, target_number) DO UPDATE SET
             target_value=excluded.target_value, is_manual=excluded.is_manual,
             is_formula_based=excluded.is_formula_based, formula=NULL, formula_inputs='[]'""",
        (annual_id, tn, value, 0 if is_formula else 1, 1 if is_formula else 0),
    )
    old_value = old["target_value"] if old else None
    if old_value is None or abs(old_value - value) > 1e-9:
        history_service.record_target_change(
            kpi_id=kpi_id, plant_id=plant_id, target_number=tn,
            period_start=f"{year}-01-01", period_end=f"{year}-12-31",
            old_value=old_value, new_value=value,
            changed_by=f"{changed_by} (formula)" if is_formula else changed_by,
            conn=conn, schema=repartition.HISTORY_SCHEMA,
        )


def _existing_plant_ids() -> Set[int]:
    return {p["id"] for p in data_retriever.get_all_plants()}


def save_annual_targets(
    year: int,
    plant_id,
    targets_data_map: dict,
    initiator_kpi_spec_id: int = None,
    changed_by: str = "system",
):
    """Saves annual targets for one or more plants and recalculates everything that depends on them.

    targets_data_map: {kpi_id: {"targets": [{"target_number": n, "target_value": v}, ...],
                                optional "repartition_logic"/"repartition_values"/... legacy config}}
    Blank (None) values leave the stored value untouched.
    """
    if not targets_data_map:
        return
    try:
        year = int(year)
    except (TypeError, ValueError):
        raise TargetValidationError("year must be an integer") from None
    if not 1900 <= year <= 2200:
        raise TargetValidationError("year is out of range")
    plant_ids = [plant_id] if isinstance(plant_id, int) else list(dict.fromkeys(plant_id or []))
    if not plant_ids:
        raise TargetValidationError("No plant selected")
    missing = set(plant_ids) - _existing_plant_ids()
    if missing:
        raise TargetValidationError(f"Plant(s) not found: {sorted(missing)}")

    specs = {k["id"]: k for k in data_retriever.get_all_kpis_detailed()}
    parsed = _parse_inputs(targets_data_map, specs)

    with repartition.engine_connection() as conn:
        for pid in plant_ids:
            for kpi_id, item in parsed.items():
                if not item["values"] and not item["config"]:
                    continue
                annual_id = _ensure_annual_row(conn, year, pid, kpi_id, item["config"])
                for tn, value in item["values"].items():
                    _upsert_value(conn, annual_id, kpi_id, year, pid, tn, value, False, changed_by)
            _recalculate_in_tx(conn, year, pid, set(parsed), specs, changed_by)


# --- Recalculation ---

def _annual_value(conn, year: int, plant_id: int, kpi_id: int, tn: int) -> Optional[float]:
    row = conn.execute(
        "SELECT v.target_value FROM kpi_annual_target_values v JOIN annual_targets t ON v.annual_target_id = t.id "
        "WHERE t.year=? AND t.plant_id=? AND t.kpi_id=? AND v.target_number=?",
        (year, plant_id, kpi_id, tn),
    ).fetchone()
    return None if row is None or row["target_value"] is None else float(row["target_value"])


def _compute_formula_annual(conn, year: int, plant_id: int, spec: dict, changed_by: str):
    kid = spec["id"]
    dag = _dag_for(spec)
    compiled = None
    if dag is None:
        try:
            compiled = compile_formula(spec.get("formula_string"))
        except FormulaError as e:
            log.warning("KPI %s has an invalid formula (%s); skipped", kid, e)
            return

    for tn in range(1, max(int(spec.get("target_count") or 1), 1) + 1):
        try:
            if dag is not None:
                def resolver(dep_id, dep_tn, _tn=tn):
                    v = _annual_value(conn, year, plant_id, int(dep_id), int(dep_tn or _tn))
                    if v is None:
                        raise KeyError(dep_id)
                    return v
                value = dag.evaluate(resolver, default_target_num=tn)
            else:
                inputs = {dep: _annual_value(conn, year, plant_id, dep, tn) for dep in compiled.kpi_ids}
                if any(v is None for v in inputs.values()):
                    continue  # inputs not entered yet for this plant/year/target
                value = compiled.evaluate(inputs)
        except KeyError:
            continue
        except (FormulaError, ValueError) as e:
            log.warning("Formula for KPI %s target %s could not be evaluated: %s", kid, tn, e)
            continue
        annual_id = _ensure_annual_row(conn, year, plant_id, kid)
        _upsert_value(conn, annual_id, kid, year, plant_id, tn, value, True, changed_by)


def _formula_daily_series(conn, year: int, plant_id: int, spec: dict, tn: int) -> Optional[np.ndarray]:
    """Day-by-day formula over the inputs' daily targets (target N of each input), or None if unavailable."""
    dag = _dag_for(spec)
    if dag is not None:
        deps = {(int(d["kpi_id"]), int(d.get("target_num") or tn)) for d in dag.find_all_kpi_dependencies()}
    else:
        try:
            compiled = compile_formula(spec.get("formula_string"))
        except FormulaError:
            return None
        deps = {(dep, tn) for dep in compiled.kpi_ids}
    series = {}
    for dep_id, dep_tn in deps:
        s = repartition.read_daily_series(conn, year, plant_id, dep_id, dep_tn)
        if s is None:
            return None
        series[(dep_id, dep_tn)] = s
    n = len(next(iter(series.values()))) if series else len(repartition.days_of_year(year))
    out = np.zeros(n)
    for i in range(n):
        try:
            if dag is not None:
                out[i] = dag.evaluate(lambda k, t, _i=i: series[(int(k), int(t or tn))][_i], default_target_num=tn)
            else:
                out[i] = compiled.evaluate({dep: series[(dep, tn)][i] for dep in compiled.kpi_ids})
        except (FormulaError, ValueError, KeyError):
            out[i] = 0.0
    return out


def _repartition_kpi(conn, year: int, plant_id: int, spec: dict):
    kid = spec["id"]
    entry = data_retriever.get_annual_target_entry(year, plant_id, kid, conn=conn)
    if not entry:
        repartition.delete_periodic_targets(conn, year, plant_id, kid)
        return
    additive = is_additive(spec.get("calculation_type"))
    for tv in entry["target_values"]:
        tn, value = tv["target_number"], tv["target_value"]
        if value is None:
            repartition.delete_periodic_targets(conn, year, plant_id, kid, tn)
            continue
        if spec.get("is_calculated"):
            series = _formula_daily_series(conn, year, plant_id, spec, tn)
            if series is not None:
                daily = repartition.reconcile(series, float(value), additive)
                dates = repartition.days_of_year(year)
                repartition.save_periodic_targets(conn, year, plant_id, kid, tn, dates, daily, spec["calculation_type"])
                continue
        logic, values, profile, params = repartition.resolve_distribution(
            spec, entry, year, splits_crud.get_split_for_indicator_year
        )
        dates, daily = repartition.compute_daily_values(
            year, float(value), spec["calculation_type"], logic, values, profile, params
        )
        repartition.save_periodic_targets(conn, year, plant_id, kid, tn, dates, daily, spec["calculation_type"])


def _recalculate_in_tx(conn, year: int, plant_id: int, seeds: Set[int], specs: Dict[int, dict], changed_by: str):
    graph = formula_graph(specs)
    affected = _dependents_closure(graph, seeds)
    for kid in _topo_order(graph, affected):
        spec = specs.get(kid)
        if not spec:
            continue
        if spec.get("is_calculated"):
            _compute_formula_annual(conn, year, plant_id, spec, changed_by)
        _repartition_kpi(conn, year, plant_id, spec)


def recalculate_kpis(kpi_ids: Iterable[int], changed_by: str = "system", years: Optional[Iterable[int]] = None):
    """Recomputes formulas + periodic targets for these KPIs (and their dependents) everywhere they have targets.

    Used after a split assignment, a split template edit, or a formula change.
    """
    kpi_ids = {int(k) for k in kpi_ids}
    if not kpi_ids:
        return
    specs = {k["id"]: k for k in data_retriever.get_all_kpis_detailed()}
    affected = _dependents_closure(formula_graph(specs), kpi_ids)
    placeholders = ",".join("?" * len(affected))
    with repartition.engine_connection() as conn:
        pairs = conn.execute(
            f"SELECT DISTINCT year, plant_id FROM annual_targets WHERE kpi_id IN ({placeholders})", tuple(affected)
        ).fetchall()
        wanted_years = set(years) if years is not None else None
        for row in pairs:
            if wanted_years is not None and row["year"] not in wanted_years:
                continue
            _recalculate_in_tx(conn, row["year"], row["plant_id"], kpi_ids, specs, changed_by)


def recalculate_indicators(indicator_ids: Iterable[int], changed_by: str = "system"):
    indicator_ids = {int(i) for i in indicator_ids}
    kpi_ids = [k["id"] for k in data_retriever.get_all_kpis_detailed() if k["indicator_id"] in indicator_ids]
    recalculate_kpis(kpi_ids, changed_by)
