"""
Catalog Payout Config — Admin L0–L3 monetization governance
===========================================================
Per-catalog-node config for free-usage quota, Solution Store cash range and
Karma rates, with L3->L0->global inheritance. Drives the payout/karma equations
in core.payout_engine (used by the Solution Store / ReviewNet / Decision Template
usage flows).

Routes (mounted under /catalog/payout):
  GET    /catalog/payout/config                 list global + per-node overrides
  GET    /catalog/payout/resolve                resolved GLOBAL config
  GET    /catalog/payout/resolve/{node_id}      resolved config for a node (+provenance)
  PUT    /catalog/payout/config/global          (admin) upsert global config
  PUT    /catalog/payout/config/node/{node_id}  (admin) upsert node override
  DELETE /catalog/payout/config/node/{node_id}  (admin) remove node override
  POST   /catalog/payout/preview                compute payout/karma for given inputs
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user, require_admin
from core.database import db
from core.payout_engine import (
    CONFIG_FIELDS,
    DEFAULT_GLOBAL,
    TEMPLATE_STEPS,
    compute_cash_payout,
    compute_karma,
    resolve_payout_config,
    template_step_karma,
)

router = APIRouter(prefix="/catalog/payout", tags=["Central Catalog Payout"])


class PayoutConfigBody(BaseModel):
    free_usage_solution_store: Optional[int] = None
    free_usage_template_by_step: Optional[Dict[str, int]] = None
    payment_min: Optional[float] = None
    payment_max: Optional[float] = None
    karma_solution_store: Optional[int] = None
    karma_reviewnet: Optional[int] = None
    karma_template_by_step: Optional[Dict[str, int]] = None


class PreviewBody(BaseModel):
    node_id: Optional[str] = None
    usage_type: str = "solution_store_paid"  # solution_store_paid|solution_store_free|template_free|reviewnet
    avg_rating: float = 0.0
    num_ratings: int = 0
    star_rating: Optional[float] = None
    template_step: Optional[str] = None  # for usage_type=template_free


def _clean(body: PayoutConfigBody) -> Dict[str, Any]:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    for dict_field in ("karma_template_by_step", "free_usage_template_by_step"):
        if dict_field in data and isinstance(data[dict_field], dict):
            data[dict_field] = {
                s: int(data[dict_field][s])
                for s in TEMPLATE_STEPS
                if data[dict_field].get(s) is not None
            }
    pmin = data.get("payment_min")
    pmax = data.get("payment_max")
    if pmin is not None and pmax is not None and float(pmax) < float(pmin):
        raise HTTPException(400, "payment_max must be >= payment_min")
    return data


@router.get("/config")
async def list_payout_config(user: dict = Depends(get_current_user)):
    """Global config + all per-node overrides (enriched with node name/level)."""
    g = await db.catalog_payout_configs.find_one({"scope": "global"}, {"_id": 0})
    nodes_raw = await db.catalog_payout_configs.find({"scope": "node"}, {"_id": 0}).to_list(2000)
    node_ids = [n["node_id"] for n in nodes_raw if n.get("node_id")]
    meta = {}
    if node_ids:
        async for nd in db.catalog_nodes.find({"node_id": {"$in": node_ids}}, {"_id": 0}):
            meta[nd["node_id"]] = {"name": nd.get("name"), "level": nd.get("level"),
                                   "life_area_id": nd.get("life_area_id")}
    nodes = []
    for n in nodes_raw:
        m = meta.get(n.get("node_id"), {})
        nodes.append({**n, "node_name": m.get("name"), "level": m.get("level"),
                      "life_area_id": m.get("life_area_id")})
    nodes.sort(key=lambda x: (x.get("level") or 0, x.get("node_name") or ""))
    return {
        "global": g or {"scope": "global", **DEFAULT_GLOBAL, "is_default": True},
        "default": DEFAULT_GLOBAL,
        "template_steps": TEMPLATE_STEPS,
        "nodes": nodes,
    }


@router.get("/resolve")
async def resolve_global(user: dict = Depends(get_current_user)):
    return await resolve_payout_config(db, None)


@router.get("/resolve/{node_id}")
async def resolve_node(node_id: str, user: dict = Depends(get_current_user)):
    node = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0})
    if not node:
        raise HTTPException(404, "catalog node not found")
    resolved = await resolve_payout_config(db, node_id)
    resolved["node_name"] = node.get("name")
    resolved["level"] = node.get("level")
    return resolved


@router.put("/config/global")
async def upsert_global(body: PayoutConfigBody, user: dict = Depends(require_admin)):
    data = _clean(body)
    data.update({"scope": "global", "node_id": None,
                 "updated_at": datetime.now(timezone.utc).isoformat(),
                 "updated_by": user["user_id"]})
    await db.catalog_payout_configs.update_one({"scope": "global"}, {"$set": data}, upsert=True)
    return await resolve_payout_config(db, None)


@router.put("/config/node/{node_id}")
async def upsert_node(node_id: str, body: PayoutConfigBody, user: dict = Depends(require_admin)):
    node = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0})
    if not node:
        raise HTTPException(404, "catalog node not found")
    data = _clean(body)
    data.update({"scope": "node", "node_id": node_id,
                 "updated_at": datetime.now(timezone.utc).isoformat(),
                 "updated_by": user["user_id"]})
    await db.catalog_payout_configs.update_one(
        {"scope": "node", "node_id": node_id}, {"$set": data}, upsert=True
    )
    resolved = await resolve_payout_config(db, node_id)
    resolved["node_name"] = node.get("name")
    resolved["level"] = node.get("level")
    return resolved


@router.delete("/config/node/{node_id}")
async def delete_node_config(node_id: str, user: dict = Depends(require_admin)):
    res = await db.catalog_payout_configs.delete_one({"scope": "node", "node_id": node_id})
    return {"deleted": res.deleted_count, "node_id": node_id}


@router.post("/preview")
async def preview(body: PreviewBody, user: dict = Depends(get_current_user)):
    """Compute the cash payout / karma for a hypothetical usage — powers the
    Admin config 'live preview' and lets the publish UI show expected earnings."""
    cfg = await resolve_payout_config(db, body.node_id)
    out: Dict[str, Any] = {"node_id": body.node_id, "usage_type": body.usage_type, "config": cfg}
    if body.usage_type == "solution_store_paid":
        out["currency"] = "INR"
        out["cash_payout"] = compute_cash_payout(cfg, body.avg_rating, body.num_ratings)
        out["reward_kind"] = "cash"
    elif body.usage_type == "solution_store_free":
        out["karma"] = compute_karma(cfg.get("karma_solution_store", 0), body.star_rating)
        out["reward_kind"] = "karma"
    elif body.usage_type == "template_free":
        step = body.template_step or "options"
        if step not in TEMPLATE_STEPS:
            raise HTTPException(400, f"template_step must be one of {TEMPLATE_STEPS}")
        out["karma"] = template_step_karma(cfg, step, body.star_rating)
        out["template_step"] = step
        out["reward_kind"] = "karma"
    elif body.usage_type == "reviewnet":
        out["karma"] = compute_karma(cfg.get("karma_reviewnet", 0), body.star_rating)
        out["reward_kind"] = "karma"
    else:
        raise HTTPException(400, "unknown usage_type")
    return out
