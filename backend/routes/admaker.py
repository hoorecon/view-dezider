"""AdMaker Program — AdWords-style bid management for Sponsored Solutions.

Advertisers (managed by Admin for now) bid on a Decider App's option for a
region + time slot. When a user runs the Finder, options that clear the
Min-Cutoff % quality gate enter an AdRank auction (bid × QualityScore) and the
top `sponsored_n` render BELOW the organic list — clearly labelled. Billing is
per click at the GSP price (see core.ad_auction).

Routes (under /api):
  GET    /admaker/bids                     admin — list (joined template titles)
  POST   /admaker/bids                     admin — create
  PUT    /admaker/bids/{bid_id}            admin — update
  DELETE /admaker/bids/{bid_id}            admin — delete
  POST   /admaker/track                    user  — record a sponsored CLICK (CPC charge)
  GET    /admaker/resolve-config           admin — effective cutoff/slots for a node/template
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request

from core import ad_auction
from core.auth import get_current_user, require_admin
from core.database import db

router = APIRouter(prefix="/admaker", tags=["AdMaker Program"])

BID_STATUSES = ("active", "paused", "exhausted")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_bid(body: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def _has(k: str) -> bool:
        return k in body and body[k] is not None

    if _has("option_name") or not partial:
        name = str(body.get("option_name") or "").strip()
        if not name:
            raise HTTPException(400, "option_name is required")
        out["option_name"] = name
    if _has("advertiser_name") or not partial:
        adv = str(body.get("advertiser_name") or "").strip()
        if not adv:
            raise HTTPException(400, "advertiser_name is required")
        out["advertiser_name"] = adv
    if _has("region") or not partial:
        out["region"] = str(body.get("region") or "global").strip().lower() or "global"
    if _has("bid_paise") or not partial:
        try:
            bp = int(float(body.get("bid_paise") or 0))
        except (TypeError, ValueError):
            raise HTTPException(400, "bid_paise must be a number")
        if bp < 1:
            raise HTTPException(400, "bid_paise must be ≥ 1 (₹0.01)")
        out["bid_paise"] = bp
    if _has("budget_paise"):
        try:
            out["budget_paise"] = max(0, int(float(body["budget_paise"])))
        except (TypeError, ValueError):
            raise HTTPException(400, "budget_paise must be a number")
    for k in ("slot_start", "slot_end"):
        if k in body:
            v = str(body.get(k) or "").strip()
            if v and ad_auction._parse_dt(v) is None:
                raise HTTPException(400, f"{k} must be ISO date/datetime (e.g. 2026-07-01 or 2026-07-01T09:00)")
            out[k] = v or None
    hrs = [body.get("daily_start_hour"), body.get("daily_end_hour")]
    if any(h is not None and str(h) != "" for h in hrs):
        try:
            sh, eh = int(float(hrs[0])), int(float(hrs[1]))
        except (TypeError, ValueError):
            raise HTTPException(400, "daily_start_hour and daily_end_hour must both be set (0-23)")
        if not (0 <= sh <= 23 and 0 <= eh <= 23):
            raise HTTPException(400, "daily hours must be 0-23")
        out["daily_start_hour"], out["daily_end_hour"] = sh, eh
    elif "daily_start_hour" in body or "daily_end_hour" in body:
        out["daily_start_hour"] = out["daily_end_hour"] = None
    if _has("timezone"):
        tz = str(body["timezone"]).strip() or "Asia/Kolkata"
        try:
            ZoneInfo(tz)
        except Exception:
            raise HTTPException(400, f"Unknown timezone '{tz}' (use IANA names like Asia/Kolkata)")
        out["timezone"] = tz
    if _has("status"):
        st = str(body["status"]).strip().lower()
        if st not in BID_STATUSES:
            raise HTTPException(400, f"status must be one of {BID_STATUSES}")
        out["status"] = st
    return out


# ══════════════════════════════ admin CRUD ══════════════════════════════
@router.get("/bids")
async def list_bids(template_id: Optional[str] = None, status: Optional[str] = None,
                    user: dict = Depends(require_admin)):
    q: Dict[str, Any] = {}
    if template_id:
        q["template_id"] = template_id
    if status in BID_STATUSES:
        q["status"] = status
    bids = await db.admaker_bids.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    tids = list({b["template_id"] for b in bids})
    titles = {t["template_id"]: t.get("title") for t in await db.decider_store_templates.find(
        {"template_id": {"$in": tids}}, {"_id": 0, "template_id": 1, "title": 1}).to_list(500)}
    for b in bids:
        b["template_title"] = titles.get(b["template_id"]) or b["template_id"]
    return {"bids": bids}


@router.post("/bids")
async def create_bid(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    template_id = str(body.get("template_id") or "").strip()
    t = await db.decider_store_templates.find_one(
        {"template_id": template_id}, {"_id": 0, "template_id": 1, "title": 1})
    if not t:
        raise HTTPException(404, "template_id not found in the Decider Store")
    clean = _clean_bid(body, partial=False)
    doc = {
        "bid_id": str(uuid.uuid4()),
        "template_id": template_id,
        "timezone": clean.get("timezone") or str(body.get("timezone") or "Asia/Kolkata"),
        "budget_paise": clean.get("budget_paise", 0),
        "slot_start": clean.get("slot_start"), "slot_end": clean.get("slot_end"),
        "daily_start_hour": clean.get("daily_start_hour"),
        "daily_end_hour": clean.get("daily_end_hour"),
        "status": clean.get("status", "active"),
        "spent_paise": 0, "impressions": 0, "clicks": 0, "last_price_paise": None,
        "created_by": user["user_id"], "created_at": _now(), "updated_at": _now(),
        **{k: clean[k] for k in ("option_name", "advertiser_name", "region", "bid_paise")},
    }
    await db.admaker_bids.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/bids/{bid_id}")
async def update_bid(bid_id: str, request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    update = _clean_bid(body, partial=True)
    if not update:
        raise HTTPException(400, "Nothing to update")
    update["updated_at"] = _now()
    res = await db.admaker_bids.update_one({"bid_id": bid_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Bid not found")
    return await db.admaker_bids.find_one({"bid_id": bid_id}, {"_id": 0})


@router.delete("/bids/{bid_id}")
async def delete_bid(bid_id: str, user: dict = Depends(require_admin)):
    res = await db.admaker_bids.delete_one({"bid_id": bid_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Bid not found")
    return {"message": "deleted"}


# ══════════════════════════ click billing (CPC) ══════════════════════════
@router.post("/track")
async def track_click(request: Request, user: dict = Depends(get_current_user)):
    """Record a click on a Sponsored Solution → charge the GSP price (CPC)."""
    body = await request.json()
    bid_id = str(body.get("bid_id") or "").strip()
    bid = await db.admaker_bids.find_one({"bid_id": bid_id}, {"_id": 0})
    if not bid:
        raise HTTPException(404, "Bid not found")
    price = int(bid.get("last_price_paise") or bid.get("bid_paise") or 0)
    await db.admaker_events.insert_one({
        "event_id": str(uuid.uuid4()), "event": "click",
        "bid_id": bid_id, "template_id": bid.get("template_id"),
        "decision_id": body.get("decision_id"), "option_id": body.get("option_id"),
        "price_paise": price, "user_id": user["user_id"], "ts": _now(),
    })
    patch: Dict[str, Any] = {"$inc": {"clicks": 1, "spent_paise": price},
                             "$set": {"updated_at": _now()}}
    await db.admaker_bids.update_one({"bid_id": bid_id}, patch)
    budget = int(bid.get("budget_paise") or 0)
    if budget > 0 and int(bid.get("spent_paise") or 0) + price >= budget:
        await db.admaker_bids.update_one(
            {"bid_id": bid_id, "status": "active"}, {"$set": {"status": "exhausted"}})
    return {"ok": True, "charged_paise": price}


# ═══════════════════ effective config (for the admin UI) ═══════════════════
@router.get("/resolve-config")
async def resolve_config(node_id: Optional[str] = None, template_id: Optional[str] = None,
                         user: dict = Depends(require_admin)):
    """Show the EFFECTIVE Min-Cutoff % + Sponsored-N and where each value
    comes from (template / CCM node / global)."""
    template = None
    if template_id:
        template = await db.decider_store_templates.find_one(
            {"template_id": template_id},
            {"_id": 0, "template_id": 1, "finder_settings": 1, "catalog_node_id": 1})
        if not template:
            raise HTTPException(404, "template not found")
    elif node_id:
        template = {"catalog_node_id": node_id}
    cfg = await ad_auction.resolve_ad_config(template)
    if node_id:
        node = await db.catalog_nodes.find_one(
            {"node_id": node_id}, {"_id": 0, "node_id": 1, "name": 1, "finder_ad_config": 1})
        cfg["node_own_config"] = (node or {}).get("finder_ad_config") or {}
    return cfg
