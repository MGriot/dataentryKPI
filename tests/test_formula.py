import pytest

from src.core.formula import FormulaError, compile_formula, evaluate_formula, referenced_kpis
from src.core.node_engine import KpiDAG


def test_basic_arithmetic_and_refs():
    assert evaluate_formula("([1] + [2]) / 2", {1: 10, 2: 30}) == 20
    assert evaluate_formula("max([1], 5) - abs(-2) + round(2.6)", {1: 1}) == 6
    assert evaluate_formula("[ 7 ] ** 2 % 5", {7: 3}) == 4
    assert referenced_kpis("[1] + [ 22 ] * [1]") == {1, 22}


def test_division_by_zero_yields_configured_value():
    assert evaluate_formula("[1] / [2]", {1: 5, 2: 0}) == 0.0
    assert compile_formula("[1] / [2]").evaluate({1: 5, 2: 0}, zero_division_value=-1) == -1


@pytest.mark.parametrize("payload", [
    "().__class__.__base__.__subclasses__()",
    "().__class__",
    "__import__('os').system('echo hi')",
    "open('x')",
    "[1].real",
    "'abc'",
    "[x for x in (1, 2)]",
    "lambda: 1",
    "max(1, key=abs)",
    "True + 1",
    "{}",
    "[1][0]",
])
def test_rejects_anything_outside_the_whitelist(payload):
    with pytest.raises(FormulaError):
        compile_formula(payload)


def test_rejects_huge_exponents_and_missing_inputs():
    with pytest.raises(FormulaError):
        evaluate_formula("9 ** 9 ** 9", {})
    with pytest.raises(FormulaError):
        evaluate_formula("[1] + [2]", {1: 1})
    with pytest.raises(FormulaError):
        evaluate_formula("x" * 5000, {})


def test_dag_abs_cycle_and_pow_guards():
    dag = KpiDAG.from_formula("abs([1] - [2])")
    assert dag.evaluate(lambda kid, tn: {1: 2.0, 2: 5.0}[kid]) == 3.0

    cyclic = KpiDAG.from_json(
        '{"nodes": [{"id": "a", "type": "operator", "data": {"op": "+"}}, {"id": "o", "type": "output", "data": {}}],'
        ' "edges": [{"id": "1", "source": "a", "target": "a"}, {"id": "2", "source": "a", "target": "o"}]}'
    )
    with pytest.raises(ValueError):
        cyclic.evaluate(lambda kid, tn: 1.0)

    with pytest.raises(ValueError):
        KpiDAG.from_formula("[1] ** 1000").evaluate(lambda kid, tn: 2.0)
