"""
KYC Data Access Audit Trail — View Dezider
Logs every read/write to DigiLocker-sourced data with timestamps, user IDs, IP addresses.
Compliant with DPDPA 2023 and UIDAI Aadhaar Data Vault Guidelines.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from core.database import db
from routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit-trail", tags=["Audit Trail"])


# ========================
# AUDIT LOGGING UTILITY
# ========================

async def log_audit_event(
    action: str,
    entity_type: str,
    entity_id: str,
    user_id: str,
    details: str,
    ip_address: str = "",
    sensitive_data_accessed: bool = False,
    data_fields_accessed: list = None,
):
    """Core audit logging function. Call from any route to log data access."""
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": f"AUD-{uuid.uuid4().hex[:10]}",
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "user_id": user_id,
        "details": details,
        "ip_address": ip_address,
        "sensitive_data_accessed": sensitive_data_accessed,
        "data_fields_accessed": data_fields_accessed or [],
        "timestamp": now,
    }
    await db.audit_trail.insert_one(entry)
    if sensitive_data_accessed:
        logger.info(f"AUDIT [SENSITIVE]: {action} on {entity_type}/{entity_id} by {user_id} from {ip_address}")
    return entry


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def require_admin(user: dict):
    u = await db.users.find_one({"user_id": user["user_id"]})
    if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
        raise HTTPException(403, "Admin access required")
    return u


# ========================
# ENDPOINTS
# ========================

@router.get("")
async def get_audit_logs(
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    sensitive_only: bool = False,
    limit: int = 50,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Get audit trail logs. Admin only."""
    await require_admin(user)

    query = {}
    if entity_type:
        query["entity_type"] = entity_type
    if action:
        query["action"] = action
    if user_id:
        query["user_id"] = user_id
    if sensitive_only:
        query["sensitive_data_accessed"] = True

    total = await db.audit_trail.count_documents(query)
    logs = await db.audit_trail.find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    for entry in logs:
        entry.pop("_id", None)

    return {"total": total, "logs": logs, "limit": limit, "skip": skip}


@router.get("/kyc")
async def get_kyc_audit_logs(
    limit: int = 50,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Get KYC-specific audit trail. Shows all DigiLocker/Biometric/TOTP data access events."""
    await require_admin(user)

    query = {
        "$or": [
            {"entity_type": "kyc"},
            {"entity_type": "digilocker"},
            {"entity_type": "biometric"},
            {"entity_type": "totp"},
            {"action": {"$regex": "kyc|digilocker|biometric|totp", "$options": "i"}},
            {"sensitive_data_accessed": True},
        ]
    }

    total = await db.audit_trail.count_documents(query)
    logs = await db.audit_trail.find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    for entry in logs:
        entry.pop("_id", None)

    return {"total": total, "logs": logs, "limit": limit, "skip": skip}


@router.get("/stats")
async def get_audit_stats(user: dict = Depends(get_current_user)):
    """Get audit trail statistics — total events, sensitive accesses, breakdown by type."""
    await require_admin(user)

    total = await db.audit_trail.count_documents({})
    sensitive = await db.audit_trail.count_documents({"sensitive_data_accessed": True})
    kyc_related = await db.audit_trail.count_documents({
        "$or": [
            {"entity_type": {"$in": ["kyc", "digilocker", "biometric", "totp"]}},
            {"sensitive_data_accessed": True},
        ]
    })
    incidents_total = await db.audit_trail.count_documents({"entity_type": "incident"})

    # Breakdown by action
    pipeline = [
        {"$group": {"_id": "$action", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20},
    ]
    action_breakdown = await db.audit_trail.aggregate(pipeline).to_list(20)

    # Recent 24h count
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent_24h = await db.audit_trail.count_documents({"timestamp": {"$gte": cutoff}})

    return {
        "total_events": total,
        "sensitive_accesses": sensitive,
        "kyc_related": kyc_related,
        "incident_events": incidents_total,
        "last_24h": recent_24h,
        "action_breakdown": [{"action": a["_id"], "count": a["count"]} for a in action_breakdown],
    }


@router.delete("/purge")
async def purge_old_audit_logs(days: int = 365, user: dict = Depends(get_current_user)):
    """Purge audit logs older than specified days. Admin only. Minimum 90 days retention."""
    await require_admin(user)

    if days < 90:
        raise HTTPException(400, "Minimum retention period is 90 days per DPDPA compliance.")

    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = await db.audit_trail.delete_many({"timestamp": {"$lt": cutoff}})

    # Log the purge itself
    await log_audit_event(
        action="audit_purge",
        entity_type="system",
        entity_id="audit_trail",
        user_id=user["user_id"],
        details=f"Purged {result.deleted_count} audit logs older than {days} days.",
        sensitive_data_accessed=True,
    )

    return {"deleted_count": result.deleted_count, "cutoff_date": cutoff, "retention_days": days}
