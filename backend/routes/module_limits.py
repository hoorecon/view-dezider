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
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user, require_super_admin

router = APIRouter(tags=["Module Free-Use Limits"])

# The three "key" modules the user explicitly named. Every OTHER module_key
# resolves to unlimited unless an admin adds a config row for it.
GATED_MODULES = ["solution_finder", "pros_cons", "my_dezider"]

# ── Default seed. Uses the ACTUAL tier / user_type values that live in the
#    system (see /admin/acm/user/{id}/type valid_types list). `-1` = unlimited.
_GATED_DEFAULT_2 = {"solution_finder": 2, "pros_cons": 2, "my_dezider": 2}
_GATED_UNLIMITED = {"solution_finder": -1, "pros_cons": -1, "my_dezider": -1}
_DEFAULT_LIMITS: Dict[str, Dict[str, int]] = {
    # Free-tier-ish → capped 2/each
    "guest":                    _GATED_DEFAULT_2,
    "free":                     _GATED_DEFAULT_2,
    "trial":                    _GATED_DEFAULT_2,
    "starter_trial":            _GATED_DEFAULT_2,
    "pro_trial":                _GATED_DEFAULT_2,
    "premium_trial":            _GATED_DEFAULT_2,
    # Real paying users → unlimited. `basic/pro/premium/enterprise` come from
    # credit_wallets.current_plan (subscription_plans.tier).
    "paid":                     _GATED_UNLIMITED,
    "basic":                    _GATED_UNLIMITED,
    "pro":                      _GATED_UNLIMITED,
    "premium":                  _GATED_UNLIMITED,
    "enterprise":               _GATED_UNLIMITED,
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

_seeded = False


async def _ensure_seed():
    """Seed the default table once (idempotent)."""
    global _seeded
    if _seeded:
        return
    for tier, mods in _DEFAULT_LIMITS.items():
        for m, lim in mods.items():
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
    """Find the caller's ACTIVE tier.

    Priority (higher wins):
      1. `users.user_type` if it's a SPECIAL override (alpha/beta/ut/it/paid_*
         etc.) — set explicitly by admin.
      2. `credit_wallets.current_plan` if there's an active paid subscription
         (status active or manual) — this is what `apply_charge()` sets.
      3. `users.user_type` if it's the default "free"/"guest"/"trial".
      4. Fallback → "free".
    """
    uid = user.get("user_id")
    doc = await db.users.find_one({"user_id": uid}, {"_id": 0, "user_type": 1})
    user_type = str((doc or {}).get("user_type") or "").lower().strip()
    _default_types = {"", "free", "guest", "trial"}

    # 1) explicit admin override — always wins
    if user_type and user_type not in _default_types:
        return user_type

    # 2) active paid subscription — beats default user_type='free'
    w = await db.credit_wallets.find_one({"user_id": uid}, {"_id": 0, "current_plan": 1, "subscription_status": 1})
    if w:
        cp = str(w.get("current_plan") or "").lower()
        st = str(w.get("subscription_status") or "").lower()
        if cp and cp != "free" and st in {"active", "manual", "pending"}:
            return cp

    # 3) default tier types
    if user_type:
        return user_type

    # 4) fallback
    return (user.get("tier") or user.get("plan_tier") or "free").lower()


async def _get_limit(tier: str, module_key: str) -> int:
    """Return the free-use limit for (tier, module). -1 = unlimited."""
    await _ensure_seed()
    row = await db.module_free_limits.find_one(
        {"tier": tier, "module": module_key}, {"_id": 0, "limit": 1},
    )
    if row:
        return int(row.get("limit", -1))
    # Unknown module → unlimited (only 3 modules are gated by design).
    return -1


async def _get_usage(user_id: str, module_key: str) -> int:
    row = await db.module_usage_counters.find_one(
        {"user_id": user_id, "module": module_key}, {"_id": 0, "count": 1},
    )
    return int(row["count"]) if row else 0


# ─────────────────── public helpers used by create endpoints ───────────────────

async def check_and_reserve_usage(user: dict, module_key: str) -> None:
    """Blocks a create call once free quota is exhausted for the caller's tier.
    Increments the counter atomically. Raises 402 with a friendly upgrade message
    when limit reached. Silently allows all admins/super-admins."""
    role = (user.get("role") or "").lower()
    if role in {"super_admin", "admin"}:
        return
    tier = await _resolve_tier(user)
    limit = await _get_limit(tier, module_key)
    if limit < 0:
        return  # unlimited
    used = await _get_usage(user["user_id"], module_key)
    if used >= limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"You've used all {limit} free {module_key.replace('_', ' ')} "
                f"creations on the {tier} plan. Upgrade to Basic / Pro for unlimited access."
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


@router.get("/admin/module-limits")
async def admin_get_limits(user: dict = Depends(require_super_admin)):
    await _ensure_seed()
    rows = await db.module_free_limits.find({}, {"_id": 0}).to_list(500)
    tiers = sorted({r["tier"] for r in rows} | set(_DEFAULT_LIMITS.keys()))
    modules = sorted({r["module"] for r in rows} | set(GATED_MODULES))
    return {"rows": rows, "tiers": tiers, "modules": modules,
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
