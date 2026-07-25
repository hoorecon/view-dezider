"""Formula validation endpoint — validates a user-authored dependency
formula and returns a dry-run evaluation using either supplied symbols or
the caller's first option's factor values.

POST /api/decisions/formulas/validate
Body:
  { "expression": "f1 * (f2/100) * f3",
    "symbols":    {"f1": 1000, "f2": 20, "f3": 3}   // optional
  }
Response:
  { "ok": true, "value": 600.0, "variables": ["f1","f2","f3"] }
  { "ok": false, "error": "Unknown variable: f9",   "variables": [...] }
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from core.auth import get_current_user
from core.formula_engine import evaluate, used_variables, FormulaError

router = APIRouter(tags=["Decisions"])


class FormulaValidateRequest(BaseModel):
    expression: str
    symbols: Optional[Dict[str, Any]] = None


@router.post("/decisions/formulas/validate")
async def validate_formula(
    body: FormulaValidateRequest,
    user: dict = Depends(get_current_user),
):
    vars_used = used_variables(body.expression)
    try:
        if body.symbols is None:
            # Dry-run with dummies to catch syntax/whitelist errors.
            dummies = {v: 1.0 for v in vars_used}
            value = evaluate(body.expression, dummies)
            return {"ok": True, "value": value, "variables": vars_used, "note": "dry-run"}
        value = evaluate(body.expression, body.symbols)
        return {"ok": True, "value": value, "variables": vars_used}
    except FormulaError as e:
        return {"ok": False, "error": str(e), "variables": vars_used}
