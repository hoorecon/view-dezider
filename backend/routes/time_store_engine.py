"""
Time Store — curated marketplace to "buy back time".

Scope for v1 ("less complex" per product): the marketplace draws SUPPLY
from two existing collections:
  - pp_orgs (status="approved")   — registered Orgs in Public Pulse
  - solutions_store_solutions     — Solutions listed in Solutions Store

DEMAND is the user's own CTT tasks + lifestyle routines + Solution Matrix
roles. The engine computes a "time audit" surfacing tasks that could be
cut, delegated, automated or outsourced — using TEPFI levers (money trades
time, people trade time, etc.).

Endpoints:

  GET  /api/time-store/time-audit                      surface save opportunities
  GET  /api/time-store/services?save_minutes_per_day   list eligible Org solutions
  GET  /api/time-store/purchases                       my purchases
  POST /api/time-store/purchase                        buy a service (payment MOCKED till keys)
  POST /api/time-store/delegate                        request delegation (internal inbox)
  GET  /api/time-store/delegations                     my delegation requests

Payment integration: stubbed to mark status=pending_payment until Razorpay
keys are provisioned. When keys exist, the purchase endpoint flips to order
creation. The Razorpay layer already exists in routes/payments.py; this
route deliberately does NOT duplicate it.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user
from core.hardening import write_audit

router = APIRouter(prefix="/time-store", tags=["Time Store"])


SAVE_BUCKETS_PER_DAY = [30, 60, 120]     # 30min, 1h, 2h per day
SAVE_BUCKETS_PER_WEEK = [180, 300, 600, 900]  # 3h, 5h, 10h, 15h per week


class PurchaseBody(BaseModel):
    solution_id: str
    save_minutes_per_day: Optional[int] = None
    save_minutes_per_week: Optional[int] = None
    note: Optional[str] = None


class DelegateBody(BaseModel):
    source_type: str          # "ctt_task" | "lifestyle_area" | "matrix_cell"
    source_id: str
    description: str
    estimated_minutes_saved: int
    proposed_delegate_id: Optional[str] = None      # user_id or org_id
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Time Audit engine
# ---------------------------------------------------------------------------
async def _time_audit(user_id: str) -> Dict[str, Any]:
    # Pull user demand signals
    ctt = await db.ctt_tasks.find(
        {"user_id": user_id, "status": {"$in": ["active", "pending", "in_progress"]}},
        {"_id": 0},
    ).limit(200).to_list(200)
    lifestyle = await db.lifestyle_designs.find_one(
        {"user_id": user_id}, {"_id": 0}, sort=[("created_at", -1)],
    ) or {}
    matrix = await db.solution_matrices.find_one(
        {"user_id": user_id, "status": {"$in": ["in_progress", "completed"]}},
        {"_id": 0}, sort=[("updated_at", -1)],
    )

    opportunities: List[Dict[str, Any]] = []

    # 1) CTT tasks marked "low-importance / high-duration" → outsource candidates
    for t in ctt:
        prio = str(t.get("priority") or t.get("importance") or "medium").lower()
        dur = int(t.get("estimated_minutes") or t.get("duration_estimate") or 0)
        if dur < 20:
            continue  # not worth the overhead
        if prio in ("low", "someday"):
            opportunities.append({
                "opp_id": f"ctt_{t.get('task_id')}",
                "source_type": "ctt_task",
                "source_id": t.get("task_id"),
                "title": t.get("title") or "Task",
                "why": f"Low-importance task taking ~{dur} min — delegate or drop.",
                "suggested_action": "delegate",
                "tepfi_lever": "People",
                "minutes_saved_per_event": dur,
                "events_per_week": 1,
            })
        elif dur >= 45 and ("admin" in (t.get("category") or "").lower() or
                            "chore" in (t.get("tags") or [])):
            opportunities.append({
                "opp_id": f"ctt_out_{t.get('task_id')}",
                "source_type": "ctt_task",
                "source_id": t.get("task_id"),
                "title": t.get("title") or "Task",
                "why": f"Repeatable admin task ~{dur} min — outsource for a fee.",
                "suggested_action": "outsource",
                "tepfi_lever": "Finance",
                "minutes_saved_per_event": dur,
                "events_per_week": 2,
            })

    # 2) Lifestyle areas with zero adherence → drop or scale down
    for area in (lifestyle.get("areas") or []):
        planned_hpd = float(area.get("hours_per_day") or 0)
        if planned_hpd >= 1.5 and (area.get("name") or "").lower() in\
                {"social media", "entertainment", "scrolling", "news"}:
            opportunities.append({
                "opp_id": f"life_{area.get('area_id') or area.get('name')}",
                "source_type": "lifestyle_area",
                "source_id": area.get("area_id") or area.get("name"),
                "title": area.get("name") or "Lifestyle area",
                "why": f"Planned {planned_hpd} h/day on {area.get('name')} — biggest cut opportunity.",
                "suggested_action": "cut",
                "tepfi_lever": "Time",
                "minutes_saved_per_event": int(planned_hpd * 60 * 0.5),
                "events_per_week": 7,
            })

    # 3) Solution Matrix cells with note-keywords suggesting mundane work
    if matrix:
        for layer_key in ("matrix_self", "matrix_micro", "matrix_macro"):
            layer = matrix.get(layer_key) or {}
            for slot_key, cell in layer.items():
                if not isinstance(cell, dict): continue
                for fld in ("time", "people", "finance", "infrastructure"):
                    text = str(cell.get(fld) or "").lower()
                    if any(kw in text for kw in ("mundane", "routine", "repetitive", "boring", "chore")):
                        opportunities.append({
                            "opp_id": f"mx_{layer_key}_{slot_key}_{fld}",
                            "source_type": "matrix_cell",
                            "source_id": f"{layer_key}.{slot_key}.{fld}",
                            "title": f"{layer_key.replace('matrix_', '').upper()} · {slot_key} · {fld}",
                            "why": f"Flagged as mundane in your matrix — {text[:60]}…",
                            "suggested_action": "automate_or_outsource",
                            "tepfi_lever": "Finance" if fld == "finance" else "People",
                            "minutes_saved_per_event": 30,
                            "events_per_week": 5,
                        })

    # De-dup and sort
    seen = set(); dedup = []
    for o in opportunities:
        if o["opp_id"] in seen: continue
        seen.add(o["opp_id"])
        dedup.append(o)
    # Rank by total weekly minutes saved
    dedup.sort(key=lambda o: o["minutes_saved_per_event"] * o["events_per_week"], reverse=True)

    total_per_week = sum(o["minutes_saved_per_event"] * o["events_per_week"] for o in dedup)
    return {
        "opportunities": dedup[:20],
        "total_minutes_saveable_per_week": total_per_week,
        "total_hours_saveable_per_week": round(total_per_week / 60, 1),
    }


@router.get("/time-audit")
async def time_audit(user: dict = Depends(get_current_user)):
    return await _time_audit(user["user_id"])


# ---------------------------------------------------------------------------
# Service catalogue — curated via Org + Solutions Store
# ---------------------------------------------------------------------------
@router.get("/services")
async def list_services(
    user: dict = Depends(get_current_user),
    save_minutes_per_day: Optional[int] = None,
    save_minutes_per_week: Optional[int] = None,
    limit: int = 50,
):
    """Surface Solutions Store listings that claim to save time, filtered by
    requested save bucket. Orgs are auto-linked via solution.org_id.
    """
    # Solutions Store has two visibility paths for authorized listings:
    #   - system-seeded: is_authorized=True
    #   - user-submitted PUBLIC: visibility=PUBLIC + approval_status=approved
    vis_clause: List[Dict[str, Any]] = [
        {"is_authorized": True},
        {"visibility": "PUBLIC", "approval_status": "approved"},
    ]
    q: Dict[str, Any] = {"status": "active", "$or": vis_clause}
    if save_minutes_per_day:
        q["time_save_per_day_min"] = {"$gte": max(0, int(save_minutes_per_day) - 30)}
    if save_minutes_per_week:
        q["time_save_per_week_min"] = {"$gte": max(0, int(save_minutes_per_week) - 60)}

    cursor = db.solutions_store.find(q, {"_id": 0}).limit(min(max(limit, 1), 200))
    services = await cursor.to_list(200)

    # Attach org branding for each
    org_ids = list({s.get("org_id") for s in services if s.get("org_id")})
    orgs: Dict[str, Dict] = {}
    if org_ids:
        async for o in db.pp_orgs.find(
            {"org_id": {"$in": org_ids}, "status": "approved"},
            {"_id": 0, "org_id": 1, "display_name": 1, "slug": 1, "brand_color": 1,
             "categories": 1},
        ):
            orgs[o["org_id"]] = o
    enriched = []
    for s in services:
        oid = s.get("org_id")
        enriched.append({
            "solution_id": s.get("solution_id"),
            "title": s.get("name") or s.get("title"),
            "description": (s.get("description") or "")[:400],
            "price_inr": s.get("price_inr") or s.get("price_range"),
            "price_model": s.get("price_model"),
            "time_save_per_day_min": s.get("time_save_per_day_min"),
            "time_save_per_week_min": s.get("time_save_per_week_min"),
            "tags": s.get("tags", []),
            "rating_avg": s.get("rating_avg"),
            "rating_count": s.get("rating_count"),
            "org": orgs.get(oid),
        })
    return {
        "services": enriched,
        "buckets_per_day": SAVE_BUCKETS_PER_DAY,
        "buckets_per_week": SAVE_BUCKETS_PER_WEEK,
    }


# ---------------------------------------------------------------------------
# Purchases — mocked payment until Razorpay wired
# ---------------------------------------------------------------------------
@router.post("/purchase")
async def purchase(body: PurchaseBody, request: Request, user: dict = Depends(get_current_user)):
    sol = await db.solutions_store.find_one(
        {"solution_id": body.solution_id}, {"_id": 0},
    )
    if not sol:
        raise HTTPException(404, "Solution not found")
    order_id = f"TS-{uuid.uuid4().hex[:10]}"
    # NOTE: Payment is MOCKED pending Razorpay integration. Once keys are live,
    # this should create a Razorpay order and return orderId/key to the frontend.
    doc = {
        "order_id": order_id,
        "user_id": user["user_id"],
        "solution_id": body.solution_id,
        "solution_title": sol.get("name") or sol.get("title"),
        "org_id": sol.get("org_id") or sol.get("posted_by_org_id"),
        "price_inr": sol.get("price_inr"),
        "save_minutes_per_day": body.save_minutes_per_day,
        "save_minutes_per_week": body.save_minutes_per_week,
        "status": "pending_payment",     # MOCKED until Razorpay keys land
        "payment_provider": "mock",
        "note": body.note,
        "created_at": datetime.now(timezone.utc),
    }
    await db.time_store_purchases.insert_one(doc)
    await write_audit(db, action="time_store.purchase", actor_id=user["user_id"],
                      actor_email=user.get("email"), request=request,
                      metadata={"order_id": order_id, "solution_id": body.solution_id})
    return {
        "ok": True,
        "order_id": order_id,
        "status": "pending_payment",
        "note": "Payment is MOCKED pending Razorpay keys. Status will update to 'paid' once integration is live.",
    }


@router.get("/purchases")
async def my_purchases(user: dict = Depends(get_current_user), limit: int = 50):
    items = await db.time_store_purchases.find(
        {"user_id": user["user_id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(min(max(limit, 1), 200)).to_list(200)
    return {"items": items}


# ---------------------------------------------------------------------------
# Delegations — internal inbox routed to Contacts / Org members / family
# ---------------------------------------------------------------------------
@router.post("/delegate")
async def delegate(body: DelegateBody, request: Request, user: dict = Depends(get_current_user)):
    if body.source_type not in ("ctt_task", "lifestyle_area", "matrix_cell"):
        raise HTTPException(400, "source_type must be ctt_task|lifestyle_area|matrix_cell")
    delegation_id = f"DEL-{uuid.uuid4().hex[:10]}"
    doc = {
        "delegation_id": delegation_id,
        "requester_id": user["user_id"],
        "source_type": body.source_type,
        "source_id": body.source_id,
        "description": body.description[:2000],
        "estimated_minutes_saved": int(body.estimated_minutes_saved),
        "proposed_delegate_id": body.proposed_delegate_id,
        "status": "open",
        "note": body.note,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.time_store_delegations.insert_one(doc)
    await write_audit(db, action="time_store.delegate", actor_id=user["user_id"],
                      actor_email=user.get("email"), request=request,
                      metadata={"delegation_id": delegation_id,
                                "source_type": body.source_type,
                                "source_id": body.source_id})
    return {"ok": True, "delegation_id": delegation_id, "status": "open"}


@router.get("/delegations")
async def my_delegations(user: dict = Depends(get_current_user), limit: int = 50):
    items = await db.time_store_delegations.find(
        {"requester_id": user["user_id"]}, {"_id": 0},
    ).sort("created_at", -1).limit(min(max(limit, 1), 200)).to_list(200)
    return {"items": items}
