"""
Free-Usage Limits per Module (WOWO Access Control add-on)
==========================================================
Enables an admin to cap the number of times a new user can create records in
key modules before hitting a paywall / upgrade prompt.

Default configuration (seeded on first read):
  free / guest / trial tiers → solution_finder=2, pros_cons=2, my_dezider=2
                                (all other modules = unlimited)
  paid tiers                   → all modules unlimited

Endpoints:
  GET  /api/admin/module-limits                Full config table
  PUT  /api/admin/module-limits                Bulk update
  GET  /api/me/module-usage                    Caller's current counts + limits

Public helper:
  await check_and_reserve_usage(user, module_key)
      → raises HTTPException(402) when the caller has hit their limit
      → otherwise increments the counter atomically
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

# Tiers we ship defaults for. `-1` = unlimited.
_DEFAULT_LIMITS: Dict[str, Dict[str, int]] = {
    "guest":          {"solution_finder": 2, "pros_cons": 2, "my_dezider": 2},
    "free":           {"solution_finder": 2, "pros_cons": 2, "my_dezider": 2},
    "trial":          {"solution_finder": 2, "pros_cons": 2, "my_dezider": 2},
    "paid_starter":   {"solution_finder": -1, "pros_cons": -1, "my_dezider": -1},
    "paid_pro":       {"solution_finder": -1, "pros_cons": -1, "my_dezider": -1},
    "paid_enterprise":{"solution_finder": -1, "pros_cons": -1, "my_dezider": -1},
    "super_admin":    {"solution_finder": -1, "pros_cons": -1, "my_dezider": -1},
    "admin":          {"solution_finder": -1, "pros_cons": -1, "my_dezider": -1},
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


async def _get_limit(tier: str, module_key: str) -> int:
    """Return the free-use limit for (tier, module). -1 = unlimited."""
    await _ensure_seed()
    row = await db.module_free_limits.find_one(
        {"tier": tier, "module": module_key}, {"_id": 0, "limit": 1},
    )
    if row:
        return int(row.get("limit", -1))
    # Unknown module → unlimited by design (user asked: only 3 modules gated).
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
    tier = (user.get("tier") or user.get("plan_tier") or "free").lower()
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
    tier = (user.get("tier") or user.get("plan_tier") or "free").lower()
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
    tiers = sorted({r["tier"] for r in rows})
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
