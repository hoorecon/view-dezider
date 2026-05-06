"""
LDC routes — Life Directions Compass.

  GET    /api/ldc/me                    — my freedoms (auto-seeds 7 defaults if first call)
  PUT    /api/ldc/me                    — set/reorder/add/remove freedoms (+ influence_pct)
  POST   /api/ldc/me/pin                — pin one freedom for the current week (Q2c hybrid)
  GET    /api/ldc/seed                  — default 7 + reserved 3 (for onboarding chooser)
  POST   /api/ldc/me/reset              — wipe + reseed defaults (debug/onboarding redo)
  GET    /api/ldc/me/weight/{key}       — numeric weight for a single freedom (used by Time Dezider)

Weight model: rank 1 → 10.0; linear down to rank 10 → 1.0.
This-week pin: extra 1.5x multiplier on Time Dezider's ldc_alignment factor.
Pin auto-clears every Sunday 23:59 UTC.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from core.database import db
from core.auth import get_current_user
from models.life_directions_models import (
    DEFAULT_FREEDOMS, RESERVED_SUGGESTIONS, LDCSetBody, PinThisWeekBody,
    seed_default_freedoms, weight_from_rank,
)

router = APIRouter(prefix="/ldc", tags=["Life Directions Compass"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_sunday_2359_utc() -> datetime:
    n = _now()
    days_until_sun = (6 - n.weekday()) % 7
    if days_until_sun == 0:
        days_until_sun = 7
    target = (n + timedelta(days=days_until_sun)).replace(hour=23, minute=59, second=0, microsecond=0)
    return target


async def _get_or_seed(user_id: str) -> Dict[str, Any]:
    """Read user's LDC doc or seed it with the 7 defaults."""
    doc = await db.ldc.find_one({"user_id": user_id}, {"_id": 0})
    if doc:
        # Auto-clear expired pins
        n = _now()
        changed = False
        for f in doc.get("freedoms", []):
            pu = f.get("pinned_until")
            # MongoDB sometimes returns offset-naive; coerce to UTC
            if pu and getattr(pu, "tzinfo", None) is None:
                pu = pu.replace(tzinfo=timezone.utc)
            if f.get("pinned_this_week") and pu and pu < n:
                f["pinned_this_week"] = False
                f["pinned_until"] = None
                changed = True
        if changed:
            await db.ldc.update_one({"user_id": user_id}, {"$set": {"freedoms": doc["freedoms"]}})
        return doc
    seed = {
        "user_id": user_id,
        "freedoms": seed_default_freedoms(),
        "influence_pct": 30,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.ldc.insert_one(seed.copy())
    seed.pop("_id", None)
    return seed


def _attach_weights(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Compute & attach weight per freedom (auto-rebalanced from rank)."""
    fr = sorted(doc.get("freedoms", []), key=lambda x: x.get("rank", 999))
    for i, f in enumerate(fr, start=1):
        f["rank"] = i
        f["weight"] = weight_from_rank(i)
    doc["freedoms"] = fr
    return doc


@router.get("/seed")
async def get_seed_library():
    """Returns the default 7 + reserved 3 (un-personalised). For onboarding."""
    return {"defaults": DEFAULT_FREEDOMS, "reserved": RESERVED_SUGGESTIONS}


@router.get("/me")
async def get_my_compass(user: dict = Depends(get_current_user)):
    doc = await _get_or_seed(user["user_id"])
    doc = _attach_weights(doc)
    return {"ok": True, "compass": doc, "reserved_suggestions": RESERVED_SUGGESTIONS}


@router.put("/me")
async def set_my_compass(body: LDCSetBody, user: dict = Depends(get_current_user)):
    """Replace the user's freedoms list (rank = position in array)."""
    if not body.freedoms:
        raise HTTPException(400, "freedoms list cannot be empty")
    if len(body.freedoms) > 30:
        raise HTTPException(400, "max 30 freedoms")

    cleaned = []
    seen_keys = set()
    for i, f in enumerate(body.freedoms, start=1):
        key = str(f.get("key", "")).strip().lower().replace(" ", "_")[:40]
        label = str(f.get("label", "")).strip()[:120]
        if not key or not label:
            raise HTTPException(400, f"freedom #{i} is missing key or label")
        if key in seen_keys:
            raise HTTPException(400, f"duplicate key '{key}'")
        seen_keys.add(key)
        cleaned.append({
            "key": key, "label": label, "rank": i,
            "icon": f.get("icon"), "color": f.get("color"),
            "custom": bool(f.get("custom", key not in [d["key"] for d in DEFAULT_FREEDOMS + RESERVED_SUGGESTIONS])),
            "pinned_this_week": bool(f.get("pinned_this_week", False)),
            "pinned_until": f.get("pinned_until"),
        })

    update: Dict[str, Any] = {"freedoms": cleaned, "updated_at": _now()}
    if body.influence_pct is not None:
        update["influence_pct"] = max(0, min(100, int(body.influence_pct)))

    await db.ldc.update_one(
        {"user_id": user["user_id"]},
        {"$set": update, "$setOnInsert": {"user_id": user["user_id"], "created_at": _now()}},
        upsert=True,
    )
    doc = await db.ldc.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {"ok": True, "compass": _attach_weights(doc)}


@router.post("/me/pin")
async def pin_this_week(body: PinThisWeekBody, user: dict = Depends(get_current_user)):
    """Pin one freedom (or unpin all if key is None) until next Sunday 23:59 UTC."""
    doc = await _get_or_seed(user["user_id"])
    until = _next_sunday_2359_utc() if body.key else None
    new_freedoms = []
    found = False
    for f in doc.get("freedoms", []):
        is_target = body.key and f["key"] == body.key
        if is_target:
            found = True
        new_freedoms.append({
            **f,
            "pinned_this_week": bool(is_target),
            "pinned_until": until if is_target else None,
        })
    if body.key and not found:
        raise HTTPException(404, f"freedom key '{body.key}' not in your list")
    await db.ldc.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"freedoms": new_freedoms, "updated_at": _now()}},
    )
    return {"ok": True, "pinned_key": body.key, "pinned_until": until}


@router.post("/me/reset")
async def reset_to_defaults(user: dict = Depends(get_current_user)):
    """Wipe + reseed defaults. Useful for onboarding redo."""
    seed = {
        "user_id": user["user_id"],
        "freedoms": seed_default_freedoms(),
        "influence_pct": 30,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.ldc.replace_one({"user_id": user["user_id"]}, seed, upsert=True)
    seed.pop("_id", None)
    return {"ok": True, "compass": _attach_weights(seed)}


@router.get("/me/weight/{key}")
async def get_freedom_weight(key: str, user: dict = Depends(get_current_user)):
    """Used by Time Dezider — returns weight for a single freedom (with pin multiplier)."""
    doc = await _get_or_seed(user["user_id"])
    doc = _attach_weights(doc)
    f = next((x for x in doc["freedoms"] if x["key"] == key), None)
    if not f:
        return {"key": key, "weight": 0.0, "pinned": False}
    weight = float(f.get("weight", 1.0))
    if f.get("pinned_this_week"):
        weight *= 1.5  # Q2c hybrid — pinned freedom gets 1.5x multiplier
    return {"key": key, "weight": round(weight, 2), "pinned": bool(f.get("pinned_this_week"))}
