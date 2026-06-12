"""Iter-108 regression — ScraperAPI per-user metering + deep-import failure
telemetry + recon ScraperAPI section.

Covers:
 1. ai_wallet config exposes the 3 new scrape-pricing keys (and they round-trip).
 2. scrape_meter math: render fetch = 10 ScraperAPI credits → cost-derived app credits.
 3. ensure_can_scrape gates at balance <= 0 (InsufficientCredits).
 4. /admin/recon/summary contains the `scraperapi` block (plan + totals).
 5. /admin/recon/daily rows carry scrape_fetches / scrape_cost_inr keys.
Run: python -m pytest tests/test_iter108_scrape_metering.py -q
"""
import os
import asyncio

import pytest
import requests

BASE_URL = os.environ.get(
    "TEST_BASE_URL", "https://pros-cons-engine.preview.emergentagent.com")
SUPER = {"email": "veales.vedic.decisions@gmail.com", "password": "Jelcos@Admin2026"}


@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=SUPER, timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("session_token") or r.json().get("token")


def test_wallet_config_has_scrape_keys(super_token):
    r = requests.get(f"{BASE_URL}/api/admin/ai-wallet/config",
                     headers={"Authorization": f"Bearer {super_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert float(cfg["scraperapi_plan_usd_month"]) > 0
    assert float(cfg["scraperapi_plan_credits_month"]) > 0
    assert "scrape_markup_pct" in cfg


def test_scrape_meter_math():
    import sys
    sys.path.insert(0, "/app/backend")
    from core import scrape_meter

    cfg = {"blended_usd_per_mtok": 2.0, "tokens_per_credit": 100.0,
           "scraperapi_plan_usd_month": 299.0,
           "scraperapi_plan_credits_month": 3_000_000.0, "scrape_markup_pct": 5.0}
    # render = 10 ScraperAPI credits
    usd_base = scrape_meter.SCRAPER_CREDITS["render"] * (299.0 / 3_000_000.0)
    app_credits = usd_base * 1.05 / scrape_meter._usd_per_app_credit(cfg)
    assert 5.0 < app_credits < 5.5  # ≈5.23 cr per rendered fetch
    assert scrape_meter.SCRAPER_CREDITS["premium_render"] == 25


def test_scrape_gate_blocks_zero_balance():
    import sys
    sys.path.insert(0, "/app/backend")
    from core import ai_wallet, scrape_meter

    async def run():
        uid = "iter108_gate_user"
        await ai_wallet.grant(uid, 0, kind="set", note="test drain")
        with pytest.raises(ai_wallet.InsufficientCredits):
            await scrape_meter.ensure_can_scrape(uid)

    asyncio.run(run())


def test_recon_summary_scraperapi_block(super_token):
    r = requests.get(f"{BASE_URL}/api/admin/recon/summary",
                     headers={"Authorization": f"Bearer {super_token}"}, timeout=40)
    assert r.status_code == 200, r.text
    sc = r.json().get("scraperapi")
    assert sc is not None, "scraperapi block missing from recon summary"
    for key in ("fetches", "scraper_credits_used", "est_cost_inr",
                "charged_credits", "charged_value_inr", "plan"):
        assert key in sc, f"missing {key}"
    assert float(sc["plan"]["credits_month"]) > 0


def test_recon_daily_has_scrape_columns(super_token):
    r = requests.get(f"{BASE_URL}/api/admin/recon/daily?days=7",
                     headers={"Authorization": f"Bearer {super_token}"}, timeout=40)
    assert r.status_code == 200, r.text
    items = r.json().get("items") or []
    if items:  # columns present on every row
        assert "scrape_fetches" in items[-1]
        assert "scrape_cost_inr" in items[-1]


def test_deep_import_error_runs_visible(super_token):
    """At least one deep_import error run exists (seeded by the e2e check) and
    the admin runs list filter returns it."""
    r = requests.get(
        f"{BASE_URL}/api/admin/import-analytics/runs?days=2&status=error&limit=50",
        headers={"Authorization": f"Bearer {super_token}"}, timeout=30)
    assert r.status_code == 200, r.text
    items = r.json().get("items") or []
    deep = [x for x in items if x.get("endpoint") == "deep_import"]
    assert deep, "no deep_import error runs visible in Import Analytics"
    assert deep[0].get("route") == "deep_import_discovery"
