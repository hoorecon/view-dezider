"""AI-credits refill pricing — Gemini-cost-pegged packs with hidden markup.

Price model (per the product spec):
    cost_usd  = credits * tokens_per_credit * blended_usd_per_mtok / 1_000_000
    markup%   = markup_admin_pct (admin buyers) | markup_user_pct (everyone else)
    total_usd = cost_usd * (1 + markup%/100)
    -> convert to INR with a LIVE USD→INR rate (fallback = configurable).

Razorpay Route: the *markup* portion is transferred to a separate linked
account; the *cost* portion stays in the primary account (the company's
Gemini-funding treasury). Gemini itself is paid separately on Google Cloud —
no payment gateway can pay Google directly.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Tuple

import httpx

log = logging.getLogger("ai_billing")

# In-process FX cache: (rate, fetched_at_epoch)
_FX_CACHE: Dict[str, Tuple[float, float]] = {}
_FX_TTL = 3600  # 1 hour
RAZORPAY_MIN_PAISE = 100      # ₹1.00 minimum order
ROUTE_MIN_TRANSFER_PAISE = 100  # don't route sub-₹1 markups


async def get_usd_to_inr(fallback: float) -> Tuple[float, str]:
    """Return (rate, source). Live fetch with 1h cache; falls back on any error."""
    now = time.time()
    cached = _FX_CACHE.get("USDINR")
    if cached and (now - cached[1]) < _FX_TTL:
        return cached[0], "cache"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get("https://open.er-api.com/v6/latest/USD")
            data = resp.json()
            rate = float((data.get("rates") or {}).get("INR"))
            if rate and rate > 0:
                _FX_CACHE["USDINR"] = (rate, now)
                return rate, "live"
    except Exception as e:
        log.warning(f"USD→INR live fetch failed, using fallback: {str(e)[:120]}")
    return float(fallback), "fallback"


def _markup_pct(cfg: Dict[str, Any], is_admin: bool) -> float:
    return float(cfg.get("markup_admin_pct" if is_admin else "markup_user_pct", 0.0))


def _routed_pct(cfg: Dict[str, Any]) -> float:
    """Fraction (0-100) of the markup that goes to the Razorpay Route linked
    account. The rest stays in the primary (treasury) account to cover the
    Razorpay gateway fee + GST and leave a tiny break-even buffer."""
    try:
        v = float(cfg.get("markup_routed_pct", 77.0))
    except (TypeError, ValueError):
        v = 77.0
    return max(0.0, min(100.0, v))


def price_for_credits(credits: int, is_admin: bool, cfg: Dict[str, Any], fx: float) -> Dict[str, Any]:
    """Compute the full price breakdown for `credits` at the current config + FX."""
    credits = int(credits)
    tpc = float(cfg.get("tokens_per_credit", 100.0)) or 100.0
    blended = float(cfg.get("blended_usd_per_mtok", 2.0)) or 2.0
    markup_pct = _markup_pct(cfg, is_admin)
    routed_pct = _routed_pct(cfg)

    cost_usd = credits * tpc * blended / 1_000_000.0
    total_usd = cost_usd * (1.0 + markup_pct / 100.0)
    cost_inr = cost_usd * fx
    total_inr = total_usd * fx
    markup_inr = total_inr - cost_inr

    total_paise = int(round(total_inr * 100))
    markup_paise = int(round(markup_inr * 100))
    cost_paise = max(0, total_paise - markup_paise)
    routed_paise = int(round(markup_paise * routed_pct / 100.0))
    retained_paise = max(0, markup_paise - routed_paise)

    return {
        "credits": credits,
        "tokens_per_credit": tpc,
        "blended_usd_per_mtok": blended,
        "markup_pct": markup_pct,
        "markup_routed_pct": routed_pct,
        "fx_usd_inr": round(fx, 4),
        "cost_usd": round(cost_usd, 6),
        "total_usd": round(total_usd, 6),
        "cost_inr": round(cost_inr, 2),
        "markup_inr": round(markup_inr, 2),
        "total_inr": round(total_inr, 2),
        "total_paise": total_paise,
        "cost_paise": cost_paise,
        "markup_paise": markup_paise,
        "routed_paise": routed_paise,
        "retained_markup_paise": retained_paise,
        "routed_inr": round(routed_paise / 100.0, 2),
        "retained_markup_inr": round(retained_paise / 100.0, 2),
        "below_min": total_paise < RAZORPAY_MIN_PAISE,
        "min_inr": RAZORPAY_MIN_PAISE / 100.0,
    }


def packs_priced(cfg: Dict[str, Any], is_admin: bool, fx: float) -> list:
    """Return configured packs with computed prices for this buyer."""
    out = []
    for p in cfg.get("credit_packs", []):
        try:
            credits = int(p.get("credits"))
        except (TypeError, ValueError):
            continue
        pr = price_for_credits(credits, is_admin, cfg, fx)
        out.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "badge": p.get("badge", ""),
            "credits": credits,
            "price_inr": pr["total_inr"],
            "price_paise": pr["total_paise"],
            "breakdown": pr,
        })
    return out
