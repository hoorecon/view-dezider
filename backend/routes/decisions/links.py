"""Dependent Decisions — link another scored decision in as a FACTOR.

A MyDezider decision can pull another *scored* MyDezider decision's option
result in as a factor (mode 'factor_only') and optionally also as an option with
a pre-filled Step-7 assessment cell (mode 'factor_and_option'). The factor's
value comes from the target's chosen option worth % ('option_worth') or its best
option ('top_score'). Re-resolution can be 'auto' (re-pulled on open) or
'manual'. Circular dependencies (A→B→A …) are blocked.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Decisions"])


def _is_scored(dec: dict) -> bool:
    """A decision is 'scored' once at least one option has a worth %."""
    return any((o.get("worth_percentage") or 0) > 0 for o in dec.get("options", []))


def _recompute_worth(factors: List[dict], options: List[dict]) -> None:
    """Mirror crud.update_decision's worth formula (top-level factors only)."""
    total_rating = sum(f.get("rating", 0) for f in factors if not f.get("parent_id"))
    for opt in options:
        worth = 0.0
        if total_rating > 0:
            for a in opt.get("assessments", []):
                f = next((x for x in factors if x["id"] == a["factor_id"] and not x.get("parent_id")), None)
                if f and a.get("percentage") is not None:
                    worth += (f.get("rating", 0) / total_rating) * max(0, min(100, a["percentage"]))
        opt["worth_percentage"] = round(min(100.0, max(0.0, worth)), 2)


def _resolve_value(target: dict, option_id: Optional[str], metric: str):
    """Return (value_pct, option_id, option_name) for the chosen metric."""
    opts = target.get("options", [])
    if metric == "top_score":
        best = max(opts, key=lambda o: o.get("worth_percentage") or 0, default=None)
        if not best:
            raise HTTPException(422, "Linked decision has no scored options.")
        return float(best.get("worth_percentage") or 0), best["id"], best.get("name", "")
    opt = next((o for o in opts if o["id"] == option_id), None)
    if not opt:
        raise HTTPException(422, "Selected option not found in the linked decision.")
    return float(opt.get("worth_percentage") or 0), opt["id"], opt.get("name", "")


async def _depends_on(start_id: str, target_id: str, user_id: str, _seen=None) -> bool:
    """True if `start_id` (transitively) depends on `target_id` via decision_link factors."""
    if _seen is None:
        _seen = set()
    if start_id in _seen:
        return False
    _seen.add(start_id)
    dec = await db.decisions.find_one({"id": start_id, "user_id": user_id}, {"_id": 0, "factors": 1})
    if not dec:
        return False
    for f in dec.get("factors", []):
        ds = f.get("data_source") or {}
        if ds.get("type") == "decision_link":
            lid = (ds.get("config") or {}).get("linked_decision_id")
            if lid == target_id:
                return True
            if lid and await _depends_on(lid, target_id, user_id, _seen):
                return True
    return False


@router.get("/decisions/{decision_id}/linkable")
async def list_linkable(decision_id: str, user: dict = Depends(get_current_user)):
    """Candidate target decisions (scored, non-cyclic) the user can link in."""
    me = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0, "id": 1})
    if not me:
        raise HTTPException(404, "Decision not found")
    out = []
    cursor = db.decisions.find(
        {"user_id": user["user_id"], "id": {"$ne": decision_id}, "status": {"$ne": "deleted"}},
        {"_id": 0, "id": 1, "title": 1, "life_area": 1, "options": 1},
    )
    async for d in cursor:
        if not _is_scored(d):
            continue
        # cycle guard: a target that already depends on me would loop
        if await _depends_on(d["id"], decision_id, user["user_id"]):
            continue
        opts = sorted(
            [{"id": o["id"], "name": o.get("name", ""),
              "worth_percentage": round(o.get("worth_percentage") or 0, 1)}
             for o in d.get("options", [])],
            key=lambda x: x["worth_percentage"], reverse=True,
        )
        out.append({
            "id": d["id"], "title": d.get("title", "Untitled"),
            "life_area": d.get("life_area"), "module": "mydezider",
            "options": opts, "top_option_id": opts[0]["id"] if opts else None,
        })
    return {"decisions": out}


class LinkRequest(BaseModel):
    linked_decision_id: str
    linked_module: str = "mydezider"
    linked_option_id: Optional[str] = None
    metric: str = "option_worth"     # option_worth | top_score
    refresh: str = "auto"            # auto | manual
    link_mode: str = "factor_only"   # factor_only | factor_and_option
    factor_name: Optional[str] = None


@router.post("/decisions/{decision_id}/link-decision")
async def link_decision(decision_id: str, req: LinkRequest, user: dict = Depends(get_current_user)):
    me = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not me:
        raise HTTPException(404, "Decision not found")
    if req.linked_decision_id == decision_id:
        raise HTTPException(422, "A decision cannot link to itself.")
    target = await db.decisions.find_one(
        {"id": req.linked_decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not target:
        raise HTTPException(404, "Linked decision not found")
    if not _is_scored(target):
        raise HTTPException(422, "The selected decision isn't scored yet. Complete its assessment (Step 7–8) first.")
    if await _depends_on(req.linked_decision_id, decision_id, user["user_id"]):
        raise HTTPException(409, "That would create a circular dependency between the two decisions.")

    value, opt_id, opt_name = _resolve_value(target, req.linked_option_id, req.metric)
    factor_name = (req.factor_name or opt_name or target.get("title") or "Linked decision").strip()

    factors = me.get("factors", [])
    options = me.get("options", [])
    max_order = max([f.get("order", 0) for f in factors], default=-1)
    prim = [f.get("rating", 0) for f in factors if not f.get("parent_id")]
    default_rating = int(round(sum(prim) / len(prim))) if prim else 5
    now = datetime.now(timezone.utc).isoformat()
    factor_id = str(uuid.uuid4())
    factors.append({
        "id": factor_id, "name": factor_name, "category": "primary",
        "rating": default_rating or 5, "order": max_order + 1,
        "unit": "%", "expected_value": round(value, 1),
        "data_type": "numeric", "factor_type": "quantitative",
        "operator": ">=", "gap_multiplier": 1.0, "parent_id": None, "weight": None,
        "data_source": {
            "type": "decision_link",
            "config": {
                "linked_decision_id": req.linked_decision_id,
                "linked_module": req.linked_module,
                "linked_option_id": opt_id, "linked_option_name": opt_name,
                "linked_title": target.get("title"), "metric": req.metric,
                "refresh": req.refresh, "link_mode": req.link_mode,
            },
            "last_value": str(round(value, 1)), "last_fetched": now,
        },
    })
    if req.link_mode == "factor_and_option":
        options.append({
            "id": str(uuid.uuid4()),
            "name": opt_name or target.get("title") or factor_name,
            "assessments": [{
                "factor_id": factor_id, "percentage": int(round(value)),
                "actual_value": round(value, 1), "assessment_mode": "custom",
            }],
            "worth_percentage": 0.0, "source": "manual",
            "ai_rationale": f"Linked from decision “{target.get('title')}”",
        })

    _recompute_worth(factors, options)
    await db.decisions.update_one(
        {"id": decision_id},
        {"$set": {"factors": factors, "options": options, "updated_at": datetime.now(timezone.utc)}})
    return {"ok": True, "factor_id": factor_id, "value": round(value, 1), "factor_name": factor_name}


@router.post("/decisions/{decision_id}/links/{factor_id}/resolve")
async def resolve_link(decision_id: str, factor_id: str, user: dict = Depends(get_current_user)):
    """Manual refresh of a single linked factor's value from its target."""
    me = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not me:
        raise HTTPException(404, "Decision not found")
    factors = me.get("factors", [])
    options = me.get("options", [])
    f = next((x for x in factors if x["id"] == factor_id), None)
    if not f or (f.get("data_source") or {}).get("type") != "decision_link":
        raise HTTPException(404, "Linked factor not found")
    cfg = f["data_source"].get("config") or {}
    target = await db.decisions.find_one(
        {"id": cfg.get("linked_decision_id"), "user_id": user["user_id"]}, {"_id": 0})
    if not target or not _is_scored(target):
        return {"ok": False, "reason": "target_unscored"}
    value, opt_id, _ = _resolve_value(target, cfg.get("linked_option_id"), cfg.get("metric", "option_worth"))
    old = f.get("expected_value")
    f["expected_value"] = round(value, 1)
    f["data_source"]["last_value"] = str(round(value, 1))
    f["data_source"]["last_fetched"] = datetime.now(timezone.utc).isoformat()
    cfg["linked_option_id"] = opt_id
    if cfg.get("link_mode") == "factor_and_option":
        for o in options:
            for a in o.get("assessments", []):
                if a["factor_id"] == factor_id:
                    a["percentage"] = int(round(value))
                    a["actual_value"] = round(value, 1)
    _recompute_worth(factors, options)
    await db.decisions.update_one(
        {"id": decision_id},
        {"$set": {"factors": factors, "options": options, "updated_at": datetime.now(timezone.utc)}})
    return {"ok": True, "old": old, "new": round(value, 1), "changed": str(old) != str(round(value, 1))}


@router.post("/decisions/{decision_id}/links/refresh-auto")
async def refresh_auto(decision_id: str, user: dict = Depends(get_current_user)):
    """Re-pull every 'auto'-refresh linked factor; returns the list of changes."""
    me = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not me:
        raise HTTPException(404, "Decision not found")
    factors = me.get("factors", [])
    options = me.get("options", [])
    changes = []
    for f in factors:
        ds = f.get("data_source") or {}
        cfg = ds.get("config") or {}
        if ds.get("type") != "decision_link" or cfg.get("refresh") != "auto":
            continue
        target = await db.decisions.find_one(
            {"id": cfg.get("linked_decision_id"), "user_id": user["user_id"]}, {"_id": 0})
        if not target or not _is_scored(target):
            continue
        value, opt_id, _ = _resolve_value(target, cfg.get("linked_option_id"), cfg.get("metric", "option_worth"))
        old = f.get("expected_value")
        if str(old) != str(round(value, 1)):
            changes.append({"factor_id": f["id"], "name": f.get("name"), "old": old, "new": round(value, 1)})
        f["expected_value"] = round(value, 1)
        ds["last_value"] = str(round(value, 1))
        ds["last_fetched"] = datetime.now(timezone.utc).isoformat()
        cfg["linked_option_id"] = opt_id
        if cfg.get("link_mode") == "factor_and_option":
            for o in options:
                for a in o.get("assessments", []):
                    if a["factor_id"] == f["id"]:
                        a["percentage"] = int(round(value))
                        a["actual_value"] = round(value, 1)
    if changes:
        _recompute_worth(factors, options)
        await db.decisions.update_one(
            {"id": decision_id},
            {"$set": {"factors": factors, "options": options, "updated_at": datetime.now(timezone.utc)}})
    return {"ok": True, "changes": changes}
