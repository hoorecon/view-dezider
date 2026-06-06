"""Iteration 65 — Phase 3: AI Credits Razorpay refill.

Covers /api/ai-wallet/packs, /refill/quote, /refill/order (with route fallback),
/refill/verify (bad signature -> 400), /refill/checkout (Razorpay HTML),
PUT /api/admin/ai-wallet/config (super-admin only), and config -> packs reflect.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://dashboard-rewire.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PASS = "Jelcos@Admin2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


# ─────────────── fixtures ───────────────
@pytest.fixture(scope="module")
def super_token():
    r = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS}, timeout=15)
    assert r.status_code == 200, f"super login failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def user_token():
    # Register a fresh throwaway user (regular role)
    email = f"refill_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "TestPass2026!", "name": "Refill Tester"},
                      timeout=15)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    return r.json()["session_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ─────────────── reset config to defaults first ───────────────
@pytest.fixture(scope="module", autouse=True)
def reset_defaults(super_token):
    defaults = {
        "markup_user_pct": 10.0,
        "markup_admin_pct": 1.0,
        "blended_usd_per_mtok": 2.0,
        "usd_to_inr_fallback": 90.0,
        "min_custom_credits": 150.0,
        "tokens_per_credit": 100.0,
        "route_linked_account_id": "acc_SyPciERWCkmA6R",
        "credit_packs": [
            {"id": "starter", "name": "Starter", "credits": 5000, "badge": "Starter"},
            {"id": "pro", "name": "Pro", "credits": 20000, "badge": "Popular"},
            {"id": "power", "name": "Power", "credits": 50000, "badge": "Best value"},
        ],
    }
    r = requests.put(f"{API}/admin/ai-wallet/config", json=defaults, headers=H(super_token), timeout=15)
    assert r.status_code == 200, r.text
    yield
    # restore at end as well (markup_user_pct=10 specifically)
    requests.put(f"{API}/admin/ai-wallet/config", json={"markup_user_pct": 10.0}, headers=H(super_token), timeout=15)


# ─────────────── /ai-wallet/packs ───────────────
class TestPacks:
    def test_user_sees_three_packs_inr(self, user_token):
        r = requests.get(f"{API}/ai-wallet/packs", headers=H(user_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["currency"] == "INR"
        assert d["markup_pct"] == 10.0
        assert d["min_custom_credits"] == 150
        assert d["fx_source"] in ("live", "cache", "fallback")
        assert d["fx_usd_inr"] > 0
        packs = d["packs"]
        ids = sorted([p["id"] for p in packs])
        assert ids == ["power", "pro", "starter"]
        # Each pack must expose price_inr and credits
        by_id = {p["id"]: p for p in packs}
        assert by_id["starter"]["credits"] == 5000
        assert by_id["pro"]["credits"] == 20000
        assert by_id["power"]["credits"] == 50000
        for p in packs:
            assert p["price_inr"] > 0
            assert p["price_paise"] == int(round(p["price_inr"] * 100))
        # Sanity: starter ≈ 5000*100*2/1e6 * 1.10 * fx ≈ 1.1 * fx ≈ ~99 at fx=90
        fx = d["fx_usd_inr"]
        expected_starter = round(5000 * 100 * 2 / 1_000_000 * 1.10 * fx, 2)
        assert abs(by_id["starter"]["price_inr"] - expected_starter) < 0.5

    def test_admin_buyer_gets_1pct_markup(self, admin_token):
        r = requests.get(f"{API}/ai-wallet/packs", headers=H(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["is_admin"] is True
        assert d["markup_pct"] == 1.0


# ─────────────── /ai-wallet/refill/quote ───────────────
class TestQuote:
    def test_quote_1000_credits_breakdown(self, user_token):
        r = requests.post(f"{API}/ai-wallet/refill/quote",
                          json={"credits": 1000}, headers=H(user_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("credits", "cost_inr", "markup_inr", "total_inr", "total_paise", "below_min", "markup_pct"):
            assert k in d, f"missing {k}"
        assert d["credits"] == 1000
        assert d["below_min"] is False
        assert d["markup_pct"] == 10.0
        # Cost + markup = total (within paise rounding)
        assert abs((d["cost_inr"] + d["markup_inr"]) - d["total_inr"]) < 0.05
        assert d["total_paise"] == int(round(d["total_inr"] * 100))

    def test_quote_below_min_returns_400(self, user_token):
        r = requests.post(f"{API}/ai-wallet/refill/quote",
                          json={"credits": 10}, headers=H(user_token), timeout=15)
        assert r.status_code == 400, r.text
        assert "150" in r.text or "min" in r.text.lower()

    def test_quote_pack_pro(self, user_token):
        r = requests.post(f"{API}/ai-wallet/refill/quote",
                          json={"pack_id": "pro"}, headers=H(user_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["credits"] == 20000
        assert d["below_min"] is False

    def test_quote_invalid_pack(self, user_token):
        r = requests.post(f"{API}/ai-wallet/refill/quote",
                          json={"pack_id": "bogus"}, headers=H(user_token), timeout=15)
        assert r.status_code == 400


# ─────────────── /ai-wallet/refill/order ───────────────
class TestOrder:
    def test_order_starter_creates_razorpay_order(self, user_token):
        r = requests.post(f"{API}/ai-wallet/refill/order",
                          json={"pack_id": "starter"}, headers=H(user_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["order_id"].startswith("order_"), d
        assert d["credits"] == 5000
        assert d["currency"] == "INR"
        assert d["amount"] == d["breakdown"]["total_paise"]
        assert d["key_id"]  # razorpay key id present
        # route_applied is bool — true if route enabled on this account, false if fallback
        assert isinstance(d["route_applied"], bool)
        # If linked account exists in config, route should be attempted; either it
        # succeeded (true) or gracefully fell back to false. Either is acceptable.

    def test_order_custom_credits(self, user_token):
        r = requests.post(f"{API}/ai-wallet/refill/order",
                          json={"credits": 200}, headers=H(user_token), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["credits"] == 200

    def test_order_below_min_400(self, user_token):
        r = requests.post(f"{API}/ai-wallet/refill/order",
                          json={"credits": 5}, headers=H(user_token), timeout=15)
        assert r.status_code == 400


# ─────────────── /ai-wallet/refill/verify ───────────────
class TestVerify:
    def test_bogus_signature_400(self, user_token):
        # Create a real order first so order exists
        o = requests.post(f"{API}/ai-wallet/refill/order",
                          json={"pack_id": "starter"}, headers=H(user_token), timeout=20).json()
        r = requests.post(f"{API}/ai-wallet/refill/verify", json={
            "razorpay_order_id": o["order_id"],
            "razorpay_payment_id": "pay_bogus_xyz",
            "razorpay_signature": "deadbeef" * 8,
        }, headers=H(user_token), timeout=15)
        assert r.status_code == 400, r.text
        assert "signature" in r.text.lower() or "verification" in r.text.lower()

    def test_missing_fields_400(self, user_token):
        r = requests.post(f"{API}/ai-wallet/refill/verify", json={}, headers=H(user_token), timeout=15)
        assert r.status_code == 400


# ─────────────── /ai-wallet/refill/checkout ───────────────
class TestCheckout:
    def test_checkout_html_includes_razorpay(self):
        # No auth required — page loads via web browser
        r = requests.get(f"{API}/ai-wallet/refill/checkout",
                         params={"order_id": "order_test", "key_id": "rzp_test_x", "amount": 9900},
                         timeout=15)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert "checkout.razorpay.com" in r.text
        assert "order_test" in r.text
        assert "9900" in r.text


# ─────────────── Admin config gating ───────────────
class TestAdminConfig:
    def test_user_blocked_403(self, user_token):
        r = requests.put(f"{API}/admin/ai-wallet/config",
                         json={"markup_user_pct": 15.0}, headers=H(user_token), timeout=15)
        assert r.status_code == 403, r.text

    def test_admin_role_blocked_403(self, admin_token):
        # admin (not super) must NOT be able to update wallet config
        r = requests.put(f"{API}/admin/ai-wallet/config",
                         json={"markup_user_pct": 15.0}, headers=H(admin_token), timeout=15)
        assert r.status_code == 403, r.text

    def test_super_admin_updates_and_packs_reflect(self, super_token, user_token):
        # Bump markup_user_pct to 20 and verify packs price for a regular user reflects it
        r = requests.put(f"{API}/admin/ai-wallet/config",
                         json={"markup_user_pct": 20.0}, headers=H(super_token), timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["markup_user_pct"] == 20.0

        p = requests.get(f"{API}/ai-wallet/packs", headers=H(user_token), timeout=15).json()
        assert p["markup_pct"] == 20.0
        # Starter price should now be cost * 1.20 (not 1.10)
        fx = p["fx_usd_inr"]
        starter = next(x for x in p["packs"] if x["id"] == "starter")
        expected = round(5000 * 100 * 2 / 1_000_000 * 1.20 * fx, 2)
        assert abs(starter["price_inr"] - expected) < 0.5

        # Revert
        rv = requests.put(f"{API}/admin/ai-wallet/config",
                          json={"markup_user_pct": 10.0}, headers=H(super_token), timeout=15)
        assert rv.status_code == 200
        assert rv.json()["markup_user_pct"] == 10.0

    def test_super_admin_updates_packs_and_route(self, super_token, user_token):
        new_packs = [
            {"id": "starter", "name": "Starter", "credits": 5000, "badge": "Starter"},
            {"id": "pro", "name": "Pro", "credits": 20000, "badge": "Popular"},
            {"id": "power", "name": "Power", "credits": 50000, "badge": "Best value"},
        ]
        body = {
            "credit_packs": new_packs,
            "route_linked_account_id": "acc_SyPciERWCkmA6R",
            "min_custom_credits": 150.0,
            "blended_usd_per_mtok": 2.0,
            "usd_to_inr_fallback": 90.0,
        }
        r = requests.put(f"{API}/admin/ai-wallet/config", json=body, headers=H(super_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["route_linked_account_id"] == "acc_SyPciERWCkmA6R"
        assert len(d["credit_packs"]) == 3
        # Confirm packs endpoint still returns the 3 packs
        p = requests.get(f"{API}/ai-wallet/packs", headers=H(user_token), timeout=15).json()
        assert len(p["packs"]) == 3
