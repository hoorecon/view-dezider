"""Per-user metering for ScraperAPI fetches (web-scrape cost recovery).

Every successful ScraperAPI fetch consumes ScraperAPI plan credits
(render=10, premium render=25). Those credits cost real money on the
company's ScraperAPI plan, so each successful fetch is charged to the END
USER's AI-credits wallet (auto cost-derived, zero-loss):

    usd_base    = scraper_credits × (plan_usd_month / plan_credits_month)
    usd_charged = usd_base × (1 + scrape_markup_pct/100)
    app_credits = usd_charged / usd_per_app_credit
      where usd_per_app_credit = blended_usd_per_mtok × tokens_per_credit / 1e6

Rows land in `scrape_usage` (recon + Import-Analytics aggregation) and the
standard ai_wallet ledger (visible in the user's wallet history). Failed
ScraperAPI requests are NOT charged (ScraperAPI doesn't bill them either).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from core.database import db
from core import ai_wallet

log = logging.getLogger("scrape_meter")

# ScraperAPI credit cost per request type (their published billing units).
SCRAPER_CREDITS = {"plain": 1, "render": 10, "premium_render": 25, "ultra_premium": 30}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _usd_per_app_credit(cfg: Dict[str, Any]) -> float:
    blended = float(cfg.get("blended_usd_per_mtok") or 2.0)
    tpc = float(cfg.get("tokens_per_credit") or 100.0)
    return max(1e-9, blended * tpc / 1_000_000.0)


async def ensure_can_scrape(user_id: str) -> None:
    """Gate a scrape-requiring fetch — raises ai_wallet.InsufficientCredits
    when the user's wallet balance is ≤ 0 (same policy as metered AI)."""
    await ai_wallet.ensure_can_spend(user_id)


async def charge_scrape(user_id: str, url: str, kind: str) -> Optional[Dict[str, Any]]:
    """Debit the user's wallet for one SUCCESSFUL ScraperAPI fetch and record
    a `scrape_usage` row. Never raises — a metering failure must not break an
    already-successful fetch (it is logged for recon follow-up)."""
    try:
        cfg = await ai_wallet.get_config()
        scraper_credits = SCRAPER_CREDITS.get(kind, SCRAPER_CREDITS["render"])
        plan_usd = float(cfg.get("scraperapi_plan_usd_month") or 0)
        plan_credits = float(cfg.get("scraperapi_plan_credits_month") or 1)
        markup = float(cfg.get("scrape_markup_pct") or 0)
        usd_base = scraper_credits * (plan_usd / max(1.0, plan_credits))
        usd_charged = usd_base * (1 + markup / 100.0)
        app_credits = round(usd_charged / _usd_per_app_credit(cfg), 4)

        host = urlparse(url).netloc[:120]
        if app_credits > 0:
            await ai_wallet.charge_credits(
                user_id, app_credits, feature="scrape_fetch",
                note=f"Web scrape ({kind.replace('_', ' ')}) — {host}")
        await db.scrape_usage.insert_one({
            "id": uuid.uuid4().hex, "user_id": user_id,
            "url": (url or "")[:500], "host": host, "kind": kind,
            "scraper_credits": scraper_credits,
            "usd_base_cost": round(usd_base, 8),
            "usd_cost": round(usd_charged, 8),
            "app_credits": app_credits,
            "created_at": _now(),
        })
        return {"scraper_credits": scraper_credits, "app_credits": app_credits}
    except Exception as e:  # noqa: BLE001 — metering must not break the fetch
        log.warning("scrape metering failed for user=%s url=%s: %s",
                    user_id, (url or "")[:80], str(e)[:160])
        return None
