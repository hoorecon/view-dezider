"""
Free-Usage Limits per Module (WOWO Access Control add-on)
==========================================================
Enables an admin to cap the number of times a new user can create records in
key modules before hitting a paywall / upgrade prompt.

Tier resolution (checked in this order):
  1. `users.user_type` — set via /admin/acm/user/{id}/type — covers guest,
     free, trial, paid, starter_trial, pro_trial, premium_trial, alpha, beta,
     unit_tester (ut), integration_tester (it), on_demand_retail_buyer, etc.
  2. `credit_wallets.current_plan` — set by `apply_charge()` on payment
     success — covers the four subscription tiers seeded from
     `subscription_plans.tier`: free / basic / pro / premium / enterprise.
  3. Fallback → "free".

Default configuration (seeded on first read):
  guest / free / trial / *_trial tiers → solution_finder=2, pros_cons=2, my_dezider=2
  Everyone else (paid, basic, pro, premium, enterprise, alpha, beta,
    unit_tester, integration_tester, admin, super_admin) → unlimited

Endpoints:
  GET  /api/admin/module-limits                Full config table
  PUT  /api/admin/module-limits                Bulk update
  GET  /api/me/module-usage                    Caller's current counts + limits

Public helper:
  await check_and_reserve_usage(user, module_key)
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user, require_super_admin

log = logging.getLogger("module_limits")

router = APIRouter(tags=["Module Free-Use Limits"])

# The key modules and features governed by Free-Use & On-Demand limits.
GATED_MODULES = [
    "my_dezider",
    "pros_cons",
    "solution_finder",
    "group_decision",
    "book_expert",
    "expert_review",
    "expire_days",
]

# ── Default seed. `-1` = unlimited.
_GATED_DEFAULT_2 = {
    "my_dezider": 2, "pros_cons": 2, "solution_finder": 2,
    "group_decision": 0, "book_expert": 0, "expert_review": 0,
    "expire_days": 30,
}
_GATED_UNLIMITED = {
    "my_dezider": -1, "pros_cons": -1, "solution_finder": -1,
    "group_decision": -1, "book_expert": -1, "expert_review": -1,
    "expire_days": -1,
}

_DEFAULT_LIMITS: Dict[str, Dict[str, int]] = {
    # Free-tier-ish → capped 2/each
    "guest":                    _GATED_DEFAULT_2,
    "free":                     _GATED_DEFAULT_2,
    "trial":                    _GATED_DEFAULT_2,
    "starter_trial":            _GATED_DEFAULT_2,
    "basic_trial":              _GATED_DEFAULT_2,
    "pro_trial":                _GATED_DEFAULT_2,
    "premium_trial":            _GATED_DEFAULT_2,
    # Real paying users → unlimited. `basic/pro/premium/enterprise` come from
    # credit_wallets.current_plan (subscription_plans.tier).
    "paid":                     _GATED_UNLIMITED,
    "basic":                    _GATED_UNLIMITED,
    "pro":                      _GATED_UNLIMITED,
    "premium":                  _GATED_UNLIMITED,
    "enterprise":               _GATED_UNLIMITED,
    # On-demand level tiers (L1, L2, L3, L4)
    "on_demand_l1": {
        "my_dezider": 1, "pros_cons": 1, "solution_finder": 1,
        "group_decision": 0, "book_expert": 0, "expert_review": 0,
        "expire_days": 30,
    },
    "on_demand_l2": {
        "my_dezider": 5, "pros_cons": 5, "solution_finder": 5,
        "group_decision": 5, "book_expert": 5, "expert_review": 0,
        "expire_days": 365,
    },
    "on_demand_l3": {
        "my_dezider": 0, "pros_cons": 0, "solution_finder": 0,
        "group_decision": 0, "book_expert": 1, "expert_review": 0,
        "expire_days": 90,
    },
    "on_demand_l4": {
        "my_dezider": 0, "pros_cons": 0, "solution_finder": 0,
        "group_decision": 0, "book_expert": 1, "expert_review": 1,
        "expire_days": 90,
    },
    # On-demand storefront buyers → unlimited (they've paid per unit).
    "on_demand_retail_buyer":   _GATED_UNLIMITED,
    "on_demand_bulk_buyer":     _GATED_UNLIMITED,
    # Internal QA / testers → unlimited by convention.
    "alpha":                    _GATED_UNLIMITED,
    "beta":                     _GATED_UNLIMITED,
    "unit_tester":              _GATED_UNLIMITED,
    "integration_tester":       _GATED_UNLIMITED,
    # Staff — also caught earlier by the role check but seeded for grid display.
    "super_admin":              _GATED_UNLIMITED,
    "admin":                    _GATED_UNLIMITED,
}

# Tiers that are ALWAYS unlimited (-1) under Module Free-Use Limits.
# Paid subscription plans are governed by the Access Control Matrix (ACM),
# NOT by the free-use limits.
UNLIMITED_EXEMPT_TIERS = {
    "paid", "basic", "pro", "premium", "enterprise",
    "on_demand_retail_buyer", "on_demand_bulk_buyer",
    "alpha", "beta", "unit_tester", "integration_tester",
    "admin", "super_admin", "co_admin"
}

_seeded = False


async def _ensure_seed():
    """Seed default limits once on first start. Preserves admin configuration."""
    global _seeded
    if _seeded:
        return
    for tier, mods in _DEFAULT_LIMITS.items():
        for m, lim in mods.items():
            if tier == "on_demand_l2":
                await db.module_free_limits.update_one(
                    {"tier": tier, "module": m},
                    {"$set": {"limit": lim, "updated_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True,
                )
            else:
                await db.module_free_limits.update_one(
                    {"tier": tier, "module": m},
                    {"$setOnInsert": {
                        "tier": tier, "module": m, "limit": lim,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
    _seeded = True


async def _resolve_tier(user: dict) -> str:
    """Find the caller's ACTIVE tier for Module Free-Use Limits.

    Priority (higher wins):
      1. `credit_wallets.current_plan` if there's an active paid subscription
         (basic / pro / premium / enterprise) — this is set on payment.
      2. `users.subscription_plan` if set to a paid plan.
      3. Active entitlement in `user_entitlements` (L1 -> on_demand_l1, L2 -> on_demand_l2, etc.)
      4. `users.user_type` if it's a special override (alpha/beta/unit_tester/integration_tester/guest/trial).
      5. `users.user_type` default.
      6. Fallback → "free".
    """
    uid = user.get("user_id") if isinstance(user, dict) else None

    # 1) active paid subscription plan — beats generic user_type='paid'
    if uid:
        w = await db.credit_wallets.find_one({"user_id": uid}, {"_id": 0, "current_plan": 1, "subscription_status": 1})
        if w:
            cp = str(w.get("current_plan") or "").lower()
            st = str(w.get("subscription_status") or "").lower()
            if cp and cp not in {"free", "none"} and st in {"active", "manual", "pending"}:
                return cp

        # 2) SKU entitlement check (active balance first, then granted SKU)
        active_ent = await db.user_entitlements.find_one(
            {"user_id": uid, "status": "active"},
            {"_id": 0, "sku_code": 1},
            sort=[("granted_at", -1)],
        )
        if active_ent:
            code = str(active_ent.get("sku_code") or "").upper()
            if code == "L1":
                return "on_demand_l1"
            elif code == "L2":
                return "on_demand_l2"
            elif code == "L3":
                return "on_demand_l3"
            elif code == "L4":
                return "on_demand_l4"

    doc = await db.users.find_one({"user_id": uid}, {"_id": 0, "user_type": 1, "subscription_plan": 1}) if uid else None
    user_type = str((doc or {}).get("user_type") or (user.get("user_type") if isinstance(user, dict) else "") or "").lower().strip()
    sub_plan = str((doc or {}).get("subscription_plan") or (user.get("subscription_plan") if isinstance(user, dict) else "") or "").lower().strip()

    if sub_plan and sub_plan not in {"free", "none"}:
        return sub_plan

    # Special tester/trial types (alpha, beta, unit_tester, integration_tester, guest, trial)
    if user_type and user_type not in {"", "free", "guest", "trial", "paid"}:
        return user_type

    if user_type == "paid":
        return sub_plan if sub_plan else "pro"

    if user_type:
        return user_type

    return (user.get("tier") or user.get("plan_tier") or "free").lower()


TRIAL_COUNT_MODULES = {"my_dezider", "dezider", "pros_cons", "solution_finder"}
_TRIAL_FOR_PLAN = {
    "free": "basic_trial",
    "guest": "basic_trial",
    "none": "basic_trial",
    "trial": "basic_trial",
    "on_demand_l1": "basic_trial",
    "on_demand_l2": "basic_trial",
    "on_demand_l3": "basic_trial",
    "on_demand_l4": "basic_trial",
    "on_demand_retail_buyer": "basic_trial",
    "on_demand_bulk_buyer": "basic_trial",
    "basic": "pro_trial",
    "starter": "pro_trial",
    "paid_basic": "pro_trial",
    "paid_starter": "pro_trial",
    "pro": "premium_trial",
    "paid_pro": "premium_trial",
}
TRIAL_LABELS = {
    "basic_trial": "Basic trial",
    "pro_trial": "Pro trial",
    "premium_trial": "Premium trial",
}


def _canonical_plan(text: str) -> str:
    """Map a plan tier or display name onto basic / pro / premium."""
    t = (text or "").lower()
    if "premium" in t or "enterprise" in t:
        return "premium"
    if t in {"pro", "paid_pro"} or " pro" in f" {t}" or t.startswith("pro ") or t.endswith(" pro") or "pro plan" in t:
        return "pro"
    if "basic" in t or "starter" in t:
        return "basic"
    return ""


async def _paid_subscription_tier(uid: str) -> str:
    """Tier of the subscription the plans page treats as current.

    Uses the saved plan name and tier, not only the short wallet code, so a
    plan titled Premium is not mistaken for Free.
    """
    if not uid:
        return ""
    w = await db.credit_wallets.find_one(
        {"user_id": uid},
        {"_id": 0, "current_plan": 1, "subscription_status": 1, "subscription_plan_id": 1, "subscription_end": 1},
    )
    if not w:
        return ""
    status = str(w.get("subscription_status") or "").lower()
    if status not in {"active", "manual", "pending", "cancelled"}:
        return ""
    end = w.get("subscription_end")
    if status == "cancelled" and end:
        end_dt = end
        if isinstance(end, str):
            try:
                end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            except Exception:
                end_dt = None
        if end_dt is not None:
            if getattr(end_dt, "tzinfo", None) is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt <= datetime.now(timezone.utc):
                return ""
    plan = None
    plan_id = w.get("subscription_plan_id")
    if plan_id:
        plan = await db.subscription_plans.find_one(
            {"plan_id": plan_id}, {"_id": 0, "tier": 1, "name": 1},
        )
    blob = " ".join([
        str((plan or {}).get("tier") or ""),
        str((plan or {}).get("name") or ""),
        str(w.get("current_plan") or ""),
    ])
    return _canonical_plan(blob)


def trial_offer_key(plan_tier: str) -> str:
    """The single trial this plan may see. Empty string when none applies."""
    return _TRIAL_FOR_PLAN.get(str(plan_tier or "").lower(), "")


async def _active_trial_type(user: dict) -> str:
    """Return basic_trial / pro_trial / premium_trial while that trial is in date."""
    from core.user_type_resolver import _is_trial_active
    uid = user.get("user_id") if isinstance(user, dict) else None
    doc = user if isinstance(user, dict) else {}
    if uid and not doc.get("trial_expires_at"):
        stored = await db.users.find_one(
            {"user_id": uid}, {"_id": 0, "trial_type": 1, "trial_expires_at": 1},
        )
        if stored:
            doc = {**doc, **stored}
    found = _is_trial_active(doc) or ""
    if found == "starter_trial":
        found = "basic_trial"
    if found not in TRIAL_LABELS:
        return ""
    paid = await _paid_subscription_tier(uid) if uid else ""
    allowed = trial_offer_key(paid) if paid else found
    if paid and found != allowed:
        return ""
    return found


async def underlying_plan_tier(user: dict) -> str:
    """Plan used to choose the trial, ignoring an in-progress trial type."""
    uid = user.get("user_id") if isinstance(user, dict) else None
    paid = await _paid_subscription_tier(uid) if uid else ""
    if paid:
        return paid
    tier = await _resolve_tier(user)
    if tier in TRIAL_LABELS or tier == "starter_trial":
        uid = user.get("user_id")
        w = await db.credit_wallets.find_one(
            {"user_id": uid}, {"_id": 0, "current_plan": 1, "subscription_status": 1},
        ) if uid else None
        if w:
            cp = str(w.get("current_plan") or "").lower()
            st = str(w.get("subscription_status") or "").lower()
            if cp and cp not in {"free", "none"} and st in {"active", "manual", "pending"}:
                return cp
        return "free"
    return tier


async def build_trial_offer(user: dict) -> dict:
    """One trial card for this user, with the live free-use counts."""
    plan = await underlying_plan_tier(user)
    offer = trial_offer_key(plan)
    active = await _active_trial_type(user)
    if not offer and not active:
        return {"eligible": False, "plan_tier": plan}
    shown = active or offer
    await _ensure_seed()
    limits = {}
    for module in ("my_dezider", "pros_cons", "solution_finder", "expire_days"):
        limits[module] = await _get_limit(shown, module)
    usage = {}
    uid = user.get("user_id")
    for module in ("my_dezider", "pros_cons", "solution_finder"):
        used = await _get_usage(uid, module) if uid else 0
        cap = limits[module]
        remaining = max(0, cap - used) if cap >= 0 else -1
        usage[module] = {
            "limit": cap,
            "used": used,
            "remaining": remaining,
        }
    doc = await db.users.find_one(
        {"user_id": uid}, {"_id": 0, "trial_expires_at": 1},
    ) if uid else None
    expires = (doc or {}).get("trial_expires_at")
    remaining_days = None
    if active and expires:
        if isinstance(expires, str):
            try:
                expires_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except Exception:
                expires_dt = None
        else:
            expires_dt = expires
        if expires_dt is not None:
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            seconds = (expires_dt - datetime.now(timezone.utc)).total_seconds()
            remaining_days = max(0, int((seconds + 86399) // 86400))
    return {
        "eligible": bool(offer) or bool(active),
        "plan_tier": plan,
        "trial_type": shown,
        "name": TRIAL_LABELS.get(shown, shown),
        "active": bool(active) and active == shown,
        "expires_at": (doc or {}).get("trial_expires_at"),
        "expire_days": limits["expire_days"],
        "remaining_days": remaining_days,
        "limits": usage,
    }


async def _get_limit(tier: str, module_key: str) -> int:
    """Return the free-use limit for (tier, module) from db.module_free_limits.
    -1 = unlimited. Admin settings in /admin/module-limits are strictly respected."""
    await _ensure_seed()
    row = await db.module_free_limits.find_one(
        {"tier": str(tier or "").lower(), "module": module_key}, {"_id": 0, "limit": 1},
    )
    if row:
        return int(row.get("limit", -1))
    return -1


async def _get_usage(user_id: str, module_key: str) -> int:
    row = await db.module_usage_counters.find_one(
        {"user_id": user_id, "module": module_key}, {"_id": 0, "count": 1},
    )
    cnt = int(row["count"]) if row else 0
    # Also count actual docs in DB (excluding sample records) so user creations are strictly accounted for
    actual = 0
    sample_filter = {"is_sample": {"$ne": True}}
    if module_key in ("my_dezider", "dezider"):
        actual = await db.decisions.count_documents({"user_id": user_id, **sample_filter})
    elif module_key == "pros_cons":
        actual = await db.pros_cons.count_documents({"user_id": user_id, **sample_filter})
    elif module_key == "swot":
        actual = await db.swot.count_documents({"user_id": user_id, **sample_filter})
    elif module_key == "solution_finder":
        actual = await db.solution_finders.count_documents({"user_id": user_id, **sample_filter})
    elif module_key in ("group_decision", "collaboration", "group_decisions"):
        actual = await db.collaboration_sessions.count_documents({"owner_id": user_id, **sample_filter})
    return max(cnt, actual)


async def _get_combined_l2_usage(user_id: str) -> int:
    m_cnt = await _get_usage(user_id, "my_dezider")
    p_cnt = await _get_usage(user_id, "pros_cons")
    s_cnt = await _get_usage(user_id, "solution_finder")
    b_cnt = await _get_usage(user_id, "book_expert")
    g_cnt = await _get_usage(user_id, "group_decision")
    return m_cnt + p_cnt + s_cnt + b_cnt + g_cnt


# ─────────────────── public helpers used by create endpoints ───────────────────

MODULE_TO_ACM_FEATURE = {
    "my_dezider": "my_dezider_create",
    "dezider": "my_dezider_create",
    "pros_cons": "pros_cons",
    "swot": "swot_analysis",
    "solution_finder": "solution_finder",
    "group_decision": "group_decision",
}


async def check_ai_feature_plan_access(user: dict, feature_name: str) -> None:
    """Restricts AI features ('Fetch My Best Factors', 'Find My Best Options', 'AI Assess ALL')
    for free plan users, guest users, and on-demand users (L1-L4).
    Allows subscription plan users (basic, pro, premium, enterprise) and admins."""
    role = str(user.get("role") or "").lower()
    if role in {"super_admin", "admin", "co_admin"}:
        return

    tier = await _resolve_tier(user)
    tier_lc = str(tier or "").lower()

    restricted_tiers = {
        "free", "guest", "trial",
        "on_demand_l1", "on_demand_l2", "on_demand_l3", "on_demand_l4"
    }

    if tier_lc in restricted_tiers:
        raise HTTPException(
            status_code=402,
            detail=f"‘{feature_name}’ is available on subscription plans. Upgrade your plan to access this feature."
        )


async def check_and_reserve_usage(user: dict, module_key: str) -> None:
    """Blocks a create call once free quota is exhausted or if ACM disables creation.
    Increments the counter atomically. Raises 403 / 402 with upgrade message.
    Silently allows all admins/super-admins."""
    role = (user.get("role") or "").lower()
    if role in {"super_admin", "admin", "co_admin"}:
        return

    # Check Conflict Breaker hard plan tier restriction (Pro and Premium plans only)
    if module_key in ("conflict_breaker", "conflict-breaker"):
        tier = await _resolve_tier(user)
        allowed_tiers = {"pro", "premium", "enterprise", "paid", "alpha", "beta", "unit_tester", "integration_tester", "admin", "super_admin", "co_admin"}
        if tier.lower() not in allowed_tiers:
            raise HTTPException(
                status_code=402,
                detail="The Conflict Breaker is available on Pro and Premium plans. Upgrade your plan to access this feature."
            )
        return

    # Check Access Control Matrix rule first (enforce level & monthly quota)
    feature_id = MODULE_TO_ACM_FEATURE.get(module_key)
    if feature_id:
        try:
            from core.acm_engine import check_feature_access
            acm_res = await check_feature_access(user, feature_id, check_quota=True)
            if not acm_res.get("allowed") or acm_res.get("access_level") in ("read", "locked", "hidden", "quota_exceeded"):
                level = acm_res.get("access_level", "disabled")
                if level == "quota_exceeded":
                    msg = f"You have reached your limit of {acm_res.get('quota_limit')} creation(s) under Access Control Matrix configuration. Upgrade your plan for higher limits."
                    raise HTTPException(status_code=402, detail=msg)
                msg = acm_res.get("upgrade_message") or f"Creation is {level} for your plan under Access Control Matrix rules."
                raise HTTPException(status_code=403, detail=msg)
        except HTTPException:
            raise
        except Exception as e:
            log.warning(f"ACM check error in module_limits: {e}")

    # Check active SKU entitlement or admin skip first
    try:
        from routes.sku_store import has_any_paid_access
        paid_res = await has_any_paid_access(user["user_id"], module_key)
        if paid_res.get("has_access"):
            via = paid_res.get("via")
            bal = paid_res.get("balance", 0)
            trial_tier = await _active_trial_type(user)
            counted = bool(trial_tier) and module_key in TRIAL_COUNT_MODULES
            if via == "admin_skip" or (bal > 0 and not counted):
                # Admin skip, or a consumable SKU while this module is not on a trial count.
                return
    except Exception as e:
        log.warning(f"has_any_paid_access check in module_limits failed: {e}")

    tier = await _resolve_tier(user)
    trial_tier = await _active_trial_type(user)
    if trial_tier and module_key in TRIAL_COUNT_MODULES:
        tier = trial_tier
    limit = await _get_limit(tier, module_key)
    if limit < 0:
        return  # unlimited

    # If tier is on_demand_l1, enforce shared 1-unit quota across MyDezider, Pros & Cons, Solution Finder
    if tier == "on_demand_l1" and module_key in ("my_dezider", "dezider", "pros_cons", "solution_finder"):
        diy_used = (
            await _get_usage(user["user_id"], "my_dezider") +
            await _get_usage(user["user_id"], "pros_cons") +
            await _get_usage(user["user_id"], "solution_finder")
        )
        if diy_used >= limit:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"You've used your {limit} L1 creation across My Dezider, Pros & Cons, or Solution Finder. "
                    f"Upgrade to L2 (5-decision bundle) or Basic / Pro for higher limits."
                ),
            )
    elif tier == "on_demand_l2" and module_key in ("my_dezider", "dezider", "pros_cons", "solution_finder", "group_decision", "book_expert"):
        l2_used = await _get_combined_l2_usage(user["user_id"])
        if l2_used >= limit:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"You've used all {limit} L2 units across the decision bundle, instant meetings, and appointment bookings. "
                    f"Purchase another bundle or an L3 booking to continue."
                ),
            )
    else:
        used = await _get_usage(user["user_id"], module_key)
        if used >= limit:
            raise HTTPException(
                status_code=402,
                detail=(
                    f"You've used all {limit} {module_key.replace('_', ' ')} "
                    f"creations on the {tier} plan. Upgrade your plan for higher limits."
                ),
            )

    # Reserve
    await db.module_usage_counters.update_one(
        {"user_id": user["user_id"], "module": module_key},
        {"$inc": {"count": 1},
         "$set": {"user_id": user["user_id"], "module": module_key,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


# ─────────────────── user endpoint ───────────────────

@router.get("/me/module-usage")
async def my_usage(user: dict = Depends(get_current_user)):
    await _ensure_seed()
    tier = await _resolve_tier(user)
    out = []
    for m in GATED_MODULES:
        lim = await _get_limit(tier, m)
        used = await _get_usage(user["user_id"], m)
        out.append({
            "module": m, "limit": lim,
            "used": used,
            "remaining": (lim - used) if lim >= 0 else -1,
            "unlimited": lim < 0,
        })
    return {"tier": tier, "usage": out}


# ─────────────────── admin endpoints ───────────────────

class LimitRow(BaseModel):
    tier: str
    module: str
    limit: int  # -1 = unlimited


class LimitsBulkUpdate(BaseModel):
    rows: List[LimitRow]


HIDDEN_ADMIN_TIERS = {
    "enterprise",
    "beta",
    "on_demand_bulk_buyer",
    "on_demand_retail_buyer",
    "paid",
    "starter_trial",
    "trial",
}


@router.get("/admin/module-limits")
async def admin_get_limits(user: dict = Depends(require_super_admin)):
    await _ensure_seed()
    # Purge any obsolete module rows (e.g. on_demand_combo) from MongoDB
    await db.module_free_limits.delete_many({"module": {"$nin": GATED_MODULES}})
    rows = await db.module_free_limits.find({"module": {"$in": GATED_MODULES}}, {"_id": 0}).to_list(500)
    visible_rows = [r for r in rows if r.get("tier") not in HIDDEN_ADMIN_TIERS]
    all_known_tiers = {r["tier"] for r in rows} | set(_DEFAULT_LIMITS.keys())
    tiers = sorted(t for t in all_known_tiers if t not in HIDDEN_ADMIN_TIERS)
    modules = [m for m in GATED_MODULES]
    return {"rows": visible_rows, "tiers": tiers, "modules": modules,
            "gated_modules": GATED_MODULES}


@router.put("/admin/module-limits")
async def admin_put_limits(body: LimitsBulkUpdate, user: dict = Depends(require_super_admin)):
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in body.rows:
        await db.module_free_limits.update_one(
            {"tier": r.tier, "module": r.module},
            {"$set": {"limit": int(r.limit), "updated_at": now_iso,
                      "updated_by": user.get("user_id")}},
            upsert=True,
        )
    return {"message": f"Updated {len(body.rows)} row(s)."}
