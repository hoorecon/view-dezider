"""Safe expression evaluator for user-editable factor dependency formulas.

Users declare formulas like ``f7 = f1 * (f2/100) * f3 * (f4/100) * f6 / f5`` on
a Decision. The engine:

  • Parses via ``ast`` and rejects any node not on a strict whitelist (no
    attribute access, no imports, no calls except ``abs, min, max, round``).
  • Evaluates against a symbol table ``{fN: value}``.
  • Supports two scopes:
        - ``per_option`` (default): each option's computed value is derived
          from that option's other factor values.
        - ``cross_option``: a single scalar shared by every option — for
          constants that don't vary per option (evaluated once from a
          caller-supplied constants map or the first option's values).

The frontend uses the same syntax; a mirror JS evaluator lives in
``frontend/src/utils/formulaEval.ts``.
"""
from __future__ import annotations

import ast
import operator
from typing import Any, Dict, List, Optional, Tuple

# ── Allowed AST nodes (everything else raises SyntaxError) ────────
_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,   # numeric literals
    ast.Num,        # <3.8 back-compat (harmless in 3.10+)
    ast.Name,
    ast.Load,
    ast.Call,
    ast.USub,
    ast.UAdd,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
)

_ALLOWED_FUNCS = {
    "abs": abs,
    "min": min,
    "max": max,
    "pow": pow,
    "round": round,
    "sqrt": lambda x: x ** 0.5,
    # `log` and `exp` are exposed via math.* so we don't leak `math` module.
    "log": __import__("math").log,
    "exp": __import__("math").exp,
}

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


class FormulaError(ValueError):
    """Raised for any parse / evaluation error the caller can render to UI."""


def parse_expression(expr: str) -> ast.Expression:
    """Parse `expr` and reject any disallowed AST node.

    Raises FormulaError on any invalid syntax or forbidden node type.
    """
    if not expr or not str(expr).strip():
        raise FormulaError("Expression is empty")
    # Alias — accept `^` as exponent (aligns with the frontend tokenizer and
    # matches typical math notation from spreadsheet users). Python would
    # otherwise interpret `^` as bitwise XOR.
    src = str(expr).replace("^", "**")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"Syntax error: {e.msg}")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise FormulaError(f"Unsupported expression element: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not (isinstance(node.func, ast.Name) and node.func.id in _ALLOWED_FUNCS):
                raise FormulaError(
                    "Only abs / min / max / round function calls are allowed"
                )
    return tree


def _eval_node(node: ast.AST, symbols: Dict[str, Any]) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, symbols)
    if isinstance(node, ast.Constant):
        v = node.value
        if not isinstance(v, (int, float)):
            raise FormulaError(f"Only numeric literals allowed (got {type(v).__name__})")
        return float(v)
    if isinstance(node, ast.Num):  # pragma: no cover  (py<3.8)
        return float(node.n)
    if isinstance(node, ast.Name):
        name = node.id
        if name not in symbols:
            raise FormulaError(f"Unknown variable: {name}")
        val = symbols[name]
        if val is None or val == "":
            raise FormulaError(f"Value for {name} is not set")
        try:
            return float(val)
        except (TypeError, ValueError):
            raise FormulaError(f"Value for {name} is not numeric: {val!r}")
    if isinstance(node, ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise FormulaError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_eval_node(node.left, symbols), _eval_node(node.right, symbols))
    if isinstance(node, ast.UnaryOp):
        v = _eval_node(node.operand, symbols)
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.UAdd):
            return +v
        raise FormulaError(f"Unsupported unary op: {type(node.op).__name__}")
    if isinstance(node, ast.Call):
        fn = _ALLOWED_FUNCS[node.func.id]  # type: ignore[union-attr]
        args = [_eval_node(a, symbols) for a in node.args]
        return float(fn(*args))
    raise FormulaError(f"Unsupported node: {type(node).__name__}")


def evaluate(expr: str, symbols: Dict[str, Any]) -> float:
    """Evaluate a whitelisted math expression against `symbols`.

    `symbols` maps variable ids (e.g. "f1") to numeric values. Missing or
    non-numeric values raise FormulaError.
    """
    tree = parse_expression(expr)
    return _eval_node(tree, symbols)


def used_variables(expr: str) -> List[str]:
    """Return the sorted, unique list of `fN` identifiers used in `expr`.

    Returns [] for a purely constant expression or when parsing fails
    silently at the caller — a separate `parse_expression` should be used
    when you need to surface errors.
    """
    try:
        tree = ast.parse(str(expr or "").replace("^", "**"), mode="eval")
    except SyntaxError:
        return []
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id not in _ALLOWED_FUNCS}
    return sorted(names)


# ──────────────────────────────────────────────────────────────────
# Formula list helpers (used by decision routes)
# ──────────────────────────────────────────────────────────────────

def order_by_dependencies(
    formulas: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Topologically order formulas so a target's inputs are resolved first.

    Returns (ordered_list, error_msg). error_msg is non-None on cycle.
    """
    remaining = list(formulas or [])
    targets = {f.get("target") for f in remaining if f.get("target")}
    resolved: List[Dict[str, Any]] = []
    done: set = set()
    # simple iterative pass — good enough for < 100 formulas
    while remaining:
        progressed = False
        next_round: List[Dict[str, Any]] = []
        for f in remaining:
            deps = [v for v in used_variables(f.get("expression", "")) if v in targets]
            if all(d in done for d in deps):
                resolved.append(f)
                done.add(f.get("target"))
                progressed = True
            else:
                next_round.append(f)
        if not progressed:
            unresolved = [f.get("target") for f in next_round]
            return resolved, f"Circular / unresolved formulas: {unresolved}"
        remaining = next_round
    return resolved, None


def apply_formulas_to_symbols(
    formulas: List[Dict[str, Any]],
    base_symbols: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Evaluate every formula and fold results back into a copy of `base_symbols`.

    Returns (new_symbols, errors_by_target). Formulas targeting values that
    fail to evaluate are skipped and their target left untouched.
    """
    ordered, cycle = order_by_dependencies(formulas or [])
    symbols = dict(base_symbols)
    errors: Dict[str, str] = {}
    if cycle:
        errors["__cycle__"] = cycle
        return symbols, errors
    for f in ordered:
        target = f.get("target")
        expr = f.get("expression") or ""
        if not target:
            continue
        try:
            val = evaluate(expr, symbols)
        except FormulaError as e:
            errors[target] = str(e)
            continue
        symbols[target] = val
    return symbols, errors
