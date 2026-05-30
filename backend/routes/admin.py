"""Admin-only endpoints: Feature Flags (WOWO), Call Config."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user, get_user_role, ADMIN_ROLES

router = APIRouter()


# ========================
# WOWO FEATURE FLAGS
# ========================

@router.get("/feature-flags")
async def get_feature_flags(user: dict = Depends(get_current_user)):
    """Get all feature flags (WOWO settings).

    Both `solution_finder` and `solution_matrix` default to TRUE — they were
    promoted to first-class dashboard modules in the June 2026 overhaul.
    Admins can still toggle them off via the admin payment/settings UI.
    """
    settings = await db.app_settings.find_one({"key": "feature_flags"})
    if not settings:
        return {"solution_finder": True, "solution_matrix": True}
    flags = settings.get("flags", {})
    return {
        "solution_finder": flags.get("solution_finder", True),
        "solution_matrix": flags.get("solution_matrix", True),
    }


@router.get("/feature-flags/public")
async def get_public_feature_flags():
    """Get feature flags without auth (for conditional UI rendering)."""
    settings = await db.app_settings.find_one({"key": "feature_flags"})
    if not settings:
        return {"solution_finder": True, "solution_matrix": True}
    flags = settings.get("flags", {})
    return {
        "solution_finder": flags.get("solution_finder", True),
        "solution_matrix": flags.get("solution_matrix", True),
    }


@router.put("/admin/feature-flags")
async def update_feature_flags(request: Request, user: dict = Depends(get_current_user)):
    """Update feature flags (admin only) - WOWO toggle"""
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    flags = {}
    if "solution_finder" in body:
        flags["solution_finder"] = bool(body["solution_finder"])
    if "solution_matrix" in body:
        flags["solution_matrix"] = bool(body["solution_matrix"])

    await db.app_settings.update_one(
        {"key": "feature_flags"},
        {"$set": {
            "flags": flags,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": user["user_id"],
        }},
        upsert=True,
    )
    return {"message": "Feature flags updated", "flags": flags}


# ========================
# ADMIN CALL CONFIG
# ========================

@router.get("/admin/call-config")
async def get_admin_call_config():
    """Get admin-configurable call settings"""
    config = await db.app_settings.find_one({"key": "call_config"})
    if not config:
        return {"default_duration": 30, "min_duration": 5, "max_duration": 120}
    return {
        "default_duration": config.get("default_duration", 30),
        "min_duration": config.get("min_duration", 5),
        "max_duration": config.get("max_duration", 120),
    }


@router.put("/admin/call-config")
async def update_admin_call_config(request: Request, user: dict = Depends(get_current_user)):
    """Update call configuration (admin only)"""
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    body = await request.json()
    update = {}
    if "default_duration" in body:
        update["default_duration"] = max(5, min(120, int(body["default_duration"])))
    if "min_duration" in body:
        update["min_duration"] = max(1, min(60, int(body["min_duration"])))
    if "max_duration" in body:
        update["max_duration"] = max(30, min(480, int(body["max_duration"])))

    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    update["updated_by"] = user["user_id"]

    await db.app_settings.update_one(
        {"key": "call_config"}, {"$set": update}, upsert=True
    )
    return {"message": "Call config updated", **update}



# ========================
# ADMIN DATA SEEDING (production starter content for every admin section)
# ========================

@router.post("/admin/seed/run")
async def trigger_admin_data_seed(user: dict = Depends(get_current_user)):
    """Idempotently seed production-ready starter content across all admin
    sections (Experts, Templates, Customer Segments, Pending Approvals,
    Social Learning, Incidents, Audit Trail, ReviewNet Factors, Decision Modes).

    Safe to re-run any number of times — every record is upserted by stable id.
    Admin-only.
    """
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    from core.admin_data_seed import seed_admin_data
    return await seed_admin_data(force=True)


@router.get("/admin/seed/status")
async def admin_seed_status(user: dict = Depends(get_current_user)):
    """Return the last seed run marker (version, timestamp, per-collection counts)."""
    role = get_user_role(user)
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")

    marker = await db.app_config.find_one({"key": "admin_data_seed"}, {"_id": 0})
    if not marker:
        return {"seeded": False}
    return {"seeded": True, **marker.get("value", {})}
