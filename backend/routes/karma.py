"""
Karma, Ratings & Fame (Collaboration Epic Phase F).

Beneficiaries rate the value they received (a cloned marketplace decision, or an
accepted public-help contribution). Ratings update the provider's fame profile
and award Karma points (per the admin Karma config). A public leaderboard ranks
users by karma; each user has a public fame profile.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.auth import get_current_user, require_admin
from core.database import db
from core import karma as karma_engine

router = APIRouter(prefix="/karma", tags=["Karma & Fame"])
admin_router = APIRouter(prefix="/admin/karma", tags=["Admin Karma"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _names_for(user_ids: List[str]) -> Dict[str, str]:
    if not user_ids:
        return {}
    out: Dict[str, str] = {}
    async for u in db.users.find({"user_id": {"$in": list(set(user_ids))}}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}):
        out[u["user_id"]] = u.get("name") or (u.get("email") or "").split("@")[0] or "Member"
    return out


# ---------------------------------------------------------------------------
# ratings
# ---------------------------------------------------------------------------
class RateRequest(BaseModel):
    stars: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


async def _recompute_provider_fame(provider_id: str):
    pipeline = [
        {"$match": {"provider_id": provider_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$stars"}, "count": {"$sum": 1}}},
    ]
    agg = [r async for r in db.ratings.aggregate(pipeline)]
    avg = round(agg[0]["avg"], 2) if agg else None
    count = agg[0]["count"] if agg else 0
    await db.referral_profiles.update_one(
        {"user_id": provider_id},
        {"$set": {"fame_rating_avg": avg, "fame_rating_count": count},
         "$setOnInsert": {"user_id": provider_id, "karma_balance": 0, "cash_balance_inr": 0.0}},
        upsert=True,
    )


async def _recompute_target(target_type: str, target_id: str):
    pipeline = [
        {"$match": {"target_type": target_type, "target_id": target_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$stars"}, "count": {"$sum": 1}}},
    ]
    agg = [r async for r in db.ratings.aggregate(pipeline)]
    avg = round(agg[0]["avg"], 2) if agg else None
    count = agg[0]["count"] if agg else 0
    if target_type == "listing":
        await db.marketplace_listings.update_one({"listing_id": target_id}, {"$set": {"rating_avg": avg, "rating_count": count}})
    elif target_type == "contribution":
        await db.public_help_contributions.update_one({"contribution_id": target_id}, {"$set": {"rating_avg": avg, "rating_count": count}})


async def _save_rating(rater: dict, target_type: str, target_id: str, provider_id: str, stars: int, comment: Optional[str]):
    if provider_id == rater["user_id"]:
        raise HTTPException(400, "You can't rate your own contribution")
    existing = await db.ratings.find_one({"rater_id": rater["user_id"], "target_type": target_type, "target_id": target_id}, {"_id": 0})
    is_new = existing is None
    doc = {
        "rater_id": rater["user_id"],
        "rater_name": rater.get("name") or rater.get("email"),
        "target_type": target_type,
        "target_id": target_id,
        "provider_id": provider_id,
        "stars": stars,
        "comment": (comment or "").strip(),
        "updated_at": _now(),
    }
    if is_new:
        doc["rating_id"] = f"rate_{uuid.uuid4().hex[:12]}"
        doc["created_at"] = _now()
        await db.ratings.insert_one(doc)
    else:
        await db.ratings.update_one({"rater_id": rater["user_id"], "target_type": target_type, "target_id": target_id}, {"$set": doc})
    await _recompute_provider_fame(provider_id)
    await _recompute_target(target_type, target_id)
    awarded = 0
    if is_new and stars >= 3:
        awarded = await karma_engine.award_karma(
            provider_id, "positive_rating", multiplier=stars,
            ref={"target_type": target_type, "target_id": target_id},
            reason=f"{stars}★ rating received",
        )
    return {"ok": True, "stars": stars, "karma_awarded": awarded, "new": is_new}


@router.post("/rate/marketplace/{listing_id}")
async def rate_listing(listing_id: str, body: RateRequest, user: dict = Depends(get_current_user)):
    listing = await db.marketplace_listings.find_one({"listing_id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(404, "Listing not found")
    cloned = await db.marketplace_clones.find_one({"listing_id": listing_id, "buyer_id": user["user_id"]}, {"_id": 1})
    if not cloned:
        raise HTTPException(403, "Only people who cloned this decision can rate it")
    return await _save_rating(user, "listing", listing_id, listing["owner_id"], body.stars, body.comment)


@router.post("/rate/contribution/{contribution_id}")
async def rate_contribution(contribution_id: str, body: RateRequest, user: dict = Depends(get_current_user)):
    c = await db.public_help_contributions.find_one({"contribution_id": contribution_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Contribution not found")
    post = await db.public_help_posts.find_one({"post_id": c["post_id"]}, {"_id": 0})
    if not post or post["owner_id"] != user["user_id"]:
        raise HTTPException(403, "Only the request owner can rate contributions")
    return await _save_rating(user, "contribution", contribution_id, c["contributor_id"], body.stars, body.comment)


@router.get("/rate/marketplace/{listing_id}/mine")
async def my_listing_rating(listing_id: str, user: dict = Depends(get_current_user)):
    r = await db.ratings.find_one({"rater_id": user["user_id"], "target_type": "listing", "target_id": listing_id}, {"_id": 0})
    return r or {}


# ---------------------------------------------------------------------------
# leaderboard + me + public profile
# ---------------------------------------------------------------------------
@router.get("/leaderboard")
async def leaderboard(limit: int = Query(50, le=200), user: dict = Depends(get_current_user)):
    cur = db.referral_profiles.find({"karma_balance": {"$gt": 0}}, {"_id": 0}).sort("karma_balance", -1).limit(limit)
    rows = await cur.to_list(limit)
    names = await _names_for([r["user_id"] for r in rows])
    items = []
    for i, r in enumerate(rows):
        items.append({
            "rank": i + 1,
            "user_id": r["user_id"],
            "name": names.get(r["user_id"], "Member"),
            "karma_balance": int(r.get("karma_balance", 0) or 0),
            "fame_rating_avg": r.get("fame_rating_avg"),
            "fame_rating_count": r.get("fame_rating_count", 0),
            "is_me": r["user_id"] == user["user_id"],
        })
    return {"items": items, "count": len(items)}


@router.get("/me")
async def my_karma(user: dict = Depends(get_current_user)):
    bal = await karma_engine.get_balance(user["user_id"])
    rank = await karma_engine.get_rank(user["user_id"])
    prof = await db.referral_profiles.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    ledger = await db.karma_ledger.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    # breakdown by event
    breakdown: Dict[str, int] = {}
    for e in ledger:
        breakdown[e["event"]] = breakdown.get(e["event"], 0) + e["points"]
    return {
        "karma_balance": bal,
        "rank": rank,
        "fame_rating_avg": prof.get("fame_rating_avg"),
        "fame_rating_count": prof.get("fame_rating_count", 0),
        "recent": ledger[:20],
        "breakdown": breakdown,
    }


@router.get("/profile/{user_id}")
async def public_profile(user_id: str, user: dict = Depends(get_current_user)):
    prof = await db.referral_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
    names = await _names_for([user_id])
    rank = await karma_engine.get_rank(user_id)
    # recent reviews about this provider
    reviews = await db.ratings.find({"provider_id": user_id, "comment": {"$ne": ""}}, {"_id": 0, "rater_name": 1, "stars": 1, "comment": 1, "created_at": 1}).sort("created_at", -1).to_list(20)
    return {
        "user_id": user_id,
        "name": names.get(user_id, "Member"),
        "karma_balance": int(prof.get("karma_balance", 0) or 0),
        "rank": rank,
        "fame_rating_avg": prof.get("fame_rating_avg"),
        "fame_rating_count": prof.get("fame_rating_count", 0),
        "reviews": reviews,
    }


# ---------------------------------------------------------------------------
# admin karma config
# ---------------------------------------------------------------------------
@admin_router.get("/config")
async def admin_get_karma(admin: dict = Depends(require_admin)):
    return await karma_engine.get_karma_config()


@admin_router.put("/config")
async def admin_update_karma(payload: Dict[str, Any], admin: dict = Depends(require_admin)):
    await karma_engine.get_karma_config()
    updates: Dict[str, Any] = {}
    if "enabled" in payload:
        updates["enabled"] = bool(payload["enabled"])
    if "points" in payload and isinstance(payload["points"], dict):
        clean = {k: int(v) for k, v in payload["points"].items() if isinstance(v, (int, float))}
        updates["points"] = clean
    if updates:
        await db.karma_config.update_one({"_id": "singleton"}, {"$set": updates})
    return await karma_engine.get_karma_config()
