"""
DPDP / GDPR data-subject rights endpoints.

Allows authenticated users to:
  - export ALL their personal data (machine-readable JSON, immediate download)
  - request account deletion (7-day soft-delete grace, then full purge)
  - cancel a pending deletion within the grace window

Admin-only:
  - audit log query by user_id
  - finalize purge after grace window has passed (cron-style endpoint)

Mounts at /api/dpdp/*. All sensitive ops are written into the audit_log.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from core.database import db
from core.auth import get_current_user, require_admin
from core.hardening import write_audit, redact_pii

router = APIRouter(prefix="/dpdp", tags=["DPDP / GDPR"])

# Collections that contain user-identifiable data. Add new collections here as
# new modules are added so the export/delete stays comprehensive.
USER_DATA_COLLECTIONS: List[str] = [
    "users", "user_sessions", "user_subscriptions", "user_wallets",
    "decisions", "factors", "options", "option_scores",
    "clds", "cld_simulations",
    "solution_finders", "solution_matrices",
    "goal_setter_entries", "goal_manifestations",
    "conflict_breakers", "unconditional_happiness",
    "pna_entries", "lifestyle_designs",
    "swot_analyses", "pros_cons_lists",
    "tepfi_matrices", "aala_entries",
    "consciousness_diary_entries",
    "ctt_tasks", "ctt_sessions", "ctt_breakdowns",
    "gem_flights", "gem_goals",
    "meditation_sessions", "meditation_settings",
    "emotional_gatekeeper_entries",
    "lifestyle_routines", "lifestyle_evals",
    "journal_entries", "notifications",
    "contacts", "collaboration_sessions", "incidents",
    "face_auth_registrations", "presence_logs",
    "social_learning_endorsements", "social_learning_credits",
    "google_calendar_tokens", "deo_api_keys", "google_calendar_events",
    "pp_consents", "pp_demographic_profiles", "pp_tool_sessions",
    "pp_feedback_items", "pp_orgs", "pp_org_memberships",
    "solutions_store_solutions",
    "video_calls", "video_call_participants",
    "meditation_settings",
]

DELETE_GRACE_DAYS = 7


# ---------------------------------------------------------------------------
# Export (Right to data portability)
# ---------------------------------------------------------------------------
@router.get("/export")
async def export_my_data(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Export every record tied to the user as JSON. Synchronous (typical
    user has < a few MB of data). For very large accounts, switch to
    background job + S3 signed URL.
    """
    uid = user["user_id"]
    payload: Dict[str, Any] = {
        "user_id": uid,
        "email": user.get("email"),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "collections": {},
    }
    for coll_name in USER_DATA_COLLECTIONS:
        try:
            cursor = db[coll_name].find(
                {"user_id": uid},
                {"_id": 0},
            ).limit(10000)
            rows = await cursor.to_list(10000)
            if rows:
                payload["collections"][coll_name] = rows
        except Exception:
            # collection might not exist yet — skip silently
            continue
    await write_audit(
        db, action="dpdp.export", actor_id=uid,
        actor_email=user.get("email"),
        request=request,
        metadata={"collections_exported": list(payload["collections"].keys())},
    )
    return payload


# ---------------------------------------------------------------------------
# Delete request + grace cancel
# ---------------------------------------------------------------------------
@router.post("/delete-request")
async def request_account_deletion(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Mark the user for deletion. After DELETE_GRACE_DAYS, the cron-style
    /dpdp/admin/purge-pending endpoint will permanently delete their data.
    """
    uid = user["user_id"]
    grace_until = datetime.now(timezone.utc) + timedelta(days=DELETE_GRACE_DAYS)
    await db.users.update_one(
        {"user_id": uid},
        {"$set": {
            "deletion_requested_at": datetime.now(timezone.utc),
            "deletion_grace_until": grace_until,
            "deletion_status": "pending",
        }},
    )
    await write_audit(
        db, action="dpdp.delete_request", actor_id=uid,
        actor_email=user.get("email"),
        request=request,
        metadata={"grace_until": grace_until.isoformat()},
    )
    return {
        "ok": True,
        "deletion_status": "pending",
        "grace_until": grace_until.isoformat(),
        "grace_days": DELETE_GRACE_DAYS,
        "how_to_cancel": "POST /api/dpdp/cancel-delete (must be within grace window)",
    }


@router.post("/cancel-delete")
async def cancel_deletion(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Cancel a pending deletion if still within the grace window."""
    uid = user["user_id"]
    fresh = await db.users.find_one({"user_id": uid}, {"_id": 0})
    if not fresh or fresh.get("deletion_status") != "pending":
        raise HTTPException(400, "No pending deletion request")
    grace_until = fresh.get("deletion_grace_until")
    if isinstance(grace_until, datetime) and grace_until.tzinfo is None:
        grace_until = grace_until.replace(tzinfo=timezone.utc)
    if grace_until and grace_until < datetime.now(timezone.utc):
        raise HTTPException(410, "Grace window expired — deletion already in flight")
    await db.users.update_one(
        {"user_id": uid},
        {"$unset": {"deletion_requested_at": 1, "deletion_grace_until": 1, "deletion_status": 1}},
    )
    await write_audit(
        db, action="dpdp.delete_cancel", actor_id=uid,
        actor_email=user.get("email"),
        request=request,
    )
    return {"ok": True, "deletion_status": "cancelled"}


@router.get("/status")
async def my_deletion_status(user: dict = Depends(get_current_user)):
    fresh = await db.users.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0, "deletion_status": 1, "deletion_grace_until": 1, "deletion_requested_at": 1},
    ) or {}
    return {
        "deletion_status": fresh.get("deletion_status", "none"),
        "deletion_requested_at": fresh.get("deletion_requested_at"),
        "deletion_grace_until": fresh.get("deletion_grace_until"),
    }


# ---------------------------------------------------------------------------
# Admin: purge pending deletions past grace window
# ---------------------------------------------------------------------------
@router.post("/admin/purge-pending")
async def admin_purge_pending(
    request: Request,
    user: dict = Depends(require_admin),
    limit: int = 50,
):
    """Hard-delete any user whose deletion grace window has elapsed.
    Designed to be hit by a cron / k8s CronJob hourly.
    """
    cutoff = datetime.now(timezone.utc)
    candidates = await db.users.find({
        "deletion_status": "pending",
        "deletion_grace_until": {"$lte": cutoff},
    }, {"_id": 0, "user_id": 1, "email": 1}).limit(min(max(limit, 1), 200)).to_list(200)

    purged: List[Dict[str, Any]] = []
    for u in candidates:
        uid = u.get("user_id")
        if not uid:
            continue
        deleted_counts: Dict[str, int] = {}
        for coll in USER_DATA_COLLECTIONS:
            try:
                res = await db[coll].delete_many({"user_id": uid})
                if res.deleted_count:
                    deleted_counts[coll] = res.deleted_count
            except Exception:
                continue
        # Tombstone the user record itself
        await db.users.update_one(
            {"user_id": uid},
            {"$set": {
                "email": f"deleted_{uid[:8]}@redacted",
                "name": "[deleted]",
                "phone": None,
                "avatar_b64": None,
                "deletion_status": "purged",
                "deletion_purged_at": datetime.now(timezone.utc),
            }},
        )
        purged.append({"user_id": uid, "deleted_counts": deleted_counts})
        await write_audit(
            db, action="dpdp.purge", actor_id=user["user_id"],
            target_type="user", target_id=uid,
            metadata={"deleted_counts": deleted_counts},
            request=request,
        )
        # Yield to event loop between users
        await asyncio.sleep(0)
    return {"ok": True, "purged_count": len(purged), "details": purged}


# ---------------------------------------------------------------------------
# Admin: read audit log
# ---------------------------------------------------------------------------
@router.get("/admin/audit-log")
async def admin_audit_log(
    user: dict = Depends(require_admin),
    actor_id: str = None,
    action: str = None,
    limit: int = 100,
    skip: int = 0,
):
    q: Dict[str, Any] = {}
    if actor_id: q["actor_id"] = actor_id
    if action: q["action"] = action
    items = await db.audit_log.find(q, {"_id": 0}).sort("ts", -1)\
        .skip(max(skip, 0)).limit(min(max(limit, 1), 500)).to_list(500)
    total = await db.audit_log.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "skip": skip}
