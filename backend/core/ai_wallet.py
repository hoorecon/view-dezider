"""Per-user AI credits wallet — metering + gating for AI features.

Users spend "AI credits" (an abstract unit) on metered AI features (AI Assist,
AI auto-fetch, AI subjective scoring). Credits are charged by ACTUAL token
usage: credits = tokens / tokens_per_credit. New users/admins are seeded with a
Super-Admin-configurable starting balance. When the balance hits 0, metered AI
is blocked until the wallet is refilled (Phase 3 = Razorpay).

Collections:
  ai_wallets        {user_id, balance, is_admin, created_at, updated_at}
  ai_wallet_ledger  {id, user_id, delta, kind, tokens, provider, feature,
                     balance_after, note, by, created_at}
  ai_wallet_config  {key:'singleton', default_user_credits, default_admin_credits,
                     tokens_per_credit, updated_at, updated_by}
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import db

log = logging.getLogger("ai_wallet")

CONFIG_KEY = "singleton"
DEFAULTS = {
    "default_user_credits": 20.0,
    "default_admin_credits": 200.0,
    "tokens_per_credit": 100.0,  # 100 tokens = 1 credit
}


class InsufficientCredits(Exception):
    """Raised when a user has no AI credits left for a metered call."""
    def __init__(self, balance: float):
        self.balance = balance
        super().__init__("Insufficient AI credits")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────── config ───────────────────────────
async def get_config() -> Dict[str, Any]:
    doc = await db.ai_wallet_config.find_one({"key": CONFIG_KEY}, {"_id": 0})
    if not doc:
        doc = {"key": CONFIG_KEY, **DEFAULTS, "updated_at": _now()}
        await db.ai_wallet_config.update_one({"key": CONFIG_KEY}, {"$set": doc}, upsert=True)
    # backfill any missing keys
    for k, v in DEFAULTS.items():
        doc.setdefault(k, v)
    return doc


async def update_config(patch: Dict[str, Any], by: str) -> Dict[str, Any]:
    allowed = {}
    for k in ("default_user_credits", "default_admin_credits", "tokens_per_credit"):
        if k in patch and patch[k] is not None:
            try:
                val = float(patch[k])
                if val < 0:
                    raise ValueError
                if k == "tokens_per_credit" and val <= 0:
                    raise ValueError
                allowed[k] = val
            except (ValueError, TypeError):
                raise ValueError(f"Invalid value for {k}")
    if not allowed:
        return await get_config()
    allowed["updated_at"] = _now()
    allowed["updated_by"] = by
    await db.ai_wallet_config.update_one({"key": CONFIG_KEY}, {"$set": {"key": CONFIG_KEY, **allowed}}, upsert=True)
    return await get_config()


# ─────────────────────────── wallet ───────────────────────────
async def _is_admin(user_id: str) -> bool:
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "role": 1})
    role = (u or {}).get("role", "user")
    return role in ("admin", "co_admin", "super_admin")


async def _get_or_create(user_id: str) -> Dict[str, Any]:
    w = await db.ai_wallets.find_one({"user_id": user_id}, {"_id": 0})
    if w:
        return w
    cfg = await get_config()
    is_admin = await _is_admin(user_id)
    start = float(cfg["default_admin_credits"] if is_admin else cfg["default_user_credits"])
    w = {"user_id": user_id, "balance": round(start, 4), "is_admin": is_admin,
         "created_at": _now(), "updated_at": _now()}
    await db.ai_wallets.update_one({"user_id": user_id}, {"$setOnInsert": w}, upsert=True)
    # ledger seed
    if start > 0:
        await _ledger(user_id, start, "seed", balance_after=start, note="Starting balance", by="system")
    fresh = await db.ai_wallets.find_one({"user_id": user_id}, {"_id": 0})
    return fresh or w


async def _ledger(user_id: str, delta: float, kind: str, *, balance_after: float,
                  tokens: int = 0, provider: str = "", feature: str = "",
                  note: str = "", by: str = "") -> None:
    await db.ai_wallet_ledger.insert_one({
        "id": uuid.uuid4().hex, "user_id": user_id, "delta": round(delta, 4),
        "kind": kind, "tokens": int(tokens), "provider": provider, "feature": feature,
        "balance_after": round(balance_after, 4), "note": note, "by": by,
        "created_at": _now(),
    })


async def get_balance(user_id: str) -> Dict[str, Any]:
    w = await _get_or_create(user_id)
    cfg = await get_config()
    return {
        "balance": round(float(w.get("balance", 0)), 2),
        "is_admin": bool(w.get("is_admin")),
        "unit": "credits",
        "tokens_per_credit": float(cfg["tokens_per_credit"]),
    }


async def ensure_can_spend(user_id: str) -> None:
    """Gate a metered call. Raises InsufficientCredits when balance <= 0."""
    w = await _get_or_create(user_id)
    if float(w.get("balance", 0)) <= 0:
        raise InsufficientCredits(float(w.get("balance", 0)))


def tokens_to_credits(tokens: int, tokens_per_credit: float) -> float:
    if tokens <= 0:
        return 0.0
    tpc = tokens_per_credit if tokens_per_credit and tokens_per_credit > 0 else DEFAULTS["tokens_per_credit"]
    credits = tokens / tpc
    # round UP to 4 decimals so tiny calls still cost something
    return max(0.0001, math.ceil(credits * 10000) / 10000)


async def charge(user_id: str, *, tokens: int, feature: str = "", provider: str = "") -> Dict[str, Any]:
    """Deduct credits for `tokens` used. Returns {charged, balance, tokens}."""
    cfg = await get_config()
    credits = tokens_to_credits(int(tokens or 0), float(cfg["tokens_per_credit"]))
    w = await _get_or_create(user_id)
    new_balance = round(float(w.get("balance", 0)) - credits, 4)
    await db.ai_wallets.update_one(
        {"user_id": user_id}, {"$set": {"balance": new_balance, "updated_at": _now()}},
    )
    await _ledger(user_id, -credits, "debit", balance_after=new_balance,
                  tokens=tokens, provider=provider, feature=feature, note="AI usage")
    return {"charged": credits, "balance": round(new_balance, 2), "tokens": int(tokens)}


async def grant(user_id: str, credits: float, *, by: str = "admin", note: str = "Manual grant",
                kind: str = "grant") -> Dict[str, Any]:
    """Add (or set, if kind='set') credits to a user's wallet."""
    w = await _get_or_create(user_id)
    if kind == "set":
        new_balance = round(float(credits), 4)
        delta = round(new_balance - float(w.get("balance", 0)), 4)
    else:
        delta = round(float(credits), 4)
        new_balance = round(float(w.get("balance", 0)) + delta, 4)
    await db.ai_wallets.update_one(
        {"user_id": user_id}, {"$set": {"balance": new_balance, "updated_at": _now()}},
    )
    await _ledger(user_id, delta, kind, balance_after=new_balance, note=note, by=by)
    return {"balance": round(new_balance, 2), "delta": delta}


async def get_ledger(user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    cur = db.ai_wallet_ledger.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cur.to_list(limit)
