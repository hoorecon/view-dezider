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
    "tokens_per_credit": 100.0,
    "confirm_threshold_credits": 15.0,  # ask the user to confirm AI actions estimated above this
    # ── Phase 3 — Razorpay refill / pricing ──
    "blended_usd_per_mtok": 2.0,       # blended Gemini list rate ($ per 1M tokens)
    "usd_to_inr_fallback": 90.0,       # used when live FX fetch fails
    "markup_admin_pct": 1.0,           # hidden markup for admin-role buyers
    "markup_user_pct": 13.0,           # hidden markup for regular users (covers RZP fee + ~10% net)
    # % of the markup that is routed via Razorpay Route to the linked account.
    # Default 77.0 → on a 13% markup, ~10% goes to linked, ~3% retained in primary
    # (treasury) to cover the ~2.36% RZP fee+GST and leave a tiny break-even buffer.
    "markup_routed_pct": 77.0,
    "route_linked_account_id": "acc_SyPciERWCkmA6R",  # Razorpay Route: markup → this linked account
    # Razorpay gateway fee + GST on the fee. Used by the admin "worked example"
    # break-even preview so the super-admin can see the real ₹ math live. The
    # backend doesn't deduct these itself — Razorpay does — but exposing them
    # as config lets ops keep the preview accurate if RZP renegotiates rates.
    "razorpay_fee_pct": 2.0,           # standard INR domestic-card rate
    "razorpay_gst_pct": 18.0,          # GST charged ON the RZP fee
    "min_custom_credits": 150.0,       # custom refill floor (keeps order >= ₹1)
    # ── "Costly & Precise AI" tier (Import-from-URL etc.) — Claude via the
    # Emergent universal key, paid from the common org balance. Credits are
    # charged at multiplier = precise_usd_per_mtok / blended_usd_per_mtok, so
    # the SAME refill-markup math stays zero-loss for this dearer provider.
    "precise_model": "claude-sonnet-4-6",
    "precise_usd_per_mtok": 9.0,
    # Import-from-URL: AI may auto-GROUP ungrouped factors into categories only
    # when the page defines no grouping AND the factor count exceeds this.
    "loader_music_volume_web": 0.55,
    "loader_music_volume_android": 0.75,
    "loader_music_volume_ios": 0.65,
    "import_group_threshold": 15,
    # ── Deep Import (Wave 2 #8b) — auto-assess & rank top options ──
    # `deep_import_max_options`: max options to FULLY assess per deep-import
    # job. Higher = more AI credits, more thorough rankings. User can pick a
    # smaller budget (≥2) inside this cap before the run.
    # `deep_import_top_n`: how many of the assessed options to surface in
    # Step 8 (Decision Comparison). Default 5.
    "deep_import_max_options": 10,
    "deep_import_top_n": 5,
    # ── ScraperAPI (web-scrape) metering — auto cost-derived per fetch ──
    # $/credit = plan_usd / plan_credits; each rendered fetch = 10 credits,
    # premium = 25. Charged to the user's wallet with `scrape_markup_pct` on top.
    "scraperapi_plan_usd_month": 299.0,        # ScraperAPI Business plan
    "scraperapi_plan_credits_month": 3000000.0,
    "scrape_markup_pct": 5.0,
    "credit_packs": [
        {"id": "starter", "name": "Starter", "credits": 5000, "badge": "Starter"},
        {"id": "pro", "name": "Pro", "credits": 20000, "badge": "Popular"},
        {"id": "power", "name": "Power", "credits": 50000, "badge": "Best value"},
    ],
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
    # positive-required numerics
    for k in ("default_user_credits", "default_admin_credits", "tokens_per_credit",
              "confirm_threshold_credits",
              "blended_usd_per_mtok", "usd_to_inr_fallback", "markup_admin_pct",
              "markup_user_pct", "markup_routed_pct",
              "razorpay_fee_pct", "razorpay_gst_pct",
              "min_custom_credits", "precise_usd_per_mtok", "import_group_threshold",
              "deep_import_max_options", "deep_import_top_n",
              "loader_music_volume_web", "loader_music_volume_android", "loader_music_volume_ios",
              "scraperapi_plan_usd_month", "scraperapi_plan_credits_month", "scrape_markup_pct"):
        if k in patch and patch[k] is not None:
            try:
                val = float(patch[k])
                if val < 0:
                    raise ValueError
                if k in ("tokens_per_credit", "blended_usd_per_mtok", "usd_to_inr_fallback",
                         "min_custom_credits", "precise_usd_per_mtok",
                         "scraperapi_plan_credits_month") and val <= 0:
                    raise ValueError
                if k == "import_group_threshold":
                    if val < 2:
                        raise ValueError
                    val = int(val)
                if k == "deep_import_max_options":
                    if val < 2 or val > 50:
                        raise ValueError
                    val = int(val)
                if k == "deep_import_top_n":
                    if val < 1 or val > 20:
                        raise ValueError
                    val = int(val)
                if k in ("loader_music_volume_web", "loader_music_volume_android", "loader_music_volume_ios"):
                    val = float(val)
                    if val < 0 or val > 1:
                        raise ValueError
                if k in ("markup_routed_pct", "razorpay_fee_pct", "razorpay_gst_pct") and val > 100.0:
                    raise ValueError
                allowed[k] = val
            except (ValueError, TypeError):
                raise ValueError(f"Invalid value for {k}")
    # Razorpay Route linked account id (string; empty disables Route)
    if "route_linked_account_id" in patch and patch["route_linked_account_id"] is not None:
        allowed["route_linked_account_id"] = str(patch["route_linked_account_id"]).strip()
    # Precise-tier Claude model name (string; falls back to default when blank)
    if "precise_model" in patch and patch["precise_model"] is not None:
        pm = str(patch["precise_model"]).strip()
        allowed["precise_model"] = pm or DEFAULTS["precise_model"]
    # credit packs (list of {id,name,credits,badge})
    if "credit_packs" in patch and isinstance(patch["credit_packs"], list):
        packs = []
        for p in patch["credit_packs"]:
            try:
                credits = int(float(p.get("credits")))
                if credits <= 0:
                    raise ValueError
                packs.append({
                    "id": str(p.get("id") or f"pack_{credits}"),
                    "name": str(p.get("name") or f"{credits} credits"),
                    "credits": credits,
                    "badge": str(p.get("badge") or ""),
                })
            except (ValueError, TypeError, AttributeError):
                raise ValueError("Invalid credit pack entry")
        allowed["credit_packs"] = packs
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
                  note: str = "", by: str = "", session_id: str = "") -> None:
    await db.ai_wallet_ledger.insert_one({
        "id": uuid.uuid4().hex, "user_id": user_id, "delta": round(delta, 4),
        "kind": kind, "tokens": int(tokens), "provider": provider, "feature": feature,
        "session_id": session_id or "",
        "balance_after": round(balance_after, 4), "note": note, "by": by,
        "created_at": _now(),
    })
    if kind == "debit":
        from core.posthog_client import track as ph_track
        ph_track(user_id, "ai_credits_consumed", {
            "credits": round(abs(delta), 4), "feature": feature,
            "provider": provider, "balance_after": round(balance_after, 4),
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


# Typical total (prompt + response) tokens per metered feature — calibrated from
# observed usage. Used ONLY to show a "~N credits" estimate / confirm before a
# spend; the real charge is always by actual tokens used.
FEATURE_TOKENS = {
    "eg_trap_analyze": 900,
    "eg_loop_recommend": 700,
    "eg_loop_reframe": 1000,
    "eg_limitation_classify": 700,
    "eg_limitation_reframe": 1000,
    "eg_outlet_analyze": 1400,
    "eg_aim_analyze": 1400,
    "eg_breakthrough_report": 2000,
    "ai_assess": 400,          # per cell (single ✨ assess)
    "ai_assess_batch": 1200,   # per ~40-cell batched chunk
}
DEFAULT_FEATURE_TOKENS = 900


async def estimates() -> Dict[str, Any]:
    """Per-feature estimated credit cost + the confirm threshold, for the
    frontend "~N cr" badges and the >threshold confirmation prompt."""
    cfg = await get_config()
    tpc = float(cfg["tokens_per_credit"])
    feats = {
        f: round(tokens_to_credits(tok, tpc), 2)
        for f, tok in FEATURE_TOKENS.items()
    }
    return {
        "tokens_per_credit": tpc,
        "confirm_threshold_credits": float(cfg.get("confirm_threshold_credits", 15.0)),
        "features": feats,
        "default_estimate": round(tokens_to_credits(DEFAULT_FEATURE_TOKENS, tpc), 2),
    }


def precise_multiplier(cfg: Dict[str, Any]) -> float:
    """Credit multiplier for the "Costly & Precise" (Claude) tier — the ratio
    of the Claude blended rate to the Gemini blended rate, floor 1×. Keeps the
    refill-markup zero-loss invariant intact for the dearer provider."""
    base = float(cfg.get("blended_usd_per_mtok") or DEFAULTS["blended_usd_per_mtok"])
    prec = float(cfg.get("precise_usd_per_mtok") or DEFAULTS["precise_usd_per_mtok"])
    return max(1.0, prec / max(0.01, base))


async def charge(user_id: str, *, tokens: int, feature: str = "", provider: str = "",
                 session_id: str = "", credit_multiplier: float = 1.0) -> Dict[str, Any]:
    """Deduct credits for `tokens` used. `credit_multiplier` > 1 is applied for
    premium providers (precise tier). Returns {charged, balance, tokens}."""
    cfg = await get_config()
    credits = tokens_to_credits(int(tokens or 0), float(cfg["tokens_per_credit"]))
    mult = max(1.0, float(credit_multiplier or 1.0))
    note = "AI usage"
    if mult > 1.0:
        credits = max(0.0001, math.ceil(credits * mult * 10000) / 10000)
        note = f"AI usage (precise ×{mult:.2f})"
    w = await _get_or_create(user_id)
    new_balance = round(float(w.get("balance", 0)) - credits, 4)
    await db.ai_wallets.update_one(
        {"user_id": user_id}, {"$set": {"balance": new_balance, "updated_at": _now()}},
    )
    await _ledger(user_id, -credits, "debit", balance_after=new_balance,
                  tokens=tokens, provider=provider, feature=feature, note=note,
                  session_id=session_id)
    return {"charged": credits, "balance": round(new_balance, 2), "tokens": int(tokens)}


async def session_cost(user_id: str, session_id: str) -> Dict[str, Any]:
    """Total AI credits a user has spent within a given session (for per-session
    cost display). Sums the debit ledger entries tagged with `session_id`."""
    if not session_id:
        return {"credits": 0.0, "calls": 0}
    cur = db.ai_wallet_ledger.find(
        {"user_id": user_id, "session_id": session_id, "kind": "debit"},
        {"_id": 0, "delta": 1},
    )
    rows = await cur.to_list(2000)
    return {"credits": round(sum(-float(r.get("delta", 0)) for r in rows), 4), "calls": len(rows)}


async def charge_credits(user_id: str, credits: float, *, feature: str = "",
                         note: str = "Feature usage") -> Dict[str, Any]:
    """Deduct a FLAT credit amount (not token-derived) — used by features that
    price by their own formula (e.g. the partner Screener). Returns
    {charged, balance}."""
    credits = max(0.0, round(float(credits or 0), 4))
    w = await _get_or_create(user_id)
    new_balance = round(float(w.get("balance", 0)) - credits, 4)
    await db.ai_wallets.update_one(
        {"user_id": user_id}, {"$set": {"balance": new_balance, "updated_at": _now()}},
    )
    await _ledger(user_id, -credits, "debit", balance_after=new_balance,
                  feature=feature, note=note)
    return {"charged": credits, "balance": round(new_balance, 2)}



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
