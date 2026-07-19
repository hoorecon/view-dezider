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


# ═══════════════ AdMaker Studio (advertiser self-serve) ═══════════════
# Same USER login — no separate auth stack. Access ladder:
#   platform admins → always; Org members with role org_admin/advertiser →
#   always; everyone else → ACM feature `admaker_program` (Premium paid_pro+).
async def _require_admaker(user: dict) -> None:
    role = str(user.get("role") or "").lower()
    if role in ("admin", "super_admin", "co_admin"):
        return
    if user.get("org_id") and str(user.get("org_role") or "").lower() in ("org_admin", "advertiser"):
        return
    from core.acm_engine import check_feature_access
    acm = await check_feature_access(user, "admaker_program", check_quota=False)
    if acm.get("allowed"):
        return
    raise HTTPException(403, acm.get("upgrade_message")
                        or "AdMaker Studio needs a Premium (Pro) plan or an Org advertiser role.")


async def _owned_options(user: dict, template_id: str) -> Dict[str, Dict[str, Any]]:
    """name_norm → {option_name, solution_id} for options whose bridged
    Solution-Store listing the caller owns (created_by, or same-org creator)."""
    t = await db.decider_store_templates.find_one(
        {"template_id": template_id}, {"_id": 0, "options.name": 1, "options.linked_solution_id": 1})
    if not t:
        raise HTTPException(404, "template not found")
    by_sol: Dict[str, str] = {}
    for o in t.get("options") or []:
        if o.get("linked_solution_id") and o.get("name"):
            by_sol[o["linked_solution_id"]] = o["name"]
    # Bank options bridged from the Solution Store carry source_ref=solution_id.
    async for b in db.decider_option_bank.find(
            {"template_id": template_id, "source": "store_bridge",
             "source_ref": {"$ne": None}}, {"_id": 0, "name": 1, "source_ref": 1}):
        by_sol.setdefault(b["source_ref"], b["name"])
    if not by_sol:
        return {}
    owner_q: Dict[str, Any] = {"solution_id": {"$in": list(by_sol.keys())}}
    if user.get("org_id"):
        org_user_ids = [m.get("user_id") async for m in db.users.find(
            {"org_id": user["org_id"]}, {"_id": 0, "user_id": 1})]
        owner_q["created_by"] = {"$in": list({user["user_id"], *filter(None, org_user_ids)})}
    else:
        owner_q["created_by"] = user["user_id"]
    owned: Dict[str, Dict[str, Any]] = {}
    async for s in db.solutions_store.find(owner_q, {"_id": 0, "solution_id": 1}):
        name = by_sol.get(s["solution_id"])
        if name:
            owned[ad_auction._norm(name)] = {"option_name": name,
                                             "solution_id": s["solution_id"]}
    return owned


@router.get("/my/eligible-options")
async def my_eligible_options(template_id: str, user: dict = Depends(get_current_user)):
    await _require_admaker(user)
    owned = await _owned_options(user, template_id)
    return {"options": sorted(owned.values(), key=lambda x: x["option_name"])}


@router.get("/my/bids")
async def my_bids(user: dict = Depends(get_current_user)):
    await _require_admaker(user)
    bids = await db.admaker_bids.find(
        {"created_by": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    tids = list({b["template_id"] for b in bids})
    titles = {t["template_id"]: t.get("title") for t in await db.decider_store_templates.find(
        {"template_id": {"$in": tids}}, {"_id": 0, "template_id": 1, "title": 1}).to_list(200)}
    for b in bids:
        b["template_title"] = titles.get(b["template_id"]) or b["template_id"]
    return {"bids": bids}


@router.post("/my/bids")
async def my_create_bid(request: Request, user: dict = Depends(get_current_user)):
    await _require_admaker(user)
    body = await request.json()
    template_id = str(body.get("template_id") or "").strip()
    owned = await _owned_options(user, template_id)
    key = ad_auction._norm(body.get("option_name"))
    if key not in owned:
        raise HTTPException(403, "You can only promote options linked to your own "
                                 "Solution-Store listings.")
    clean = _clean_bid(body, partial=False)
    doc = {
        "bid_id": str(uuid.uuid4()), "template_id": template_id,
        "advertiser_name": clean.get("advertiser_name") or user.get("name") or "Advertiser",
        "option_name": owned[key]["option_name"],
        "solution_id": owned[key]["solution_id"],
        "region": clean["region"], "bid_paise": clean["bid_paise"],
        "budget_paise": clean.get("budget_paise", 0),
        "slot_start": clean.get("slot_start"), "slot_end": clean.get("slot_end"),
        "daily_start_hour": clean.get("daily_start_hour"),
        "daily_end_hour": clean.get("daily_end_hour"),
        "timezone": clean.get("timezone") or "Asia/Kolkata",
        "status": "active", "spent_paise": 0, "impressions": 0, "clicks": 0,
        "last_price_paise": None, "org_id": user.get("org_id"),
        "created_by": user["user_id"], "created_at": _now(), "updated_at": _now(),
    }
    await db.admaker_bids.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/my/bids/{bid_id}")
async def my_update_bid(bid_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _require_admaker(user)
    body = await request.json()
    body.pop("option_name", None)  # target changes require a fresh ownership check
    update = _clean_bid(body, partial=True)
    if not update:
        raise HTTPException(400, "Nothing to update")
    update["updated_at"] = _now()
    res = await db.admaker_bids.update_one(
        {"bid_id": bid_id, "created_by": user["user_id"]}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Bid not found")
    return await db.admaker_bids.find_one({"bid_id": bid_id}, {"_id": 0})


@router.delete("/my/bids/{bid_id}")
async def my_delete_bid(bid_id: str, user: dict = Depends(get_current_user)):
    await _require_admaker(user)
    res = await db.admaker_bids.delete_one({"bid_id": bid_id, "created_by": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Bid not found")
    return {"message": "deleted"}


@router.get("/my/dashboard")
async def my_dashboard(user: dict = Depends(get_current_user)):
    """Advertiser metrics: per-bid + account totals (impressions, clicks, CTR,
    spend, avg CPC, budget headroom)."""
    await _require_admaker(user)
    bids = await db.admaker_bids.find(
        {"created_by": user["user_id"]}, {"_id": 0}).to_list(200)
    tids = list({b["template_id"] for b in bids})
    titles = {t["template_id"]: t.get("title") for t in await db.decider_store_templates.find(
        {"template_id": {"$in": tids}}, {"_id": 0, "template_id": 1, "title": 1}).to_list(200)}
    tot_imp = tot_clk = tot_spend = 0
    rows = []
    for b in bids:
        imp, clk, spend = int(b.get("impressions") or 0), int(b.get("clicks") or 0), int(b.get("spent_paise") or 0)
        tot_imp += imp; tot_clk += clk; tot_spend += spend
        rows.append({**b, "template_title": titles.get(b["template_id"]) or b["template_id"],
                     "ctr_pct": round(clk / imp * 100.0, 2) if imp else 0.0,
                     "avg_cpc_paise": int(spend / clk) if clk else 0})
    return {"totals": {"bids": len(bids), "impressions": tot_imp, "clicks": tot_clk,
                       "ctr_pct": round(tot_clk / tot_imp * 100.0, 2) if tot_imp else 0.0,
                       "spend_paise": tot_spend,
                       "avg_cpc_paise": int(tot_spend / tot_clk) if tot_clk else 0},
            "bids": rows}


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
