"""
ExpertNet — REST routes (Phases A-D in one module).

Phase A — Profiles + Discovery + Match
Phase B — Availability + Booking + Intake forms (built-in or external)
Phase C — Consultation sessions + Recommendations → CTT/Lifestyle + delivery tracking
Phase D — Webinars (1:many sessions, free or paid)
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import get_current_user, require_admin
from core.database import db
from models.expert_net_models import (
    AvailabilityUpdate,
    BookingCreate,
    DeliveryStatusUpdate,
    ExpertProfileCreate,
    ExpertProfileUpdate,
    ExpertRecommendation,
    IntakeFormUpsert,
    WebinarCreate,
    WebinarRegister,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/expert-net", tags=["ExpertNet"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip(d: dict) -> dict:
    if d and "_id" in d:
        d.pop("_id", None)
    return d


async def _ensure_indexes_once():
    await db.experts.create_index("expert_id", unique=True)
    await db.experts.create_index([("specializations", 1)])
    await db.experts.create_index([("catalog_node_ids", 1)])
    await db.experts.create_index([("is_active", 1), ("is_online", 1)])
    await db.expert_availability.create_index("expert_id", unique=True)
    await db.expert_intake_forms.create_index("expert_id", unique=True)
    await db.expert_bookings.create_index("booking_id", unique=True)
    await db.expert_bookings.create_index([("user_id", 1), ("status", 1)])
    await db.expert_bookings.create_index([("expert_id", 1), ("slot_start", 1)])
    await db.expert_recommendations.create_index([("user_id", 1), ("created_at", -1)])
    await db.expert_recommendations.create_index("booking_id")
    await db.expert_deliveries.create_index([("user_id", 1), ("created_at", -1)])
    await db.expert_deliveries.create_index("order_id")
    await db.expert_webinars.create_index("webinar_id", unique=True)
    await db.expert_webinars.create_index("starts_at")
    await db.expert_webinar_registrations.create_index([("webinar_id", 1), ("user_id", 1)], unique=True)


_indexes_ready = False


async def _ix_safe():
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await _ensure_indexes_once()
        _indexes_ready = True
    except Exception as e:
        logger.warning("expert_net indexes deferred: %s", e)


def _is_admin(user: dict) -> bool:
    return (user.get("role") or "user").lower() in ("admin", "co_admin", "super_admin")


# ===========================================================================
# Phase A — Expert profiles + discovery + match
# ===========================================================================
@router.post("/experts")
async def create_expert(body: ExpertProfileCreate, user: dict = Depends(get_current_user)):
    """Self-onboard or admin-create. The current user becomes the expert
    unless they're admin & set `org_id` for org-managed profile."""
    await _ix_safe()
    expert_id = f"ex_{uuid.uuid4().hex[:12]}"
    doc = {
        "expert_id": expert_id,
        "user_id": user["user_id"],
        "name": body.name,
        "headline": body.headline,
        "bio": body.bio,
        "specializations": body.specializations,
        "catalog_node_ids": body.catalog_node_ids,
        "languages": body.languages,
        "hourly_rate_inr": body.hourly_rate_inr,
        "intro_video_url": body.intro_video_url,
        "photo_url": body.photo_url,
        "time_zone": body.time_zone,
        "country": body.country,
        "city": body.city,
        "accepts_instant_calls": body.accepts_instant_calls,
        "is_active": body.is_active,
        "is_online": False,
        "org_id": body.org_id,
        "rating_avg": None,
        "rating_count": 0,
        "consult_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.experts.insert_one(doc)
    return _strip(doc)


@router.put("/experts/{expert_id}")
async def update_expert(expert_id: str, body: ExpertProfileUpdate, user: dict = Depends(get_current_user)):
    existing = await db.experts.find_one({"expert_id": expert_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "expert not found")
    if existing.get("user_id") != user["user_id"] and not _is_admin(user):
        raise HTTPException(403, "only the expert owner or admin can update")
    set_doc: Dict[str, Any] = {"updated_at": _now()}
    for f, v in body.model_dump(exclude_unset=True).items():
        set_doc[f] = v
    await db.experts.update_one({"expert_id": expert_id}, {"$set": set_doc})
    return _strip(await db.experts.find_one({"expert_id": expert_id}, {"_id": 0}))


@router.get("/experts")
async def list_experts(
    specialization: Optional[str] = Query(None),
    catalog_node_id: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    min_rate: Optional[int] = Query(None, ge=0),
    max_rate: Optional[int] = Query(None, ge=0),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    is_online: Optional[bool] = Query(None),
    only_instant: Optional[bool] = Query(None),
    sort: Optional[str] = Query(None),     # rating | rate_asc | rate_desc | newest
    user: dict = Depends(get_current_user),
):
    await _ix_safe()
    q: Dict[str, Any] = {"is_active": True}
    if specialization:
        q["specializations"] = {"$regex": specialization, "$options": "i"}
    if catalog_node_id:
        q["catalog_node_ids"] = catalog_node_id
    if language:
        q["languages"] = language
    if is_online is not None:
        q["is_online"] = is_online
    if only_instant:
        q["accepts_instant_calls"] = True
    if min_rate is not None or max_rate is not None:
        rate_q: Dict[str, Any] = {}
        if min_rate is not None:
            rate_q["$gte"] = min_rate
        if max_rate is not None:
            rate_q["$lte"] = max_rate
        q["hourly_rate_inr"] = rate_q
    if min_rating is not None:
        q["rating_avg"] = {"$gte": min_rating}

    cur = db.experts.find(q, {"_id": 0})
    if sort == "rating":
        cur = cur.sort([("rating_avg", -1), ("rating_count", -1)])
    elif sort == "rate_asc":
        cur = cur.sort("hourly_rate_inr", 1)
    elif sort == "rate_desc":
        cur = cur.sort("hourly_rate_inr", -1)
    elif sort == "newest":
        cur = cur.sort("created_at", -1)
    else:
        cur = cur.sort([("is_online", -1), ("rating_avg", -1), ("name", 1)])
    items = [_strip(d) for d in await cur.to_list(200)]
    return {"items": items, "count": len(items)}


@router.get("/experts/{expert_id}")
async def get_expert(expert_id: str, user: dict = Depends(get_current_user)):
    e = await db.experts.find_one({"expert_id": expert_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "expert not found")
    avail = await db.expert_availability.find_one({"expert_id": expert_id}, {"_id": 0})
    intake = await db.expert_intake_forms.find_one({"expert_id": expert_id}, {"_id": 0})
    return {"expert": _strip(e), "availability": _strip(avail) if avail else None, "intake_form": _strip(intake) if intake else None}


@router.post("/experts/{expert_id}/online")
async def set_online(expert_id: str, body: dict, user: dict = Depends(get_current_user)):
    """Expert toggles online presence. Body: {is_online: bool}"""
    e = await db.experts.find_one({"expert_id": expert_id}, {"_id": 1, "user_id": 1})
    if not e:
        raise HTTPException(404, "expert not found")
    if e.get("user_id") != user["user_id"] and not _is_admin(user):
        raise HTTPException(403, "not allowed")
    await db.experts.update_one(
        {"expert_id": expert_id},
        {"$set": {"is_online": bool(body.get("is_online")), "updated_at": _now()}},
    )
    return {"ok": True, "is_online": bool(body.get("is_online"))}


@router.post("/experts/{expert_id}/connect-now")
async def connect_now(expert_id: str, user: dict = Depends(get_current_user)):
    """Direct-connect to an online + accepts_instant expert.
    Returns a video_call session id (or 409 if expert offline / unavailable).
    """
    e = await db.experts.find_one({"expert_id": expert_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "expert not found")
    if not e.get("is_online") or not e.get("accepts_instant_calls"):
        raise HTTPException(409, "expert is not available for instant calls right now")
    session_id = f"vc_{uuid.uuid4().hex[:12]}"
    await db.video_call_sessions.insert_one({
        "session_id": session_id,
        "kind": "expert_consult",
        "expert_id": expert_id,
        "host_user_id": e.get("user_id"),
        "guest_user_id": user["user_id"],
        "status": "ringing",
        "created_at": _now(),
    })
    return {"ok": True, "session_id": session_id, "video_url": f"/tools/collab-call?session_id={session_id}"}


# ===========================================================================
# Phase B — Availability + Booking + Intake forms
# ===========================================================================
@router.put("/experts/{expert_id}/availability")
async def upsert_availability(expert_id: str, body: AvailabilityUpdate, user: dict = Depends(get_current_user)):
    e = await db.experts.find_one({"expert_id": expert_id}, {"_id": 0, "user_id": 1, "time_zone": 1})
    if not e:
        raise HTTPException(404, "expert not found")
    if e.get("user_id") != user["user_id"] and not _is_admin(user):
        raise HTTPException(403, "not allowed")
    doc = {
        "expert_id": expert_id,
        "windows": [w.model_dump() for w in body.windows],
        "blackout_dates": body.blackout_dates,
        "time_zone": e.get("time_zone") or "Asia/Kolkata",
        "updated_at": _now(),
    }
    await db.expert_availability.update_one(
        {"expert_id": expert_id}, {"$set": doc}, upsert=True,
    )
    return doc


@router.put("/experts/{expert_id}/intake-form")
async def upsert_intake(expert_id: str, body: IntakeFormUpsert, user: dict = Depends(get_current_user)):
    e = await db.experts.find_one({"expert_id": expert_id}, {"_id": 0, "user_id": 1})
    if not e:
        raise HTTPException(404, "expert not found")
    if e.get("user_id") != user["user_id"] and not _is_admin(user):
        raise HTTPException(403, "not allowed")
    if body.mode == "external" and not body.external_url:
        raise HTTPException(400, "external_url required when mode=external")
    if body.mode == "builtin" and not body.fields:
        raise HTTPException(400, "at least one field required when mode=builtin")
    doc = {
        "expert_id": expert_id,
        "title": body.title,
        "description": body.description,
        "mode": body.mode,
        "external_url": body.external_url,
        "fields": [f.model_dump() for f in body.fields],
        "is_required_before_booking": body.is_required_before_booking,
        "updated_at": _now(),
    }
    await db.expert_intake_forms.update_one({"expert_id": expert_id}, {"$set": doc}, upsert=True)
    return doc


@router.get("/experts/{expert_id}/slots")
async def list_slots(
    expert_id: str,
    days_ahead: int = Query(14, ge=1, le=60),
    user: dict = Depends(get_current_user),
):
    """Return open slots over the next N days, after subtracting existing bookings."""
    e = await db.experts.find_one({"expert_id": expert_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "expert not found")
    avail = await db.expert_availability.find_one({"expert_id": expert_id}, {"_id": 0})
    if not avail:
        return {"slots": [], "count": 0}

    blackout = set(avail.get("blackout_dates") or [])
    windows = avail.get("windows") or []

    # existing bookings to exclude
    cur = db.expert_bookings.find(
        {"expert_id": expert_id, "status": {"$in": ["pending", "confirmed"]},
         "slot_start": {"$gte": _now()}}, {"_id": 0, "slot_start": 1, "slot_end": 1},
    )
    booked = [(b["slot_start"], b["slot_end"]) async for b in cur]

    out: List[dict] = []
    today = datetime.now(timezone.utc).date()
    for offset in range(days_ahead):
        d = today + timedelta(days=offset)
        if d.isoformat() in blackout:
            continue
        wd = d.weekday()
        for w in windows:
            if w["weekday"] != wd:
                continue
            cursor_minutes = w["start_minutes"]
            while cursor_minutes + w["slot_minutes"] <= w["end_minutes"]:
                start = datetime(d.year, d.month, d.day, cursor_minutes // 60, cursor_minutes % 60, tzinfo=timezone.utc)
                end = start + timedelta(minutes=w["slot_minutes"])
                clash = any(not (end <= bs or start >= be) for bs, be in booked)
                if not clash and start > _now():
                    out.append({"start": start.isoformat(), "end": end.isoformat(), "duration_minutes": w["slot_minutes"]})
                cursor_minutes += w["slot_minutes"]
    return {"slots": out[:200], "count": len(out)}


@router.post("/bookings")
async def create_booking(body: BookingCreate, user: dict = Depends(get_current_user)):
    e = await db.experts.find_one({"expert_id": body.expert_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "expert not found")
    intake = await db.expert_intake_forms.find_one({"expert_id": body.expert_id}, {"_id": 0})

    # Validate intake (only enforce for builtin mode)
    if intake and intake.get("is_required_before_booking", True):
        if intake.get("mode") == "builtin":
            answers = body.intake_response or {}
            for fld in intake.get("fields") or []:
                if fld.get("required") and not answers.get(fld["field_id"]):
                    raise HTTPException(400, f"intake field '{fld['field_id']}' is required")

    # parse slot
    try:
        slot_start = datetime.fromisoformat(body.slot_start_iso.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(400, "slot_start_iso invalid")
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=timezone.utc)
    slot_end = slot_start + timedelta(minutes=body.duration_minutes)

    # Conflict check
    clash = await db.expert_bookings.find_one({
        "expert_id": body.expert_id,
        "status": {"$in": ["pending", "confirmed"]},
        "slot_start": {"$lt": slot_end},
        "slot_end": {"$gt": slot_start},
    }, {"_id": 1})
    if clash:
        raise HTTPException(409, "slot already booked")

    booking_id = f"bk_{uuid.uuid4().hex[:12]}"
    doc = {
        "booking_id": booking_id,
        "expert_id": body.expert_id,
        "expert_name": e.get("name"),
        "user_id": user["user_id"],
        "user_name": user.get("name") or user.get("email"),
        "slot_start": slot_start,
        "slot_end": slot_end,
        "duration_minutes": body.duration_minutes,
        "intake_response": body.intake_response or {},
        "intake_external_url": (intake or {}).get("external_url"),
        "intake_mode": (intake or {}).get("mode"),
        "note": body.note,
        "decision_id": body.decision_id,
        "solution_id": body.solution_id,
        "status": "pending" if e.get("hourly_rate_inr") else "confirmed",
        "video_session_id": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.expert_bookings.insert_one(doc)

    # Notify expert + user (in-app)
    try:
        for uid, msg in (
            (e.get("user_id"), f"New booking by {doc['user_name']} on {slot_start.strftime('%Y-%m-%d %H:%M UTC')}"),
            (user["user_id"], f"Booking with {e.get('name')} {'pending payment' if doc['status'] == 'pending' else 'confirmed'} for {slot_start.strftime('%Y-%m-%d %H:%M UTC')}"),
        ):
            if uid:
                await db.notifications.insert_one({
                    "id": f"nt_xn_{uuid.uuid4().hex[:10]}",
                    "user_id": uid,
                    "title": "Expert booking",
                    "message": msg,
                    "type": "expert_net",
                    "url": f"/tools/expert-net/booking?booking_id={booking_id}",
                    "read": False,
                    "created_at": _now(),
                })
    except Exception:
        pass

    return _strip(doc)


@router.get("/bookings")
async def my_bookings(
    role: str = Query("user"),                # "user" or "expert"
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    if role == "expert":
        my_experts = [e["expert_id"] async for e in db.experts.find({"user_id": user["user_id"]}, {"_id": 0, "expert_id": 1})]
        if not my_experts:
            return {"items": [], "count": 0}
        q: Dict[str, Any] = {"expert_id": {"$in": my_experts}}
    else:
        q = {"user_id": user["user_id"]}
    if status:
        q["status"] = status
    cur = db.expert_bookings.find(q, {"_id": 0}).sort("slot_start", -1)
    items = [_strip(d) for d in await cur.to_list(200)]
    return {"items": items, "count": len(items)}


@router.post("/bookings/{booking_id}/confirm")
async def confirm_booking(booking_id: str, user: dict = Depends(get_current_user)):
    b = await db.expert_bookings.find_one({"booking_id": booking_id}, {"_id": 0})
    if not b:
        raise HTTPException(404, "booking not found")
    e = await db.experts.find_one({"expert_id": b["expert_id"]}, {"_id": 0, "user_id": 1})
    if not (_is_admin(user) or (e and e.get("user_id") == user["user_id"])):
        raise HTTPException(403, "only the expert can confirm")
    await db.expert_bookings.update_one({"booking_id": booking_id}, {"$set": {"status": "confirmed", "updated_at": _now()}})
    return {"ok": True, "status": "confirmed"}


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, user: dict = Depends(get_current_user)):
    b = await db.expert_bookings.find_one({"booking_id": booking_id}, {"_id": 0})
    if not b:
        raise HTTPException(404, "booking not found")
    e = await db.experts.find_one({"expert_id": b["expert_id"]}, {"_id": 0, "user_id": 1})
    can = (b.get("user_id") == user["user_id"]) or (e and e.get("user_id") == user["user_id"]) or _is_admin(user)
    if not can:
        raise HTTPException(403, "not allowed")
    await db.expert_bookings.update_one({"booking_id": booking_id}, {"$set": {"status": "cancelled", "updated_at": _now()}})
    return {"ok": True, "status": "cancelled"}


@router.post("/bookings/{booking_id}/start-call")
async def start_booking_call(booking_id: str, user: dict = Depends(get_current_user)):
    b = await db.expert_bookings.find_one({"booking_id": booking_id}, {"_id": 0})
    if not b or b.get("status") not in ("confirmed", "in_progress"):
        raise HTTPException(404, "booking not confirmed")
    if b.get("video_session_id"):
        return {"session_id": b["video_session_id"], "video_url": f"/tools/collab-call?session_id={b['video_session_id']}"}
    sid = f"vc_{uuid.uuid4().hex[:12]}"
    await db.video_call_sessions.insert_one({
        "session_id": sid, "kind": "expert_booking",
        "booking_id": booking_id,
        "host_user_id": (await db.experts.find_one({"expert_id": b["expert_id"]}, {"_id": 0, "user_id": 1}) or {}).get("user_id"),
        "guest_user_id": b["user_id"],
        "status": "ringing", "created_at": _now(),
    })
    await db.expert_bookings.update_one(
        {"booking_id": booking_id},
        {"$set": {"video_session_id": sid, "status": "in_progress", "updated_at": _now()}},
    )
    return {"session_id": sid, "video_url": f"/tools/collab-call?session_id={sid}"}


# ===========================================================================
# Phase C — Recommendations → CTT/Lifestyle + delivery tracking
# ===========================================================================
@router.post("/bookings/{booking_id}/recommend")
async def add_recommendation(
    booking_id: str, body: ExpertRecommendation, user: dict = Depends(get_current_user),
):
    """Expert recommends a Solution Store item to the user as part of consulting.
    Auto-creates a CTT task and/or a Lifestyle routine on the user's account.
    """
    b = await db.expert_bookings.find_one({"booking_id": booking_id}, {"_id": 0})
    if not b:
        raise HTTPException(404, "booking not found")
    e = await db.experts.find_one({"expert_id": b["expert_id"]}, {"_id": 0, "user_id": 1, "name": 1})
    if not (_is_admin(user) or (e and e.get("user_id") == user["user_id"])):
        raise HTTPException(403, "only the expert can add recommendations")

    sol = await db.solutions_store.find_one({"solution_id": body.solution_id}, {"_id": 0})
    if not sol:
        raise HTTPException(404, "solution not found")

    rec_id = f"rc_{uuid.uuid4().hex[:12]}"
    doc = {
        "recommendation_id": rec_id,
        "booking_id": booking_id,
        "expert_id": b["expert_id"],
        "expert_name": e.get("name") if e else None,
        "user_id": b["user_id"],
        "solution_id": body.solution_id,
        "solution_name": sol.get("name") or sol.get("title"),
        "note": body.note,
        "create_ctt_task": body.create_ctt_task,
        "create_lifestyle_routine": body.create_lifestyle_routine,
        "routine_frequency": body.routine_frequency,
        "linked_ctt_task_id": None,
        "linked_routine_id": None,
        "created_at": _now(),
    }

    # Auto-create CTT task on the user's account
    if body.create_ctt_task:
        ctt_id = f"ct_{uuid.uuid4().hex[:10]}"
        await db.ctt_tasks.insert_one({
            "task_id": ctt_id,
            "user_id": b["user_id"],
            "title": f"Try: {sol.get('name') or sol.get('title')}",
            "description": (body.note or "") + f"\n\nRecommended by {(e or {}).get('name') or 'expert'}",
            "category": "expert_recommended",
            "source": "expert_net",
            "source_ref": rec_id,
            "is_active": True,
            "created_at": _now(),
            "day_status": {},
        })
        doc["linked_ctt_task_id"] = ctt_id

    # Auto-create lifestyle routine
    if body.create_lifestyle_routine:
        r_id = f"lr_{uuid.uuid4().hex[:10]}"
        await db.lifestyle_routines.insert_one({
            "routine_id": r_id,
            "user_id": b["user_id"],
            "title": f"Routine: {sol.get('name') or sol.get('title')}",
            "frequency": body.routine_frequency,
            "source": "expert_net",
            "source_ref": rec_id,
            "is_active": True,
            "created_at": _now(),
        })
        doc["linked_routine_id"] = r_id

    await db.expert_recommendations.insert_one(doc)

    # Notify user
    try:
        await db.notifications.insert_one({
            "id": f"nt_rec_{uuid.uuid4().hex[:10]}",
            "user_id": b["user_id"],
            "title": "New expert recommendation",
            "message": f"{(e or {}).get('name') or 'Expert'} recommended {sol.get('name') or sol.get('title')}",
            "type": "expert_net",
            "url": "/tools/expert-net/recommendations",
            "read": False,
            "created_at": _now(),
        })
    except Exception:
        pass

    return _strip(doc)


@router.get("/recommendations")
async def my_recommendations(user: dict = Depends(get_current_user)):
    cur = db.expert_recommendations.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1)
    return {"items": [_strip(d) for d in await cur.to_list(200)]}


# ---- Delivery tracking (eCommerce-lite) -----------------------------------
@router.post("/deliveries/from-purchase/{order_id}")
async def init_delivery_from_purchase(order_id: str, user: dict = Depends(get_current_user)):
    """Convert a Time Store purchase into a delivery-trackable order.
    Status starts at 'ordered'."""
    p = await db.time_store_purchases.find_one({"order_id": order_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "purchase not found")
    if p["user_id"] != user["user_id"] and not _is_admin(user):
        raise HTTPException(403, "not your order")
    existing = await db.expert_deliveries.find_one({"order_id": order_id}, {"_id": 0})
    if existing:
        return _strip(existing)
    doc = {
        "order_id": order_id,
        "user_id": p["user_id"],
        "solution_id": p.get("solution_id"),
        "solution_name": p.get("solution_title") or p.get("solution_name"),
        "status": "ordered",
        "history": [{"status": "ordered", "at": _now(), "note": "Order placed"}],
        "tracking_number": None,
        "tracking_url": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.expert_deliveries.insert_one(doc)
    return _strip(doc)


@router.put("/deliveries/{order_id}/status")
async def update_delivery_status(order_id: str, body: DeliveryStatusUpdate, user: dict = Depends(get_current_user)):
    """Provider/admin updates delivery status; user can mark 'delivered' as confirmation."""
    d = await db.expert_deliveries.find_one({"order_id": order_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "delivery not found")
    if not (_is_admin(user) or d["user_id"] == user["user_id"]):
        raise HTTPException(403, "not allowed")
    set_doc = {
        "status": body.status,
        "tracking_number": body.tracking_number or d.get("tracking_number"),
        "tracking_url": body.tracking_url or d.get("tracking_url"),
        "updated_at": _now(),
    }
    history_event = {"status": body.status, "at": _now(), "note": body.note or ""}
    await db.expert_deliveries.update_one(
        {"order_id": order_id},
        {"$set": set_doc, "$push": {"history": history_event}},
    )
    return _strip(await db.expert_deliveries.find_one({"order_id": order_id}, {"_id": 0}))


@router.get("/deliveries")
async def my_deliveries(user: dict = Depends(get_current_user)):
    cur = db.expert_deliveries.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1)
    return {"items": [_strip(d) for d in await cur.to_list(200)]}


# ===========================================================================
# Phase D — 1:many Webinars
# ===========================================================================
@router.post("/webinars")
async def create_webinar(body: WebinarCreate, user: dict = Depends(get_current_user)):
    """Expert announces a free or paid webinar / one-to-many session."""
    my_experts = [e async for e in db.experts.find({"user_id": user["user_id"]}, {"_id": 0})]
    if not my_experts and not _is_admin(user):
        raise HTTPException(403, "only experts (or admin) can create webinars")
    expert = my_experts[0] if my_experts else None

    try:
        starts = datetime.fromisoformat(body.starts_at_iso.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(400, "starts_at_iso invalid")
    if starts.tzinfo is None:
        starts = starts.replace(tzinfo=timezone.utc)

    webinar_id = f"wb_{uuid.uuid4().hex[:12]}"
    doc = {
        "webinar_id": webinar_id,
        "title": body.title,
        "description": body.description,
        "starts_at": starts,
        "duration_minutes": body.duration_minutes,
        "capacity": body.capacity,
        "price_inr": body.price_inr,
        "is_free": body.is_free or body.price_inr == 0,
        "currency": "INR",
        "language": body.language,
        "catalog_node_ids": body.catalog_node_ids,
        "expert_id": expert["expert_id"] if expert else None,
        "expert_name": expert["name"] if expert else None,
        "host_user_id": user["user_id"],
        "registered_count": 0,
        "status": "scheduled",
        "video_session_id": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.expert_webinars.insert_one(doc)
    return _strip(doc)


@router.get("/webinars")
async def list_webinars(
    upcoming_only: bool = Query(True),
    catalog_node_id: Optional[str] = Query(None),
    free_only: Optional[bool] = Query(None),
    user: dict = Depends(get_current_user),
):
    q: Dict[str, Any] = {"status": {"$in": ["scheduled", "live"]}}
    if upcoming_only:
        q["starts_at"] = {"$gte": _now() - timedelta(hours=1)}
    if catalog_node_id:
        q["catalog_node_ids"] = catalog_node_id
    if free_only is True:
        q["is_free"] = True
    cur = db.expert_webinars.find(q, {"_id": 0}).sort("starts_at", 1)
    items = [_strip(d) for d in await cur.to_list(200)]
    # mark which the user has already registered for
    registered = {
        r["webinar_id"]
        async for r in db.expert_webinar_registrations.find(
            {"user_id": user["user_id"], "webinar_id": {"$in": [w["webinar_id"] for w in items]}},
            {"_id": 0, "webinar_id": 1},
        )
    }
    for w in items:
        w["i_am_registered"] = w["webinar_id"] in registered
    return {"items": items, "count": len(items)}


@router.post("/webinars/register")
async def register_webinar(body: WebinarRegister, user: dict = Depends(get_current_user)):
    w = await db.expert_webinars.find_one({"webinar_id": body.webinar_id}, {"_id": 0})
    if not w:
        raise HTTPException(404, "webinar not found")
    if w.get("capacity") and w.get("registered_count", 0) >= w["capacity"]:
        raise HTTPException(409, "webinar is full")

    payment_status = "paid_free" if w.get("is_free") else "pending_payment"   # MOCKED until Razorpay live keys
    try:
        await db.expert_webinar_registrations.insert_one({
            "registration_id": f"wr_{uuid.uuid4().hex[:10]}",
            "webinar_id": body.webinar_id,
            "user_id": user["user_id"],
            "user_name": user.get("name") or user.get("email"),
            "payment_status": payment_status,
            "payment_provider": "free" if w.get("is_free") else "mock",
            "amount_inr": 0 if w.get("is_free") else w.get("price_inr") or 0,
            "registered_at": _now(),
        })
    except Exception:
        # already registered (unique index)
        return {"ok": True, "already_registered": True}

    await db.expert_webinars.update_one({"webinar_id": body.webinar_id}, {"$inc": {"registered_count": 1}})
    return {"ok": True, "payment_status": payment_status}


@router.post("/webinars/{webinar_id}/start")
async def start_webinar(webinar_id: str, user: dict = Depends(get_current_user)):
    """Host expert flips webinar to live + creates a video session for the broadcast."""
    w = await db.expert_webinars.find_one({"webinar_id": webinar_id}, {"_id": 0})
    if not w:
        raise HTTPException(404, "webinar not found")
    if w["host_user_id"] != user["user_id"] and not _is_admin(user):
        raise HTTPException(403, "only host can start")
    sid = w.get("video_session_id") or f"vc_wb_{uuid.uuid4().hex[:10]}"
    await db.video_call_sessions.insert_one({
        "session_id": sid,
        "kind": "webinar",
        "webinar_id": webinar_id,
        "host_user_id": user["user_id"],
        "status": "live",
        "created_at": _now(),
    })
    await db.expert_webinars.update_one(
        {"webinar_id": webinar_id},
        {"$set": {"status": "live", "video_session_id": sid, "updated_at": _now()}},
    )
    return {"ok": True, "session_id": sid, "video_url": f"/tools/collab-call?session_id={sid}"}


@router.get("/webinars/{webinar_id}")
async def get_webinar(webinar_id: str, user: dict = Depends(get_current_user)):
    w = await db.expert_webinars.find_one({"webinar_id": webinar_id}, {"_id": 0})
    if not w:
        raise HTTPException(404, "webinar not found")
    reg = await db.expert_webinar_registrations.find_one(
        {"webinar_id": webinar_id, "user_id": user["user_id"]}, {"_id": 0},
    )
    return {"webinar": _strip(w), "my_registration": _strip(reg) if reg else None}
