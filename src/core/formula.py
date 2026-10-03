"""
Safe evaluation of KPI formula strings such as "([12] + [13]) / max([14], 1)".

Formulas are parsed with `ast` and evaluated by walking a strict whitelist of node types --
nothing is ever passed to eval(). Allowed: numeric literals, KPI references `[id]`,
+ - * / % ** (bounded), unary +/-, parentheses, and abs/min/max/round. Anything else
(attribute access, subscripts, names, keyword args, comprehensions, strings, ...) is
rejected with FormulaError before evaluation.
"""
import ast
import math
import operator
import re
from typing import Callable, Dict, Mapping, Set

MAX_FORMULA_LENGTH = 2000
MAX_NODES = 300
MAX_EXPONENT = 64
MAX_BASE_FOR_POW = 1e12

_REF = re.compile(r"\[\s*(\d+)\s*\]")
_REF_NAME = re.compile(r"^__kpi_(\d+)$")

_BIN_OPS: Dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS: Dict[str, Callable] = {"abs": abs, "min": min, "max": max, "round": round}


class FormulaError(ValueError):
    pass


def referenced_kpis(formula: str) -> Set[int]:
    """KPI ids referenced as [id] in a formula string."""
    return {int(m) for m in _REF.findall(formula or "")}


class CompiledFormula:
    def __init__(self, source: str, tree: ast.Expression):
        self.source = source
        self._tree = tree
        self.kpi_ids = referenced_kpis(source)

    def evaluate(self, values: Mapping[int, float], zero_division_value: float = 0.0) -> float:
        """Evaluates with {kpi_id: value}. Division by zero yields `zero_division_value`."""
        missing = self.kpi_ids - set(values)
        if missing:
            raise FormulaError(f"Missing values for KPI(s): {sorted(missing)}")
        try:
            result = _eval(self._tree.body, values, zero_division_value)
        except ZeroDivisionError:
            return zero_division_value
        except (OverflowError, ValueError, TypeError) as e:
            raise FormulaError(f"Formula could not be evaluated: {e}") from e
        if not math.isfinite(result):
            raise FormulaError("Formula result is not a finite number")
        return result


def compile_formula(formula: str) -> CompiledFormula:
    if formula is None or not str(formula).strip():
        raise FormulaError("Formula is empty")
    source = str(formula).strip()
    if len(source) > MAX_FORMULA_LENGTH:
        raise FormulaError(f"Formula is longer than {MAX_FORMULA_LENGTH} characters")
    rewritten = _REF.sub(lambda m: f"__kpi_{int(m.group(1))}", source)
    try:
        tree = ast.parse(rewritten, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Invalid formula syntax: {e.msg}") from None
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise FormulaError("Formula is too complex")
    for node in nodes:
        _validate(node)
    return CompiledFormula(source, tree)


def evaluate_formula(formula: str, values: Mapping[int, float], zero_division_value: float = 0.0) -> float:
    return compile_formula(formula).evaluate(values, zero_division_value)


def _validate(node: ast.AST):
    if isinstance(node, (ast.Expression, ast.Load)) or type(node) in _BIN_OPS or type(node) in _UNARY_OPS:
        return
    if isinstance(node, ast.BinOp):
        if type(node.op) not in _BIN_OPS:
            raise FormulaError(f"Operator '{type(node.op).__name__}' is not allowed")
        return
    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _UNARY_OPS:
            raise FormulaError(f"Operator '{type(node.op).__name__}' is not allowed")
        return
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise FormulaError("Only numeric constants are allowed")
        return
    if isinstance(node, ast.Name):
        if _REF_NAME.match(node.id) or node.id in _FUNCTIONS:
            return
        raise FormulaError(f"Unknown name '{node.id}'. Reference KPIs as [id].")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
            raise FormulaError("Only abs(), min(), max() and round() can be called")
        if node.keywords:
            raise FormulaError("Keyword arguments are not allowed")
        if not node.args:
            raise FormulaError(f"{node.func.id}() needs at least one argument")
        return
    raise FormulaError(f"'{type(node).__name__}' is not allowed in formulas")


def _eval(node: ast.AST, values: Mapping[int, float], zdv: float) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        match = _REF_NAME.match(node.id)
        if not match:
            raise FormulaError(f"'{node.id}' must be called, e.g. {node.id}(...)")
        return float(values[int(match.group(1))])
    if isinstance(node, ast.UnaryOp):
        return _UNARY_OPS[type(node.op)](_eval(node.operand, values, zdv))
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, values, zdv)
        right = _eval(node.right, values, zdv)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_EXPONENT or abs(left) > MAX_BASE_FOR_POW:
                raise FormulaError("Exponent or base too large")
            if left < 0 and not float(right).is_integer():
                raise FormulaError("Negative base with fractional exponent")
        if isinstance(node.op, (ast.Div, ast.Mod)) and right == 0:
            return zdv
        return float(_BIN_OPS[type(node.op)](left, right))
    if isinstance(node, ast.Call):
        func = node.func.id
        args = [_eval(a, values, zdv) for a in node.args]
        if func == "round":
            if len(args) > 2:
                raise FormulaError("round() takes at most 2 arguments")
            return float(round(args[0], int(args[1])) if len(args) == 2 else round(args[0]))
        if func == "abs":
            if len(args) != 1:
                raise FormulaError("abs() takes exactly 1 argument")
            return abs(args[0])
        return float(_FUNCTIONS[func](args))
    raise FormulaError(f"'{type(node).__name__}' is not allowed in formulas")
