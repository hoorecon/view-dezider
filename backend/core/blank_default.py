"""Blank-cell default percentage — single source of truth.

When AI assessment cannot resolve a cell (status="error"), instead of leaving
the option's worth contribution at 0% we write a small DEFAULT percentage so
one missing cell doesn't silently torpedo an otherwise viable option.

Precedence (highest wins):
  1. decision.blank_default_pct       — per-decision override (Step 7 toggle)
  2. user_preferences.blank_default_pct — per-user profile preference
  3. DEFAULT_BLANK_PCT (5)            — global fallback

Set the value to 0 (decision/user) to fully opt OUT and keep the legacy
"empty cell" behaviour.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.database import db

log = logging.getLogger("blank_default")

DEFAULT_BLANK_PCT = 5
MIN_BLANK_PCT = 0
MAX_BLANK_PCT = 100


def _clamp(v: Any) -> Optional[int]:
    try:
        n = int(round(float(v)))
    except Exception:  # noqa: BLE001
        return None
    if n < MIN_BLANK_PCT or n > MAX_BLANK_PCT:
        return None
    return n


async def get_user_blank_default(user_id: str) -> int:
    """Profile-level default (user_preferences.blank_default_pct)."""
    if not user_id:
        return DEFAULT_BLANK_PCT
    doc = await db.user_preferences.find_one(
        {"user_id": user_id}, {"_id": 0, "blank_default_pct": 1}) or {}
    v = _clamp(doc.get("blank_default_pct"))
    return DEFAULT_BLANK_PCT if v is None else v


async def set_user_blank_default(user_id: str, pct: int) -> int:
    """Persist the user's profile-level default. Returns the stored value."""
    n = _clamp(pct)
    if n is None:
        raise ValueError("blank_default_pct must be an integer 0-100")
    await db.user_preferences.update_one(
        {"user_id": user_id},
        {"$set": {"blank_default_pct": n}},
        upsert=True,
    )
    log.info("user %s blank_default_pct set to %d", user_id, n)
    return n


def resolve_decision_blank_pct(decision: Dict[str, Any], user_blank_pct: int) -> int:
    """Effective default for a SPECIFIC decision (decision override > user > 5)."""
    v = _clamp((decision or {}).get("blank_default_pct"))
    if v is None:
        return user_blank_pct
    return v


async def effective_blank_pct(decision: Dict[str, Any], user_id: str) -> int:
    """Convenience: resolve the effective % in one call (use only when you
    don't already have the user pref cached for the request)."""
    return resolve_decision_blank_pct(decision, await get_user_blank_default(user_id))
