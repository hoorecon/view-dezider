"""
Karma engine (Collaboration Epic Phase F).

Awards Karma points for collaborative value — accepted public-help contributions,
marketplace clones of your decisions, and positive ratings. Points per event are
admin-configurable (karma_config singleton). The balance reuses the existing
`referral_profiles.karma_balance` so all karma the user earns lives in one place,
and every award is journaled to `karma_ledger`.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from core.database import db

log = logging.getLogger("karma")

DEFAULT_KARMA_CONFIG = {
    "_id": "singleton",
    "enabled": True,
    "points": {
        "contribution_accepted": 10,   # public help: owner accepted your input
        "decision_cloned_free": 5,     # someone free-cloned your decision
        "decision_cloned_paid": 15,    # someone paid-cloned your decision
        "positive_rating": 4,          # per star (so 5★ = 20, 4★ = 16)
        "public_help_resolved": 8,     # your public request reached an accepted answer
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_karma_config() -> dict:
    cfg = await db.karma_config.find_one({"_id": "singleton"})
    if not cfg:
        await db.karma_config.insert_one(dict(DEFAULT_KARMA_CONFIG))
        return dict(DEFAULT_KARMA_CONFIG)
    merged = {**DEFAULT_KARMA_CONFIG, **cfg}
    merged["points"] = {**DEFAULT_KARMA_CONFIG["points"], **(cfg.get("points") or {})}
    return merged


async def award_karma(user_id: str, event: str, *, multiplier: float = 1.0,
                      ref: Optional[dict] = None, reason: Optional[str] = None) -> int:
    """Award karma for an event. Returns points awarded (0 if disabled/zero)."""
    if not user_id:
        return 0
    cfg = await get_karma_config()
    if not cfg.get("enabled"):
        return 0
    base = cfg.get("points", {}).get(event, 0)
    points = int(round(base * multiplier))
    if points <= 0:
        return 0
    await db.referral_profiles.update_one(
        {"user_id": user_id},
        {"$inc": {"karma_balance": points}, "$setOnInsert": {"user_id": user_id, "cash_balance_inr": 0.0}},
        upsert=True,
    )
    await db.karma_ledger.insert_one({
        "ledger_id": f"karma_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "event": event,
        "points": points,
        "reason": reason or event.replace("_", " "),
        "ref": ref or {},
        "created_at": _now(),
    })
    return points


async def get_balance(user_id: str) -> int:
    p = await db.referral_profiles.find_one({"user_id": user_id}, {"_id": 0, "karma_balance": 1})
    return int((p or {}).get("karma_balance", 0) or 0)


async def get_rank(user_id: str) -> int:
    bal = await get_balance(user_id)
    higher = await db.referral_profiles.count_documents({"karma_balance": {"$gt": bal}})
    return higher + 1


async def spend_karma(user_id: str, points: int, *, reason: str, ref: Optional[dict] = None) -> bool:
    """Deduct karma if the user has enough. Returns True on success."""
    if points <= 0:
        return True
    bal = await get_balance(user_id)
    if bal < points:
        return False
    await db.referral_profiles.update_one({"user_id": user_id}, {"$inc": {"karma_balance": -points}})
    await db.karma_ledger.insert_one({
        "ledger_id": f"karma_{uuid.uuid4().hex[:12]}",
        "user_id": user_id, "event": "spend", "points": -points,
        "reason": reason, "ref": ref or {}, "created_at": _now(),
    })
    return True
