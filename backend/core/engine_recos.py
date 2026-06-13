"""Engine tiering for Deep-Import stages — margin protection.

Holds the per-stage AI tier config (fast | precise | job) that
routes/deep_import.py honors at runtime, plus data-driven recommendations
computed from the per-run AI call trace (url_import_runs.ai_calls):
success rate + avg credits per tier, per stage.

"job" = follow the tier the user picked when starting the deep import.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from core.database import db

logger = logging.getLogger(__name__)

STAGES = ("links_pick", "hubs_pick", "consolidate")
DEFAULT_TIERS: Dict[str, str] = {"links_pick": "fast", "hubs_pick": "fast",
                                 "consolidate": "job"}
VALID_TIERS = ("fast", "precise", "job")
STAGE_LABEL = {"links_pick": "Link pick", "hubs_pick": "Hub locate",
               "consolidate": "Consolidate"}

_CFG_KEY = "deep_stage_tiers"

# ── Import quality floor (admin-tunable) ─────────────────────────────────────
# A URL-import run is only stamped `success` when the merged factor count is
# at least this many. Anything below the floor is recorded as `partial` — the
# user still got a result, but the run is flagged in Admin Intel + fed into
# the Auto-Tune candidate pool because it's silently under-extracted.
# Carwale "best Electric cars under 10 lakh" regression (2 factors only) is
# the canonical example this floor catches.
_QF_KEY = "import_quality_floor"
DEFAULT_QUALITY_FLOOR = 4


def _now():
    return datetime.now(timezone.utc)


async def get_quality_floor() -> int:
    doc = await db.app_config.find_one({"key": _QF_KEY}, {"_id": 0}) or {}
    v = doc.get("min_factors")
    return v if isinstance(v, int) and 1 <= v <= 50 else DEFAULT_QUALITY_FLOOR


async def set_quality_floor(min_factors: int, admin_id: str) -> int:
    if not isinstance(min_factors, int) or not (1 <= min_factors <= 50):
        raise ValueError("min_factors must be an integer between 1 and 50")
    await db.app_config.update_one(
        {"key": _QF_KEY},
        {"$set": {"min_factors": min_factors, "updated_by": admin_id, "updated_at": _now()}},
        upsert=True)
    logger.info("import quality floor set to %d by %s", min_factors, admin_id)
    return await get_quality_floor()


def _norm_stage(stage: str) -> str:
    return "links_pick" if str(stage).startswith("links_pick") else str(stage)


def _tier_of(provider: str) -> str:
    return "precise" if provider == "emergent_precise" else "fast"


async def get_stage_tiers() -> Dict[str, str]:
    doc = await db.app_config.find_one({"key": _CFG_KEY}, {"_id": 0}) or {}
    return {s: (doc.get(s) if doc.get(s) in VALID_TIERS else DEFAULT_TIERS[s])
            for s in STAGES}


async def set_stage_tier(stage: str, tier: str, admin_id: str) -> Dict[str, str]:
    if stage not in STAGES or tier not in VALID_TIERS:
        raise ValueError(f"stage must be one of {STAGES}, tier one of {VALID_TIERS}")
    await db.app_config.update_one(
        {"key": _CFG_KEY},
        {"$set": {stage: tier, "updated_by": admin_id, "updated_at": _now()}},
        upsert=True)
    logger.info("deep stage tier set: %s → %s by %s", stage, tier, admin_id)
    return await get_stage_tiers()


async def compute_recos(days: int = 30) -> Dict[str, Any]:
    """Per-stage engine stats + a conservative recommendation. Success is
    attributed from the parent run's status to each of its traced calls."""
    since = _now() - timedelta(days=days)
    rows = await db.url_import_runs.aggregate([
        {"$match": {"endpoint": "deep_import", "ts": {"$gte": since},
                    "ai_calls.0": {"$exists": True}}},
        {"$project": {"_id": 0, "status": 1, "ai_calls": 1}},
        {"$unwind": "$ai_calls"},
        {"$group": {
            "_id": {"stage": "$ai_calls.stage", "provider": "$ai_calls.provider"},
            "n": {"$sum": 1},
            "ok": {"$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}},
            "credits": {"$avg": "$ai_calls.credits"},
        }},
    ]).to_list(200)

    # stage → tier → aggregated stats
    agg: Dict[str, Dict[str, Dict[str, float]]] = {}
    for r in rows:
        stage = _norm_stage(r["_id"]["stage"] or "")
        if stage not in STAGES:
            continue
        t = _tier_of(r["_id"]["provider"] or "")
        cell = agg.setdefault(stage, {}).setdefault(t, {"n": 0, "ok": 0, "cr_sum": 0.0})
        cell["n"] += r["n"]
        cell["ok"] += r["ok"]
        cell["cr_sum"] += float(r["credits"] or 0) * r["n"]

    current = await get_stage_tiers()
    out: List[Dict[str, Any]] = []
    for stage in STAGES:
        tiers_stats = {}
        for t, c in (agg.get(stage) or {}).items():
            tiers_stats[t] = {"runs": c["n"],
                              "success_rate": round(100 * c["ok"] / c["n"], 1) if c["n"] else None,
                              "avg_credits": round(c["cr_sum"] / c["n"], 1) if c["n"] else None}
        fast, precise = tiers_stats.get("fast"), tiers_stats.get("precise")
        cur = current[stage]
        action, reason, saving = "keep", "Not enough data — keep current tier.", None
        if fast and fast["runs"] >= 3 and (fast["success_rate"] or 0) >= 90:
            if cur in ("precise", "job") and stage != "consolidate":
                action = "downgrade_to_fast"
                reason = f"Fast tier succeeds {fast['success_rate']}% over {fast['runs']} calls."
                if precise and precise["avg_credits"]:
                    saving = round(precise["avg_credits"] - (fast["avg_credits"] or 0), 1)
            else:
                action, reason = "keep", f"Fast tier holding {fast['success_rate']}% over {fast['runs']} calls — no change needed."
        if fast and fast["runs"] >= 3 and (fast["success_rate"] or 0) < 60 and cur == "fast":
            action = "upgrade_to_precise"
            reason = f"Fast tier only succeeds {fast['success_rate']}% over {fast['runs']} calls — quality first."
        if stage == "consolidate" and precise and precise["runs"] >= 3 \
                and (precise["success_rate"] or 0) >= 90 and not fast and cur in ("precise", "job"):
            action = "try_fast"
            reason = (f"Precise succeeds {precise['success_rate']}% at "
                      f"{precise['avg_credits']} cr/call — no fast sample yet; "
                      "try fast on a few runs to validate the saving.")
        out.append({"stage": stage, "label": STAGE_LABEL[stage], "current_tier": cur,
                    "tiers": tiers_stats, "recommendation": action,
                    "reason": reason, "projected_saving": saving})
    return {"days": days, "stages": out, "tiers": current}
