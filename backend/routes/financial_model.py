"""
Financial Model API — Phase 1 of the "Financial Model" branch on L1 (Financial)
of an Org's 6 LeGS tree.

A model is owned by a user + scoped to one of their Orgs (user_org_id) and can be
linked to an L1 six_legs goal (leg_goal_id). It stores assumptions; the 3-statement
forecast + ratios + DCF valuation are computed on the fly by core.fin_model.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user
from core.fin_model import compute_model, default_assumptions

router = APIRouter(prefix="/financial-models", tags=["Financial Model"])

UNITS = [
    {"id": "absolute", "name": "Absolute", "divisor": 1, "suffix": ""},
    {"id": "thousands", "name": "Thousands (K)", "divisor": 1_000, "suffix": "K"},
    {"id": "lakhs", "name": "Lakhs", "divisor": 100_000, "suffix": "L"},
    {"id": "millions", "name": "Millions (M)", "divisor": 1_000_000, "suffix": "M"},
    {"id": "crores", "name": "Crores", "divisor": 10_000_000, "suffix": "Cr"},
]
HISTORICAL_STAGES = [
    {"id": "pre_revenue", "name": "Pre-revenue (0 months)"},
    {"id": "3m", "name": "3 months actuals"},
    {"id": "6m", "name": "6 months actuals"},
    {"id": "9m", "name": "9 months actuals"},
    {"id": "1y", "name": "1 year actuals"},
    {"id": "2y", "name": "2 years actuals"},
]
CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED", "SGD"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _own_org(user: dict, user_org_id: str) -> dict:
    org = await db.user_orgs.find_one({"id": user_org_id, "owner_user_id": user["user_id"]})
    if not org:
        raise HTTPException(404, "Org not found or not yours")
    return org


def _with_computed(model: dict) -> dict:
    model = dict(model)
    model.pop("_id", None)
    try:
        model["computed"] = compute_model(
            model.get("assumptions") or {}, model.get("projection_years", 5))
    except Exception as e:  # noqa: BLE001
        model["computed"] = None
        model["compute_error"] = str(e)[:200]
    return model


@router.get("/meta")
async def get_meta(user: dict = Depends(get_current_user)):
    return {
        "default_assumptions": default_assumptions(),
        "units": UNITS,
        "currencies": CURRENCIES,
        "historical_stages": HISTORICAL_STAGES,
        "max_projection_years": 10,
    }


class ComputeIn(BaseModel):
    assumptions: Dict[str, Any]
    projection_years: int = 5


@router.post("/compute")
async def compute_preview(body: ComputeIn, user: dict = Depends(get_current_user)):
    """Stateless compute for live preview (no save)."""
    return {"computed": compute_model(body.assumptions or {}, body.projection_years)}


class ModelIn(BaseModel):
    user_org_id: str
    leg_goal_id: Optional[str] = None
    name: str = "Financial Model"
    currency: str = "INR"
    units: str = "absolute"
    historical_stage: str = "pre_revenue"
    projection_years: int = 5
    assumptions: Optional[Dict[str, Any]] = None


@router.post("")
async def create_model(p: ModelIn, user: dict = Depends(get_current_user)):
    await _own_org(user, p.user_org_id)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "user_org_id": p.user_org_id,
        "leg_goal_id": p.leg_goal_id,
        "name": (p.name or "Financial Model").strip(),
        "currency": p.currency or "INR",
        "units": p.units or "absolute",
        "historical_stage": p.historical_stage or "pre_revenue",
        "projection_years": max(1, min(int(p.projection_years or 5), 10)),
        "assumptions": p.assumptions or default_assumptions(),
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.financial_models.insert_one(doc)
    return _with_computed(doc)


@router.get("")
async def list_models(user_org_id: str, user: dict = Depends(get_current_user)):
    await _own_org(user, user_org_id)
    rows = await db.financial_models.find(
        {"user_org_id": user_org_id, "user_id": user["user_id"]},
        {"_id": 0, "assumptions": 0},
    ).sort("created_at", -1).to_list(200)
    return {"models": rows}


@router.get("/{model_id}")
async def get_model(model_id: str, user: dict = Depends(get_current_user)):
    doc = await db.financial_models.find_one(
        {"id": model_id, "user_id": user["user_id"]})
    if not doc:
        raise HTTPException(404, "Financial model not found")
    return _with_computed(doc)


@router.put("/{model_id}")
async def update_model(model_id: str, request: Request, user: dict = Depends(get_current_user)):
    existing = await db.financial_models.find_one(
        {"id": model_id, "user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "Financial model not found")
    body = await request.json()
    allowed = ["name", "currency", "units", "historical_stage", "assumptions", "leg_goal_id"]
    update: Dict[str, Any] = {k: body[k] for k in allowed if k in body}
    if "projection_years" in body:
        update["projection_years"] = max(1, min(int(body["projection_years"] or 5), 10))
    update["updated_at"] = _now()
    await db.financial_models.update_one({"id": model_id}, {"$set": update})
    doc = await db.financial_models.find_one({"id": model_id})
    return _with_computed(doc)


@router.delete("/{model_id}")
async def delete_model(model_id: str, user: dict = Depends(get_current_user)):
    res = await db.financial_models.delete_one(
        {"id": model_id, "user_id": user["user_id"]})
    if not res.deleted_count:
        raise HTTPException(404, "Financial model not found")
    return {"ok": True}
