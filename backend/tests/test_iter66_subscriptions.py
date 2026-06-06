"""Phase-4 Subscriptions (recurring monthly + one-time fallback) regression."""
import os
import time
import requests
import pytest

BASE_URL = "https://dashboard-rewire.preview.emergentagent.com"
API = f"{BASE_URL}/api"

SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PW = "Jelcos@Admin2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PW = "AdminPass2026!"

PLAN_BASIC = "plan_SyQQFEOgXDv1iD"
PLAN_PRO = "plan_SyQQoS2iyoiYgA"
PLAN_PREMIUM = "plan_SyQU7DMsIsdlqH"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"login {email} failed: {r.status_code} {r.text[:120]}")
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER_EMAIL, SUPER_PW)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PW)


@pytest.fixture(scope="module")
def user_token():
    """Fresh throwaway regular user."""
    email = f"sub_{int(time.time())}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "AutoPass2026!", "name": "Sub Tester"},
                      timeout=15)
    assert r.status_code in (200, 201), r.text
    return r.json()["session_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ───────────── /subscriptions/plans ─────────────
class TestPlans:
    def test_list_plans_returns_3_active(self, user_token):
        r = requests.get(f"{API}/subscriptions/plans", headers=H(user_token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        plans = body["plans"]
        assert len(plans) == 3
        tiers = {p["tier"]: p for p in plans}
        assert set(tiers) == {"basic", "pro", "premium"}
        assert tiers["basic"]["price_inr"] == 999
        assert tiers["pro"]["price_inr"] == 1999
        assert tiers["premium"]["price_inr"] == 3999
        assert tiers["basic"]["credits_per_month"] == 1500
        assert tiers["pro"]["credits_per_month"] == 4000
        assert tiers["premium"]["credits_per_month"] == 9000
        assert "recurring_available" in body
        assert body["currency"] == "INR"


# ───────────── /subscriptions/me ─────────────
class TestMe:
    def test_fresh_user_status_none(self, user_token):
        r = requests.get(f"{API}/subscriptions/me", headers=H(user_token), timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "none"
        assert body["current_plan"] in ("free", "none")
        assert body["subscription_id"] in (None, "")


# ───────────── /subscriptions/create ─────────────
class TestCreate:
    def test_recurring_or_onetime_fallback(self, user_token):
        r = requests.post(f"{API}/subscriptions/create", headers=H(user_token),
                          json={"plan_id": PLAN_BASIC}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mode"] in ("recurring", "onetime")
        if body["mode"] == "recurring":
            assert body["subscription_id"].startswith("sub_")
            assert "short_url" in body and body["short_url"]
            assert "key_id" in body
        else:
            assert body["order_id"].startswith("order_")
            assert body["amount"] == 99900  # basic = ₹999 = 99900 paise
            assert body.get("key_id")

    def test_invalid_plan_returns_400(self, user_token):
        r = requests.post(f"{API}/subscriptions/create", headers=H(user_token),
                          json={"plan_id": "plan_bogus_999"}, timeout=15)
        assert r.status_code == 400


# ───────────── /subscriptions/create-onetime ─────────────
class TestOnetime:
    def test_create_onetime_pro_returns_order(self, user_token):
        r = requests.post(f"{API}/subscriptions/create-onetime", headers=H(user_token),
                          json={"plan_id": PLAN_PRO}, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["mode"] == "onetime"
        assert body["order_id"].startswith("order_")
        assert body["amount"] == 199900  # ₹1999 * 100
        assert body.get("key_id")
        assert body["credits"] == 4000

    def test_verify_onetime_bogus_signature_400(self, user_token):
        # First create an order so we have a real order_id
        r = requests.post(f"{API}/subscriptions/create-onetime", headers=H(user_token),
                          json={"plan_id": PLAN_BASIC}, timeout=20)
        assert r.status_code == 200
        oid = r.json()["order_id"]
        r2 = requests.post(f"{API}/subscriptions/verify-onetime", headers=H(user_token),
                           json={"razorpay_order_id": oid,
                                 "razorpay_payment_id": "pay_fake_xxx",
                                 "razorpay_signature": "deadbeef" * 8}, timeout=15)
        assert r2.status_code == 400
        assert "signature" in r2.json().get("detail", "").lower() or "verification" in r2.json().get("detail", "").lower()

    def test_verify_missing_fields_400(self, user_token):
        r = requests.post(f"{API}/subscriptions/verify-onetime", headers=H(user_token),
                          json={"razorpay_order_id": "order_x"}, timeout=15)
        assert r.status_code == 400


# ───────────── /subscriptions/checkout (hosted HTML) ─────────────
class TestCheckoutHTML:
    def test_checkout_html_loads(self, user_token):
        r = requests.get(f"{API}/subscriptions/checkout",
                         params={"order_id": "order_test", "key_id": "rzp_live_xxx", "amount": 99900},
                         timeout=15)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert "checkout.razorpay.com" in r.text
        assert "order_test" in r.text
        assert "99900" in r.text


# ───────────── /subscriptions/cancel ─────────────
class TestCancel:
    def test_cancel_no_sub_graceful(self, user_token):
        r = requests.post(f"{API}/subscriptions/cancel", headers=H(user_token),
                          json={}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "message" in body


# ───────────── admin endpoints ─────────────
class TestAdmin:
    def test_non_super_admin_403(self, admin_token):
        # plain admin must NOT be able to PUT plan
        r = requests.put(f"{API}/admin/subscriptions/plans/{PLAN_BASIC}",
                         headers=H(admin_token), json={"credits_per_month": 1800}, timeout=15)
        assert r.status_code == 403

    def test_regular_user_403(self, user_token):
        r = requests.put(f"{API}/admin/subscriptions/plans/{PLAN_BASIC}",
                         headers=H(user_token), json={"credits_per_month": 1800}, timeout=15)
        assert r.status_code == 403

    def test_super_admin_update_plan_then_revert(self, super_token, user_token):
        # update credits to 1800
        r = requests.put(f"{API}/admin/subscriptions/plans/{PLAN_BASIC}",
                         headers=H(super_token),
                         json={"credits_per_month": 1800, "active": True}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["credits_per_month"] == 1800

        # GET /api/subscriptions/plans now reflects 1800
        rr = requests.get(f"{API}/subscriptions/plans", headers=H(user_token), timeout=15)
        assert rr.status_code == 200
        basic = next(p for p in rr.json()["plans"] if p["tier"] == "basic")
        assert basic["credits_per_month"] == 1800

        # revert to 1500
        rb = requests.put(f"{API}/admin/subscriptions/plans/{PLAN_BASIC}",
                          headers=H(super_token),
                          json={"credits_per_month": 1500, "active": True}, timeout=15)
        assert rb.status_code == 200
        assert rb.json()["credits_per_month"] == 1500

    def test_super_admin_sync(self, super_token):
        r = requests.post(f"{API}/admin/subscriptions/sync", headers=H(super_token),
                          json={}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "plans" in body
        assert "updated" in body
