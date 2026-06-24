"""
ACM Engine — Access Control Matrix core logic.
Evaluates (user_type, subscription_plan, feature_id) → {allowed, quota, usage, access_level}

Design:
  - Unified 5-axis resolver (core.user_type_resolver) → effective_access_key
  - Legacy fallback chain keeps old seed maps compatible (paid_premium → paid_enterprise,
    starter_trial → trial, on_demand_retail_buyer → paid_starter, etc.)
  - Quota tracking per (user_id, feature_id, period)
  - Caches the matrix in memory (refreshed on admin update)
  - Trial expiry auto-downgrades via resolver
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from core.database import db

logger = logging.getLogger(__name__)

# Legacy access-key → list of fallback keys to try, in order, when the
# resolver-issued effective key is not present in a feature's access map.
# This keeps the existing ~1500 hand-crafted access entries valid while
# we roll out the new keys gradually.
LEGACY_ACCESS_KEY_FALLBACK = {
    "platform_admin":          ["paid_enterprise", "paid_pro"],
    "paid_premium":            ["paid_enterprise"],
    "starter_trial":           ["trial", "paid_starter", "free"],
    "pro_trial":               ["trial", "paid_pro", "paid_starter", "free"],
    "premium_trial":           ["trial", "paid_enterprise", "paid_pro", "free"],
    "on_demand_retail_buyer":  ["paid_starter", "free"],
    "on_demand_bulk_buyer":    ["paid_pro", "paid_starter", "free"],
}


def _lookup_access_rule(access_map: dict, access_key: str) -> dict:
    """Look up an access rule with legacy fallback chain.

    Returns {"level": str, "quota": int}. Never raises — defaults to
    {"level": "hidden", "quota": 0} if nothing matches.
    """
    if not isinstance(access_map, dict):
        return {"level": "hidden", "quota": 0}
    rule = access_map.get(access_key)
    if rule:
        return rule
    for fb in LEGACY_ACCESS_KEY_FALLBACK.get(access_key, []):
        rule = access_map.get(fb)
        if rule:
            return rule
    return {"level": "hidden", "quota": 0}

# In-memory cache of the ACM matrix (refreshed on seed/update)
_acm_cache: dict = {}  # feature_id → {module_id, feature_name, release_stage, quota_unit, quota_resets, access: {...}}
# Cross-worker cache invalidation. Each worker keeps an in-process copy of the
# matrix; a stamp stored in `acm_meta` is bumped on every WRITE. Readers check
# the stamp (throttled) and reload if another worker changed the matrix — this
# fixes stale tiles in multi-worker (gunicorn/uvicorn --workers N) deployments
# where a PUT only refreshed the cache on the single worker that served it.
_acm_cache_stamp: str = ""
_last_stamp_check: float = 0.0
_STAMP_CHECK_INTERVAL = 2.0  # seconds — bounds cross-worker staleness


async def _read_cache_stamp() -> str:
    doc = await db.acm_meta.find_one({"key": "acm_cache_stamp"}, {"_id": 0, "value": 1})
    return (doc or {}).get("value", "")


async def bump_acm_cache_stamp() -> str:
    """Mark the ACM matrix as changed so every worker reloads on next read."""
    import uuid as _uuid
    stamp = _uuid.uuid4().hex
    await db.acm_meta.update_one(
        {"key": "acm_cache_stamp"},
        {"$set": {"key": "acm_cache_stamp", "value": stamp}},
        upsert=True,
    )
    return stamp


async def ensure_fresh_cache():
    """Reload the in-process cache if empty or if another worker bumped the stamp.
    Throttled to at most once per _STAMP_CHECK_INTERVAL to avoid a DB hit on
    every single access check."""
    global _last_stamp_check
    import time as _time
    if not _acm_cache:
        await refresh_acm_cache()
        return
    now = _time.monotonic()
    if now - _last_stamp_check < _STAMP_CHECK_INTERVAL:
        return
    _last_stamp_check = now
    stamp = await _read_cache_stamp()
    if stamp and stamp != _acm_cache_stamp:
        await refresh_acm_cache()


# ============================================================
# CACHE MANAGEMENT
# ============================================================

async def refresh_acm_cache():
    """Reload the ACM matrix from MongoDB into memory."""
    global _acm_cache, _acm_cache_stamp
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
    # Record the stamp we just loaded so ensure_fresh_cache() won't needlessly reload.
    _acm_cache_stamp = await _read_cache_stamp()
    logger.info(f"ACM cache refreshed: {len(new_cache)} features loaded (stamp={_acm_cache_stamp[:8]})")
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
    # PRESERVE admin's custom per-feature `access` maps + `tile_overrides`
    # across version bumps — otherwise every seed bump silently destroys the
    # admin's WOWO customizations (the exact bug Sabba hit on 2026-06-16).
    preserved_access: dict[str, dict] = {}  # feature_id → preserved fields
    if force or version_changed:
        existing_mods = await db.acm_modules.find({}, {"features": 1}).to_list(None)
        for em in existing_mods:
            for f in em.get("features") or []:
                fid = f.get("feature_id")
                if not fid:
                    continue
                preserved_access[fid] = {
                    "access": f.get("access"),
                    "tile_overrides": f.get("tile_overrides"),
                }
        await db.acm_modules.delete_many({})
        await db.acm_user_types.delete_many({})
        await db.acm_subscription_plans.delete_many({})

    # Seed user types
    for ut in USER_TYPES:
        await db.acm_user_types.update_one({"id": ut["id"]}, {"$set": ut}, upsert=True)

    # Seed subscription plans
    for sp in SUBSCRIPTION_PLANS:
        await db.acm_subscription_plans.update_one({"id": sp["id"]}, {"$set": sp}, upsert=True)

    # Seed modules with features — merging preserved admin overrides
    for mod in ACM_MODULES:
        merged = dict(mod)
        if preserved_access:
            new_features = []
            for f in mod.get("features") or []:
                fid = f.get("feature_id")
                saved = preserved_access.get(fid) if fid else None
                if saved and saved.get("access"):
                    # admin had customized this feature → keep their access map
                    # but inherit any new metadata (parent_feature_id,
                    # is_section, section_order, quota_unit, etc.) from seed.
                    nf = dict(f)
                    nf["access"] = saved["access"]
                    if saved.get("tile_overrides"):
                        nf["tile_overrides"] = saved["tile_overrides"]
                    new_features.append(nf)
                else:
                    new_features.append(f)
            merged["features"] = new_features
        await db.acm_modules.update_one(
            {"module_id": mod["module_id"]},
            {"$set": merged},
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
    """Build the access key for lookup in the ACM matrix (legacy/sync)."""
    if user_type in ("super_admin", "admin", "co_admin"):
        return "platform_admin"
    if user_type == "paid":
        plan = subscription_plan or "starter"
        if plan == "enterprise":
            plan = "premium"
        return f"paid_{plan}"
    return user_type


def get_user_acm_profile(user: dict) -> dict:
    """Sync ACM profile extraction. For new code prefer
    ``resolve_user_acm_profile`` (async, calls the 5-axis resolver).
    """
    user_type = user.get("user_type", "free")
    subscription_plan = user.get("subscription_plan", "none")

    # If resolver has already stamped an effective key, trust it.
    eff = user.get("effective_access_key")
    if eff:
        return {
            "user_type": user_type,
            "subscription_plan": subscription_plan,
            "access_key": eff,
        }

    # Platform admin shortcut
    role = (user.get("role") or "").lower()
    if role in ("super_admin", "admin", "co_admin"):
        return {
            "user_type": "paid",
            "subscription_plan": "premium",
            "access_key": "platform_admin",
        }

    # Legacy trial auto-downgrade
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
                user_type = "free"

    return {
        "user_type": user_type,
        "subscription_plan": subscription_plan,
        "access_key": _resolve_access_key(user_type, subscription_plan),
    }


async def resolve_user_acm_profile(user: dict) -> dict:
    """Async-resolve via the 5-axis user_type_resolver and cache result on the user doc."""
    try:
        from core.user_type_resolver import resolve_user_type
        user_type, plan, effective, reason = await resolve_user_type(user)
        # Cache to user doc for fast subsequent reads
        uid = user.get("user_id")
        if uid:
            await db.users.update_one(
                {"user_id": uid},
                {"$set": {
                    "effective_access_key": effective,
                    "effective_user_type": user_type,
                    "effective_plan": plan,
                    "effective_reason": reason,
                    "effective_resolved_at": datetime.now(timezone.utc),
                }},
            )
        return {
            "user_type": user_type,
            "subscription_plan": plan,
            "access_key": effective,
            "reason": reason,
        }
    except Exception as e:
        logger.warning(f"resolver fallback (sync): {e}")
        return get_user_acm_profile(user)


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
    # Ensure cache is loaded AND fresh across workers (reload if another worker
    # changed the matrix — fixes stale single-feature checks in multi-worker).
    await ensure_fresh_cache()

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
    access_rule = _lookup_access_rule(feature["access"], access_key)

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
    await ensure_fresh_cache()

    profile = get_user_acm_profile(user)
    access_key = profile["access_key"]
    result = {}

    for feature_id, feature in _acm_cache.items():
        access_rule = _lookup_access_rule(feature["access"], access_key)
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
