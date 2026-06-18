"""WOWO-ACM v2 — Unified 5-axis user type resolver.

Single source of truth for "what tier should this user effectively see?".
Returns (user_type, subscription_plan, effective_access_key, reason) so every
gating decision is deterministic and auditable.

Precedence (highest → lowest):
  1. role ∈ {super_admin, admin, co_admin}      → bypass
  2. Active SKU entitlement (per feature)       → handled by store layer
  3. user_type via DB + Razorpay sub status     → standard ACM gating
  4. Default                                    → free

Customer Segments are NOT consulted (analytics-only per architecture decision).
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional

from core.database import db

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"super_admin", "admin", "co_admin"}

# Razorpay slug → ACM plan name (post-rename: Enterprise→Premium, api removed)
RAZORPAY_TO_ACM_PLAN = {
    "basic":      "starter",
    "starter":    "starter",
    "pro":        "pro",
    "premium":    "premium",
    "enterprise": "premium",  # legacy alias
}

TRIAL_DEFAULT_DAYS = {
    "starter_trial": 1,
    "pro_trial":     3,
    "premium_trial": 7,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_trial_active(user: Dict[str, Any]) -> Optional[str]:
    """Return active trial type or None."""
    trial_type = user.get("trial_type")
    expires_at = user.get("trial_expires_at")
    if not trial_type or not expires_at:
        return None
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except Exception:
            return None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > _now() and trial_type in TRIAL_DEFAULT_DAYS:
        return trial_type
    return None


async def _razorpay_active_plan(user_id: str) -> Optional[str]:
    """Return ACM plan name if user has an active Razorpay subscription."""
    sub = await db.razorpay_subscriptions.find_one(
        {"user_id": user_id, "status": {"$in": ["active", "authenticated"]}},
        sort=[("created_at", -1)],
    )
    if not sub:
        return None
    plan = (sub.get("plan_slug") or sub.get("plan_id") or "").lower()
    return RAZORPAY_TO_ACM_PLAN.get(plan)


async def _has_active_on_demand_sku(user_id: str, kind: str) -> bool:
    """True if user has any active SKU of given kind (retail|bulk|wallet)."""
    row = await db.sku_entitlements.find_one({
        "user_id": user_id,
        "kind": kind,
        "active": True,
        "$or": [
            {"expires_at": None},
            {"expires_at": {"$gt": _now()}},
        ],
    })
    return row is not None


async def resolve_user_type(user: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """Compute (user_type, plan, effective_key, reason).

    `effective_key` is what ACM matrix lookups should use.
    `reason` is a human-readable trace for debugging.
    """
    if not user:
        return ("free", "none", "free", "no_user_doc → default free")

    role = (user.get("role") or "user").lower()
    if role in ADMIN_ROLES:
        return ("paid", "premium", "platform_admin",
                f"role={role} → bypass ACM (platform_admin key)")

    user_id = user.get("user_id") or user.get("id") or ""

    # 2a. Active Razorpay subscription
    rzp_plan = await _razorpay_active_plan(user_id) if user_id else None
    if rzp_plan:
        return ("paid", rzp_plan, f"paid_{rzp_plan}",
                f"razorpay_sub.active → user_type=paid plan={rzp_plan}")

    # 2b. Active trial
    trial_type = _is_trial_active(user)
    if trial_type:
        return (trial_type, "none", trial_type,
                f"trial active until {user.get('trial_expires_at')}")

    # 2c. On-demand buyer status
    if user_id:
        if await _has_active_on_demand_sku(user_id, "bulk"):
            return ("on_demand_bulk_buyer", "none", "on_demand_bulk_buyer",
                    "active bulk SKU entitlement")
        if await _has_active_on_demand_sku(user_id, "retail"):
            return ("on_demand_retail_buyer", "none", "on_demand_retail_buyer",
                    "active retail SKU entitlement")

    # 2d. Internal QA flags
    stored_type = (user.get("user_type") or "").lower()
    if stored_type in ("unit_tester", "integration_tester", "alpha", "beta"):
        return (stored_type, "none", stored_type,
                f"user.user_type={stored_type} (internal flag)")

    # 2e. Default
    return ("free", "none", "free", "no active subscription/trial/sku → default free")


async def persist_resolved_type(user_id: str) -> Dict[str, Any]:
    """Re-run resolver and write back to user doc. Called by webhooks + admin actions."""
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        return {"ok": False, "reason": "user_not_found"}
    user_type, plan, effective, reason = await resolve_user_type(user)
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_type": user_type,
            "subscription_plan": plan,
            "effective_access_key": effective,
            "effective_reason": reason,
            "effective_resolved_at": _now(),
        }},
    )
    logger.info("ACM resolver: user=%s → %s/%s (%s)", user_id, user_type, plan, reason)
    return {"ok": True, "user_type": user_type, "plan": plan,
            "effective_access_key": effective, "reason": reason}
