"""
ACM Routes — WOWO Access Control Matrix API
Endpoints for seeding, querying, and managing the ACM.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user, get_user_role, ADMIN_ROLES
from core.acm_engine import (
    seed_acm_defaults, refresh_acm_cache,
    check_feature_access, check_and_consume,
    get_all_feature_access, get_user_acm_profile,
    resolve_user_acm_profile,
    _acm_cache,
)

router = APIRouter(prefix="/acm", tags=["ACM — Access Control Matrix"])


# ============================================================
# SEED & ADMIN
# ============================================================

@router.post("/seed")
async def seed_acm(force: bool = False, user: dict = Depends(get_current_user)):
    """Seed the ACM matrix from defaults. Admin only."""
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    result = await seed_acm_defaults(force=force)
    return result


@router.post("/refresh-cache")
async def api_refresh_cache(user: dict = Depends(get_current_user)):
    """Force-refresh the in-memory ACM cache. Admin only."""
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    count = await refresh_acm_cache()
    return {"message": "Cache refreshed", "features_loaded": count}


# ============================================================
# FULL MATRIX VIEW (Admin)
# ============================================================

@router.get("/matrix")
async def get_full_matrix(user: dict = Depends(get_current_user)):
    """Get the complete ACM matrix (all modules, features, access rules). Admin only."""
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")

    modules = await db.acm_modules.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    user_types = await db.acm_user_types.find({}, {"_id": 0}).sort("order", 1).to_list(20)
    plans = await db.acm_subscription_plans.find({}, {"_id": 0}).sort("order", 1).to_list(20)
    meta = await db.acm_meta.find_one({"key": "release_stages"}, {"_id": 0})
    release_stages = meta.get("stages", []) if meta else []

    return {
        "modules": modules,
        "user_types": user_types,
        "subscription_plans": plans,
        "release_stages": release_stages,
        "total_modules": len(modules),
        "total_features": sum(len(m.get("features", [])) for m in modules),
    }


# ============================================================
# UPDATE FEATURE ACCESS (Admin)
# ============================================================

@router.put("/feature/{feature_id}")
async def update_feature_access(feature_id: str, request: Request, user: dict = Depends(get_current_user)):
    """
    Update access rules for a specific feature. Admin only.
    Body: {
        "release_stage": "beta",
        "access": {
            "unit_tester": {"level": "full", "quota": -1},
            "free": {"level": "locked", "quota": 0},
            "paid_pro": {"level": "full", "quota": 20},
            ...
        }
    }
    """
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")

    body = await request.json()
    new_access = body.get("access", {})
    new_stage = body.get("release_stage")

    # Find the module containing this feature
    module = await db.acm_modules.find_one({"features.feature_id": feature_id})
    if not module:
        raise HTTPException(404, f"Feature '{feature_id}' not found in ACM")

    # Update the specific feature within the module
    update_ops = {}
    for i, feat in enumerate(module.get("features", [])):
        if feat["feature_id"] == feature_id:
            if new_access:
                update_ops[f"features.{i}.access"] = new_access
            if new_stage:
                update_ops[f"features.{i}.release_stage"] = new_stage
            break

    if not update_ops:
        raise HTTPException(400, "No valid updates provided")

    update_ops["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_ops["updated_by"] = user["user_id"]

    await db.acm_modules.update_one({"module_id": module["module_id"]}, {"$set": update_ops})

    # ─── SECTION ↔ TILE CASCADE (dashboard_tiles module only) ─────────────
    # Three rules, applied in this order:
    #   R1. If a SECTION row was edited → for each audience set to Hidden,
    #       push the same level to every child tile that does NOT carry an
    #       override flag for that audience (i.e. only "untouched" tiles).
    #       For Full/Read/Locked, do the same (so enabling a section turns
    #       its un-overridden tiles back on).
    #   R2. When a single TILE row is edited → record its
    #       `tile_overrides[audience] = true` so future section cascades
    #       skip those audiences. Also clear the override when a user
    #       resets a tile back to match the parent.
    #   R3. If a TILE is set to Full/Read while its parent SECTION is
    #       Hidden for the SAME audience → auto-flip the section to Full
    #       for that audience (because at least one child is visible now).
    cascade_log: list[str] = []
    if module["module_id"] == "dashboard_tiles" and new_access:
        edited_feat = next((f for f in module["features"] if f["feature_id"] == feature_id), None)
        is_section = bool(edited_feat and edited_feat.get("is_section"))
        parent_id = edited_feat.get("parent_feature_id") if edited_feat else None
        mod_now = await db.acm_modules.find_one({"module_id": "dashboard_tiles"})

        if is_section:
            # R1 — cascade to children that aren't overridden for that audience
            for j, feat in enumerate(mod_now["features"]):
                if feat.get("parent_feature_id") != feature_id:
                    continue
                overrides = feat.get("tile_overrides", {}) or {}
                child_access = dict(feat.get("access") or {})
                changed = False
                for aud, rule in new_access.items():
                    if overrides.get(aud):
                        continue  # respect per-tile override
                    child_access[aud] = rule
                    changed = True
                if changed:
                    await db.acm_modules.update_one(
                        {"module_id": "dashboard_tiles"},
                        {"$set": {f"features.{j}.access": child_access,
                                  f"features.{j}.updated_at": datetime.now(timezone.utc).isoformat()}},
                    )
                    cascade_log.append(f"cascaded → {feat['feature_id']}")

        elif parent_id:
            # R2 — mark every audience touched by this tile edit as overridden
            tile_idx = next(i for i, f in enumerate(mod_now["features"]) if f["feature_id"] == feature_id)
            current_overrides = mod_now["features"][tile_idx].get("tile_overrides", {}) or {}
            for aud in new_access.keys():
                current_overrides[aud] = True
            await db.acm_modules.update_one(
                {"module_id": "dashboard_tiles"},
                {"$set": {f"features.{tile_idx}.tile_overrides": current_overrides}},
            )

            # R3 — auto-unhide parent section if this tile is Full/Read for a
            # currently-hidden audience.
            parent_idx = next((i for i, f in enumerate(mod_now["features"]) if f["feature_id"] == parent_id), -1)
            if parent_idx >= 0:
                parent_access = dict(mod_now["features"][parent_idx].get("access") or {})
                changed_parent = False
                for aud, rule in new_access.items():
                    if rule.get("level") in ("full", "read") \
                       and (parent_access.get(aud) or {}).get("level") == "hidden":
                        parent_access[aud] = {"level": "full", "quota": -1}
                        changed_parent = True
                if changed_parent:
                    await db.acm_modules.update_one(
                        {"module_id": "dashboard_tiles"},
                        {"$set": {f"features.{parent_idx}.access": parent_access}},
                    )
                    cascade_log.append(f"auto-unhid parent → {parent_id}")

    await refresh_acm_cache()

    resp = {"message": f"Feature '{feature_id}' updated", "updates": list(update_ops.keys())}
    if cascade_log:
        resp["cascade"] = cascade_log
    return resp


# ============================================================
# USER-FACING: My Access
# ============================================================

@router.get("/my-access")
async def get_my_access(user: dict = Depends(get_current_user)):
    """
    Get the current user's access levels for ALL features.
    Uses the 5-axis resolver (core.user_type_resolver) to compute the
    effective access key, persists it on the user doc, then evaluates
    every feature in one shot.
    """
    profile = await resolve_user_acm_profile(user)
    # Re-fetch user with the freshly stamped effective_access_key so the
    # downstream `get_all_feature_access` reads the cached key.
    fresh = await db.users.find_one({"user_id": user["user_id"]}) or user
    features = await get_all_feature_access(fresh)

    return {
        "user_id": user["user_id"],
        "user_type": profile["user_type"],
        "subscription_plan": profile.get("subscription_plan", "none"),
        "access_key": profile["access_key"],
        "effective_access_key": profile["access_key"],
        "effective_reason": profile.get("reason"),
        "features": features,
    }


@router.get("/check/{feature_id}")
async def check_single_feature(feature_id: str, user: dict = Depends(get_current_user)):
    """Check access for a single feature. Returns detailed access info."""
    result = await check_feature_access(user, feature_id, check_quota=True)
    return {"feature_id": feature_id, **result}


# ============================================================
# USER TYPE & PLAN MANAGEMENT (Admin)
# ============================================================

@router.put("/user/{user_id}/type")
async def set_user_type(user_id: str, request: Request, user: dict = Depends(get_current_user)):
    """
    Set a user's type and/or subscription plan. Admin only.
    Body: {
        "user_type": "beta",
        "subscription_plan": "pro",
        "trial_duration_days": 14  (only for trial type)
    }
    """
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")

    body = await request.json()
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(404, "User not found")

    update = {}
    valid_types = [
        "free", "trial", "paid",
        "starter_trial", "pro_trial", "premium_trial",
        "on_demand_retail_buyer", "on_demand_bulk_buyer",
        "unit_tester", "integration_tester", "alpha", "beta",
    ]
    valid_plans = ["none", "starter", "pro", "premium", "enterprise", "api"]

    if "user_type" in body:
        if body["user_type"] not in valid_types:
            raise HTTPException(400, f"Invalid user_type. Must be one of: {valid_types}")
        update["user_type"] = body["user_type"]

        # Set trial dates if switching to trial
        if body["user_type"] == "trial":
            update["trial_start_date"] = datetime.now(timezone.utc).isoformat()
            update["trial_duration_days"] = body.get("trial_duration_days", 14)

    if "subscription_plan" in body:
        if body["subscription_plan"] not in valid_plans:
            raise HTTPException(400, f"Invalid subscription_plan. Must be one of: {valid_plans}")
        update["subscription_plan"] = body["subscription_plan"]

        if body["subscription_plan"] != "none":
            update["subscription_start_date"] = datetime.now(timezone.utc).isoformat()

    if not update:
        raise HTTPException(400, "No valid fields to update")

    update["acm_updated_at"] = datetime.now(timezone.utc).isoformat()
    update["acm_updated_by"] = user["user_id"]

    await db.users.update_one({"user_id": user_id}, {"$set": update})

    return {
        "message": f"User {user_id} updated",
        "user_type": update.get("user_type", target.get("user_type", "free")),
        "subscription_plan": update.get("subscription_plan", target.get("subscription_plan", "none")),
    }


@router.get("/users")
async def list_users_by_type(
    user_type: Optional[str] = None,
    subscription_plan: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """List users filtered by type or plan. Admin only."""
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")

    query: dict = {}
    if user_type:
        query["user_type"] = user_type
    if subscription_plan:
        query["subscription_plan"] = subscription_plan

    total = await db.users.count_documents(query)
    users = await db.users.find(
        query,
        {"_id": 0, "password_hash": 0, "otp_code": 0},
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "users": users}


# ============================================================
# USAGE STATS (Admin)
# ============================================================

@router.get("/usage-stats")
async def get_usage_stats(
    feature_id: Optional[str] = None,
    period: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Get aggregated usage statistics. Admin only."""
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")

    query: dict = {}
    if feature_id:
        query["feature_id"] = feature_id
    if period:
        query["period"] = period

    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": {"feature_id": "$feature_id", "period": "$period"},
            "total_usage": {"$sum": "$count"},
            "unique_users": {"$addToSet": "$user_id"},
        }},
        {"$project": {
            "feature_id": "$_id.feature_id",
            "period": "$_id.period",
            "total_usage": 1,
            "unique_users": {"$size": "$unique_users"},
        }},
        {"$sort": {"total_usage": -1}},
        {"$limit": 100},
    ]

    stats = await db.acm_usage.aggregate(pipeline).to_list(100)
    return {"stats": stats}
