"""
ACM Engine — Access Control Matrix core logic.
Evaluates (user_type, subscription_plan, feature_id) → {allowed, quota, usage, access_level}

Design:
  - Two-axis check: user_type × subscription_plan
  - Quota tracking per (user_id, feature_id, period)
  - Caches the matrix in memory (refreshed on admin update)
  - Trial expiry auto-downgrades to free
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from core.database import db

logger = logging.getLogger(__name__)

# In-memory cache of the ACM matrix (refreshed on seed/update)
_acm_cache: dict = {}  # feature_id → {module_id, feature_name, release_stage, quota_unit, quota_resets, access: {...}}


# ============================================================
# CACHE MANAGEMENT
# ============================================================

async def refresh_acm_cache():
    """Reload the ACM matrix from MongoDB into memory."""
    global _acm_cache
    modules = await db.acm_modules.find({}, {"_id": 0}).to_list(50)
    new_cache = {}
    for mod in modules:
        for feat in mod.get("features", []):
            new_cache[feat["feature_id"]] = {
                "module_id": mod["module_id"],
                "module_name": mod["module_name"],
                "feature_name": feat["feature_name"],
                "release_stage": feat.get("release_stage", "ga_free"),
                "quota_unit": feat.get("quota_unit", "toggle"),
                "quota_resets": feat.get("quota_resets", "none"),
                "access": feat.get("access", {}),
            }
    _acm_cache = new_cache
    logger.info(f"ACM cache refreshed: {len(new_cache)} features loaded")
    return len(new_cache)


async def seed_acm_defaults(force: bool = False):
    """Seed the ACM matrix from acm_seed_data.py into MongoDB.

    Version-aware: if `ACM_SEED_VERSION` in acm_seed_data.py has bumped since
    last seed, we auto-reseed (even without force=True). This lets feature
    additions (new modules / features) roll out on boot without an admin call.
    """
    from data.acm_seed_data import (
        ACM_MODULES, USER_TYPES, SUBSCRIPTION_PLANS, RELEASE_STAGES, ACM_SEED_VERSION,
    )

    existing = await db.acm_modules.count_documents({})
    stored_meta = await db.acm_meta.find_one({"key": "seed_version"}, {"_id": 0})
    stored_version = (stored_meta or {}).get("version")

    version_changed = stored_version != ACM_SEED_VERSION

    if existing > 0 and not force and not version_changed:
        await refresh_acm_cache()
        return {
            "message": "ACM already seeded (up to date)",
            "modules": existing,
            "features": len(_acm_cache),
            "seed_version": ACM_SEED_VERSION,
        }

    if version_changed and existing > 0 and not force:
        logger.info(f"ACM seed version changed ({stored_version} → {ACM_SEED_VERSION}); auto-reseeding")

    # Clear on explicit force OR on version bump (safer: remove stale modules/features)
    if force or version_changed:
        await db.acm_modules.delete_many({})
        await db.acm_user_types.delete_many({})
        await db.acm_subscription_plans.delete_many({})

    # Seed user types
    for ut in USER_TYPES:
        await db.acm_user_types.update_one({"id": ut["id"]}, {"$set": ut}, upsert=True)

    # Seed subscription plans
    for sp in SUBSCRIPTION_PLANS:
        await db.acm_subscription_plans.update_one({"id": sp["id"]}, {"$set": sp}, upsert=True)

    # Seed modules with features
    for mod in ACM_MODULES:
        await db.acm_modules.update_one(
            {"module_id": mod["module_id"]},
            {"$set": mod},
            upsert=True,
        )

    # Store release stages
    await db.acm_meta.update_one(
        {"key": "release_stages"},
        {"$set": {"key": "release_stages", "stages": RELEASE_STAGES}},
        upsert=True,
    )

    # Persist the seed version
    await db.acm_meta.update_one(
        {"key": "seed_version"},
        {"$set": {
            "key": "seed_version",
            "version": ACM_SEED_VERSION,
            "seeded_at": datetime.now(timezone.utc),
            "force": force,
            "version_changed": version_changed,
        }},
        upsert=True,
    )

    await refresh_acm_cache()
    return {
        "message": "ACM seeded successfully",
        "modules": len(ACM_MODULES),
        "features": len(_acm_cache),
        "seed_version": ACM_SEED_VERSION,
        "was_version_bump": version_changed,
    }


async def ensure_acm_seeded_on_boot():
    """Idempotent boot-time ACM check — re-seeds only if data missing or version bumped."""
    try:
        result = await seed_acm_defaults(force=False)
        logger.info(
            f"ACM boot check: {result['message']} "
            f"(modules={result.get('modules')}, features={result.get('features')}, "
            f"version={result.get('seed_version')})"
        )
    except Exception as e:
        logger.error(f"ACM boot seed failed: {e}")


# ============================================================
# ACCESS CHECK
# ============================================================

def _resolve_access_key(user_type: str, subscription_plan: str) -> str:
    """Build the access key for lookup in the ACM matrix."""
    if user_type == "paid":
        return f"paid_{subscription_plan}" if subscription_plan else "paid_starter"
    return user_type


def get_user_acm_profile(user: dict) -> dict:
    """Extract ACM-relevant fields from a user document."""
    user_type = user.get("user_type", "free")
    subscription_plan = user.get("subscription_plan", "none")

    # Auto-downgrade trial users if expired
    if user_type == "trial":
        trial_start = user.get("trial_start_date")
        trial_days = user.get("trial_duration_days", 14)
        if trial_start:
            if isinstance(trial_start, str):
                trial_start = datetime.fromisoformat(trial_start)
            if trial_start.tzinfo is None:
                trial_start = trial_start.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - trial_start).days
            if elapsed > trial_days:
                user_type = "free"  # Auto-downgrade (DB update happens async)

    return {
        "user_type": user_type,
        "subscription_plan": subscription_plan,
        "access_key": _resolve_access_key(user_type, subscription_plan),
    }


async def check_feature_access(
    user: dict, feature_id: str, check_quota: bool = True
) -> dict:
    """
    Check if a user can access a specific feature.

    Returns:
        {
            "allowed": bool,           # Can the user use this feature?
            "access_level": str,       # "full", "read", "locked", "hidden"
            "quota_limit": int,        # -1 = unlimited, 0 = none
            "quota_used": int,         # Current usage in the period
            "quota_remaining": int,    # -1 = unlimited
            "quota_unit": str,         # e.g., "decisions/month", "toggle"
            "upgrade_message": str,    # Shown when locked
        }
    """
    # Ensure cache is loaded
    if not _acm_cache:
        await refresh_acm_cache()

    feature = _acm_cache.get(feature_id)
    if not feature:
        # Feature not in ACM — default to full access (backward compat)
        return {
            "allowed": True, "access_level": "full",
            "quota_limit": -1, "quota_used": 0, "quota_remaining": -1,
            "quota_unit": "toggle", "upgrade_message": "",
        }

    profile = get_user_acm_profile(user)
    access_key = profile["access_key"]
    access_rule = feature["access"].get(access_key, {"level": "hidden", "quota": 0})

    level = access_rule.get("level", "hidden")
    quota_limit = access_rule.get("quota", 0)
    quota_unit = feature["quota_unit"]

    # Hidden = not accessible at all
    if level == "hidden":
        return {
            "allowed": False, "access_level": "hidden",
            "quota_limit": 0, "quota_used": 0, "quota_remaining": 0,
            "quota_unit": quota_unit, "upgrade_message": "",
        }

    # Locked = visible but not usable
    if level == "locked":
        return {
            "allowed": False, "access_level": "locked",
            "quota_limit": 0, "quota_used": 0, "quota_remaining": 0,
            "quota_unit": quota_unit,
            "upgrade_message": f"Upgrade your plan to access {feature['feature_name']}",
        }

    # Read = view only
    if level == "read":
        return {
            "allowed": True, "access_level": "read",
            "quota_limit": -1, "quota_used": 0, "quota_remaining": -1,
            "quota_unit": quota_unit, "upgrade_message": "",
        }

    # Full access — check quota
    if quota_limit == -1 or quota_unit == "toggle":
        return {
            "allowed": True, "access_level": "full",
            "quota_limit": -1, "quota_used": 0, "quota_remaining": -1,
            "quota_unit": quota_unit, "upgrade_message": "",
        }

    # Quota-based access — check usage
    quota_used = 0
    if check_quota:
        quota_used = await get_usage_count(user["user_id"], feature_id, feature["quota_resets"])

    quota_remaining = max(0, quota_limit - quota_used)
    allowed = quota_used < quota_limit

    return {
        "allowed": allowed,
        "access_level": "full" if allowed else "quota_exceeded",
        "quota_limit": quota_limit,
        "quota_used": quota_used,
        "quota_remaining": quota_remaining,
        "quota_unit": quota_unit,
        "upgrade_message": f"You've used {quota_used}/{quota_limit} {quota_unit}. Upgrade for more." if not allowed else "",
    }


async def check_and_consume(user: dict, feature_id: str) -> dict:
    """Check access AND increment usage if allowed. Use this before creating resources."""
    result = await check_feature_access(user, feature_id, check_quota=True)
    if result["allowed"] and result["access_level"] == "full" and result["quota_limit"] != -1:
        # Increment usage
        feature = _acm_cache.get(feature_id, {})
        await increment_usage(user["user_id"], feature_id, feature.get("quota_resets", "monthly"))
        result["quota_used"] += 1
        result["quota_remaining"] = max(0, result["quota_remaining"] - 1)
    return result


# ============================================================
# USAGE TRACKING
# ============================================================

def _get_usage_period(reset_type: str) -> str:
    """Get the current period string based on reset type."""
    now = datetime.now(timezone.utc)
    if reset_type == "monthly":
        return now.strftime("%Y-%m")
    elif reset_type == "weekly":
        return now.strftime("%Y-W%W")
    elif reset_type == "daily":
        return now.strftime("%Y-%m-%d")
    elif reset_type == "yearly":
        return now.strftime("%Y")
    else:
        return "lifetime"


async def get_usage_count(user_id: str, feature_id: str, reset_type: str = "monthly") -> int:
    """Get current usage count for a user+feature in the current period."""
    period = _get_usage_period(reset_type)

    if reset_type == "none":
        # For non-resetting quotas (active_tasks, active_goals, etc.), count actual resources
        return await _count_active_resources(user_id, feature_id)

    doc = await db.acm_usage.find_one({
        "user_id": user_id,
        "feature_id": feature_id,
        "period": period,
    })
    return doc["count"] if doc else 0


async def increment_usage(user_id: str, feature_id: str, reset_type: str = "monthly"):
    """Increment usage for a user+feature in the current period."""
    period = _get_usage_period(reset_type)
    await db.acm_usage.update_one(
        {"user_id": user_id, "feature_id": feature_id, "period": period},
        {
            "$inc": {"count": 1},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()},
        },
        upsert=True,
    )


async def _count_active_resources(user_id: str, feature_id: str) -> int:
    """Count active resources for non-resetting quotas (tasks, goals, routines, contacts)."""
    resource_map = {
        "ctt_tasks": ("ctt_tasks", {"created_by": user_id, "status": {"$ne": "completed"}}),
        "gem_goals": ("gem_goals", {"created_by": user_id, "status": {"$ne": "completed"}}),
        "lifestyle_routines": ("lifestyle_routines", {"user_id": user_id, "active": True}),
        "contacts": ("contacts", {"owner_user_id": user_id}),
        "deo_api_keys": ("deo_api_keys", {"user_id": user_id, "status": "active"}),
    }
    if feature_id in resource_map:
        coll, query = resource_map[feature_id]
        return await db[coll].count_documents(query)
    return 0


# ============================================================
# BULK ACCESS CHECK (for UI rendering)
# ============================================================

async def get_all_feature_access(user: dict) -> dict:
    """
    Get access levels for ALL features at once.
    Used by the frontend to render the entire UI conditionally.
    Returns: { feature_id: {access_level, quota_limit, quota_used, quota_remaining, quota_unit} }
    """
    if not _acm_cache:
        await refresh_acm_cache()

    profile = get_user_acm_profile(user)
    access_key = profile["access_key"]
    result = {}

    for feature_id, feature in _acm_cache.items():
        access_rule = feature["access"].get(access_key, {"level": "hidden", "quota": 0})
        level = access_rule.get("level", "hidden")
        quota_limit = access_rule.get("quota", 0)
        quota_unit = feature["quota_unit"]

        # For quota features, get usage
        quota_used = 0
        if level == "full" and quota_limit > 0 and quota_unit != "toggle":
            quota_used = await get_usage_count(
                user["user_id"], feature_id, feature.get("quota_resets", "monthly")
            )

        quota_remaining = -1 if quota_limit == -1 else max(0, quota_limit - quota_used)

        result[feature_id] = {
            "access_level": level,
            "quota_limit": quota_limit,
            "quota_used": quota_used,
            "quota_remaining": quota_remaining,
            "quota_unit": quota_unit,
        }

    return result
