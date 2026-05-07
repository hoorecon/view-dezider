"""
tier_matrix.py — Admin CRUD on the 7-chakra subscription-tier matrix.

  GET   /api/tiers                          — public list of 7 chakra tiers
  GET   /api/tier-matrix                    — public read of full matrix grid
  GET   /api/admin/tier-matrix              — admin read (with seed if empty)
  POST  /api/admin/tier-matrix/seed         — admin: smart-seed missing cells
  PUT   /api/admin/tier-matrix/cell         — admin: set ONE cell (with cascade)
  POST  /api/admin/tier-matrix/bulk         — admin: set MANY cells in one call
  POST  /api/admin/tier-matrix/reset        — admin: wipe + reseed defaults
  GET   /api/me/tier-access                 — current user's unlocked map
  PUT   /api/admin/users/{user_id}/tier     — admin: assign user a tier

Storage:
  • db.tier_matrix : one doc per (module_id, feature_id|null, tier_key) cell
    keys: { matrix_id, module_id, feature_id, tier_key, allowed: bool, updated_at, updated_by }
  • db.users.subscription_tier : "root" | "sacral" | ... | "crown"
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from core.database import db
from core.auth import get_current_user, require_admin
from models.tier_models import (
    CHAKRA_TIERS, TIER_KEYS, SMART_SEED_MIN_TIER, DEFAULT_MIN_TIER,
    TierMatrixCellSet, TierMatrixBulkSet, UserTierAssign,
)

try:
    from routes.customer_segments import _invalidate_pricing_cache
except Exception:  # circular import safety
    def _invalidate_pricing_cache() -> None:
        pass

router = APIRouter(tags=["Tier Matrix — 7 Chakras"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tier_index(key: str) -> int:
    for t in CHAKRA_TIERS:
        if t["key"] == key:
            return t["order"]
    raise HTTPException(400, f"unknown tier '{key}'")


async def _acm_modules_features() -> List[Dict[str, Any]]:
    """Fetch the canonical ACM module list (32 modules, 89 features) from db.acm_modules."""
    return await db.acm_modules.find({}, {"_id": 0}).sort("order", 1).to_list(50)


async def _ensure_seeded() -> None:
    """If the tier_matrix collection is empty, smart-seed it from ACM + rules."""
    count = await db.tier_matrix.count_documents({})
    if count > 0:
        return
    await _smart_seed()


async def _smart_seed() -> Dict[str, int]:
    """Smart-seed the matrix using SMART_SEED_MIN_TIER + module-dominates rule.

    For each module:
      • module-level cell at tier T = Y if module's min_tier <= T (cascades up)
      • each feature cell at tier T = Y if module's min_tier <= T (default open under enabled module)
    """
    modules = await _acm_modules_features()
    inserted = 0
    for mod in modules:
        mid = mod.get("module_id")
        if not mid:
            continue
        min_tier_order = SMART_SEED_MIN_TIER.get(mid, DEFAULT_MIN_TIER)

        # Module-level cells (one per tier)
        for t in CHAKRA_TIERS:
            allowed = (t["order"] >= min_tier_order)
            cell = {
                "matrix_id": f"tm_{uuid.uuid4().hex[:12]}",
                "module_id": mid,
                "feature_id": None,
                "tier_key": t["key"],
                "allowed": allowed,
                "updated_at": _now(),
                "updated_by": "system_smart_seed",
            }
            await db.tier_matrix.insert_one(cell)
            inserted += 1

        # Feature-level cells (default = same as module)
        for f in mod.get("features", []):
            fid = f.get("feature_id")
            if not fid:
                continue
            for t in CHAKRA_TIERS:
                allowed = (t["order"] >= min_tier_order)
                cell = {
                    "matrix_id": f"tm_{uuid.uuid4().hex[:12]}",
                    "module_id": mid,
                    "feature_id": fid,
                    "tier_key": t["key"],
                    "allowed": allowed,
                    "updated_at": _now(),
                    "updated_by": "system_smart_seed",
                }
                await db.tier_matrix.insert_one(cell)
                inserted += 1
    return {"inserted_cells": inserted}


# ----------------------------------------------------------------------
# Public reads
# ----------------------------------------------------------------------
@router.get("/tiers")
async def list_tiers():
    """Public 7-tier metadata — used by the pricing page + admin UI headers."""
    return {"tiers": CHAKRA_TIERS}


@router.get("/tier-matrix")
async def get_public_matrix():
    """Public read of the matrix (no auth) — used by pricing-page comparison table."""
    await _ensure_seeded()
    modules = await _acm_modules_features()
    cells: List[Dict[str, Any]] = []
    async for c in db.tier_matrix.find({}, {"_id": 0}):
        cells.append(c)
    by_key = {(c["module_id"], c.get("feature_id"), c["tier_key"]): c for c in cells}

    rows = []
    for mod in modules:
        mid = mod.get("module_id")
        if not mid:
            continue
        mod_row = {
            "module_id": mid,
            "module_name": mod.get("module_name"),
            "module_icon": mod.get("module_icon"),
            "module_order": mod.get("order"),
            "tiers": {t["key"]: bool(by_key.get((mid, None, t["key"]), {}).get("allowed", False)) for t in CHAKRA_TIERS},
            "features": [],
        }
        for f in mod.get("features", []):
            fid = f.get("feature_id")
            if not fid:
                continue
            mod_row["features"].append({
                "feature_id": fid,
                "feature_name": f.get("feature_name"),
                "tiers": {t["key"]: bool(by_key.get((mid, fid, t["key"]), {}).get("allowed", False)) for t in CHAKRA_TIERS},
            })
        rows.append(mod_row)
    return {"tiers": CHAKRA_TIERS, "rows": rows, "total_modules": len(rows)}


@router.get("/me/tier-access")
async def my_tier_access(user: dict = Depends(get_current_user)):
    """Return the current user's tier + the set of allowed (module, feature) keys."""
    tier_key = user.get("subscription_tier") or "root"
    cells = []
    async for c in db.tier_matrix.find({"tier_key": tier_key, "allowed": True}, {"_id": 0}):
        cells.append(c)
    allowed_modules = sorted({c["module_id"] for c in cells if c.get("feature_id") is None})
    allowed_features = sorted({(c["module_id"], c["feature_id"]) for c in cells if c.get("feature_id") is not None})
    return {
        "tier_key": tier_key,
        "tier_meta": next((t for t in CHAKRA_TIERS if t["key"] == tier_key), None),
        "allowed_modules": allowed_modules,
        "allowed_features": [{"module_id": m, "feature_id": f} for m, f in allowed_features],
    }


# ----------------------------------------------------------------------
# Admin CRUD
# ----------------------------------------------------------------------
@router.get("/admin/tier-matrix")
async def admin_get_matrix(user: dict = Depends(require_admin)):
    """Admin read — same as public but always seeds first if empty."""
    await _ensure_seeded()
    return await get_public_matrix()


@router.post("/admin/tier-matrix/seed")
async def admin_smart_seed(user: dict = Depends(require_admin)):
    """Smart-seed only the missing cells (idempotent)."""
    count = await db.tier_matrix.count_documents({})
    if count > 0:
        return {"ok": True, "message": "matrix already seeded", "existing_cells": count}
    res = await _smart_seed()
    return {"ok": True, **res}


@router.post("/admin/tier-matrix/reset")
async def admin_reset_matrix(user: dict = Depends(require_admin)):
    """Wipe + smart-reseed (admin escape hatch when matrix gets messy)."""
    await db.tier_matrix.delete_many({})
    res = await _smart_seed()
    _invalidate_pricing_cache()
    return {"ok": True, "wiped": True, **res}


async def _set_cell(module_id: str, feature_id: Optional[str], tier_key: str,
                    allowed: bool, by_user: str) -> None:
    """Set ONE cell. Caller is responsible for cascade/dominance rules."""
    if tier_key not in TIER_KEYS:
        raise HTTPException(400, f"unknown tier '{tier_key}'")
    await db.tier_matrix.update_one(
        {"module_id": module_id, "feature_id": feature_id, "tier_key": tier_key},
        {"$set": {
            "module_id": module_id, "feature_id": feature_id, "tier_key": tier_key,
            "allowed": bool(allowed),
            "updated_at": _now(), "updated_by": by_user,
        },
         "$setOnInsert": {"matrix_id": f"tm_{uuid.uuid4().hex[:12]}"}},
        upsert=True,
    )


async def _apply_toggle_with_rules(module_id: str, feature_id: Optional[str],
                                   tier_key: str, allowed: bool, by_user: str) -> Dict[str, Any]:
    """Apply Q1c (cascade ON when toggling ON) + Q2a (module dominates).

    Toggle ON:
      • Set this cell.
      • If feature: require parent module=Y at same tier (auto-enable parent if needed).
      • Cascade up to higher tiers (T+1..7).
      • If module-level: feature children at the same tier default to Y if currently N.
    Toggle OFF:
      • Set this cell.
      • If module-level: force all features under it to N at this tier.
      • No cascade up/down (admin override).
    """
    affected = 0
    tier_idx = _tier_index(tier_key)

    if allowed:  # Toggle ON
        if feature_id is not None:
            # Parent module must be Y at this tier — auto-enable if needed
            parent = await db.tier_matrix.find_one(
                {"module_id": module_id, "feature_id": None, "tier_key": tier_key}, {"_id": 0}
            )
            if not parent or not parent.get("allowed"):
                await _set_cell(module_id, None, tier_key, True, by_user)
                affected += 1

        # Set this cell + cascade up
        for t in CHAKRA_TIERS:
            if t["order"] >= tier_idx:
                # Only cascade-set if currently N (preserve existing OFF overrides only when going DOWN; cascade ON always wins)
                existing = await db.tier_matrix.find_one(
                    {"module_id": module_id, "feature_id": feature_id, "tier_key": t["key"]}, {"_id": 0}
                )
                if not existing or not existing.get("allowed"):
                    await _set_cell(module_id, feature_id, t["key"], True, by_user)
                    affected += 1

        # If module-level toggle ON: enable child features at same tier (only those currently N)
        if feature_id is None:
            modules = await _acm_modules_features()
            mod = next((m for m in modules if m.get("module_id") == module_id), None)
            for f in (mod.get("features", []) if mod else []):
                fid = f.get("feature_id")
                if not fid:
                    continue
                existing = await db.tier_matrix.find_one(
                    {"module_id": module_id, "feature_id": fid, "tier_key": tier_key}, {"_id": 0}
                )
                if not existing or not existing.get("allowed"):
                    await _set_cell(module_id, fid, tier_key, True, by_user)
                    affected += 1

    else:  # Toggle OFF
        await _set_cell(module_id, feature_id, tier_key, False, by_user)
        affected += 1

        # Module dominates: if module is N, force all features N at same tier
        if feature_id is None:
            modules = await _acm_modules_features()
            mod = next((m for m in modules if m.get("module_id") == module_id), None)
            for f in (mod.get("features", []) if mod else []):
                fid = f.get("feature_id")
                if not fid:
                    continue
                await _set_cell(module_id, fid, tier_key, False, by_user)
                affected += 1

    return {"affected_cells": affected}


@router.put("/admin/tier-matrix/cell")
async def admin_set_cell(body: TierMatrixCellSet, user: dict = Depends(require_admin)):
    res = await _apply_toggle_with_rules(
        body.module_id, body.feature_id, body.tier_key, body.allowed, user.get("user_id", "admin")
    )
    return {"ok": True, **res}


@router.post("/admin/tier-matrix/bulk")
async def admin_bulk_set(body: TierMatrixBulkSet, user: dict = Depends(require_admin)):
    total = 0
    for c in body.cells:
        res = await _apply_toggle_with_rules(
            c.module_id, c.feature_id, c.tier_key, c.allowed, user.get("user_id", "admin")
        )
        total += res["affected_cells"]
    return {"ok": True, "input_cells": len(body.cells), "affected_cells": total}


# ----------------------------------------------------------------------
# Assign user to a tier
# ----------------------------------------------------------------------
@router.put("/admin/users/{user_id}/tier")
async def admin_assign_user_tier(user_id: str, body: UserTierAssign, user: dict = Depends(require_admin)):
    if body.tier_key not in TIER_KEYS:
        raise HTTPException(400, f"unknown tier '{body.tier_key}'")
    res = await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"subscription_tier": body.tier_key, "tier_updated_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "user not found")
    return {"ok": True, "user_id": user_id, "tier_key": body.tier_key}
