"""Iter 46 — Tests for:
ITEM 1: Store checkout math (GST + coupon), coupon validate, admin SKU update accepts gst_percent
ITEM 1.4: Decision-create consume_one path doesn't raise on user with no entitlement
ITEM 2: GET /api/store/my-entitlements rollup
ITEM 3: WhatsApp OTP send/verify/status (including dev_code echo, cooldown, wrong code, no-auth 401)
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


# ───────────────────────── helpers ─────────────────────────
def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["session_token"]


def _register_fresh() -> dict:
    email = f"iter46_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(
        f"{API}/auth/register",
        json={"email": email, "password": "TestPass2026!", "name": "Iter46 Tester"},
        timeout=20,
    )
    assert r.status_code in (200, 201), f"register: {r.status_code} {r.text}"
    body = r.json()
    return {"email": email, "token": body["session_token"], "user": body.get("user")}


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture
def fresh_user():
    return _register_fresh()


# ───────────────────────── ITEM 1: Store checkout math ─────────────────────────
class TestStoreCheckoutMath:
    def test_skus_have_gst_percent(self):
        r = requests.get(f"{API}/store/skus", timeout=20)
        assert r.status_code == 200
        data = r.json()
        skus = data.get("skus", [])
        assert len(skus) >= 4
        codes = [s["code"] for s in skus]
        for needed in ("L1", "L2", "L3", "L4"):
            assert needed in codes, f"Missing SKU {needed}"
        for s in skus:
            assert "gst_percent" in s, f"SKU {s['code']} missing gst_percent"

    def test_purchase_no_coupon_pricing_math(self, fresh_user):
        # Find L1
        r = requests.get(f"{API}/store/skus", timeout=20)
        l1 = next(s for s in r.json()["skus"] if s["code"] == "L1")
        base = int(l1["price_paise"])
        gst_pct = float(l1.get("gst_percent", 18))
        expected_gst = int(round(base * gst_pct / 100.0))
        expected_total = base + expected_gst

        r = requests.post(
            f"{API}/store/purchase",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            json={"sku_code": "L1"},
            timeout=30,
        )
        # Razorpay live key may legitimately error in non-prod; skip cleanly if so.
        if r.status_code in (500, 502):
            pytest.skip(f"Razorpay gateway error in this env: {r.text[:120]}")
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert "pricing" in body
        p = body["pricing"]
        assert p["base_paise"] == base
        assert p["discount_paise"] == 0
        assert p["taxable_paise"] == base
        assert p["gst_percent"] == gst_pct
        assert p["gst_paise"] == expected_gst
        assert p["total_paise"] == expected_total
        assert body["amount"] == expected_total

    def test_purchase_invalid_coupon_returns_400(self, fresh_user):
        r = requests.post(
            f"{API}/store/purchase",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            json={"sku_code": "L1", "coupon_code": "NOPE_INVALID_XYZ123"},
            timeout=30,
        )
        if r.status_code in (500, 502):
            pytest.skip(f"Razorpay gateway error in this env: {r.text[:120]}")
        assert r.status_code == 400, f"{r.status_code} {r.text}"


# ───────────────────────── Coupon validate ─────────────────────────
class TestCouponValidate:
    def test_invalid_coupon_returns_valid_false(self, fresh_user):
        r = requests.post(
            f"{API}/coupons/validate",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            json={"coupon_code": "DOES_NOT_EXIST_123", "list_price": 199, "flow": "STORE"},
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("valid") is False
        assert "net_payable_amount" in body
        assert "remarks" in body


# ───────────────────────── Admin SKU update accepts gst_percent ─────────────────────────
class TestAdminSkuGstUpdate:
    def test_admin_can_update_gst_percent(self, admin_token):
        # Update L1 GST to 12, then revert.
        r = requests.put(
            f"{API}/store/admin/skus/L1",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"gst_percent": 12},
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        # Verify persisted via GET
        r2 = requests.get(f"{API}/store/skus", timeout=20)
        l1 = next(s for s in r2.json()["skus"] if s["code"] == "L1")
        assert float(l1.get("gst_percent")) == 12

        # Revert
        revert = requests.put(
            f"{API}/store/admin/skus/L1",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"gst_percent": 18},
            timeout=20,
        )
        assert revert.status_code == 200


# ───────────────────────── ITEM 1.4 — Decision create with NO entitlement ─────────────────────────
class TestDecisionCreateNoEntitlement:
    def test_create_decision_no_entitlement_does_not_block(self, fresh_user):
        r = requests.post(
            f"{API}/decisions",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            json={"title": "TEST_no_entitlement", "context": "ctx"},
            timeout=20,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text}"
        body = r.json()
        assert "id" in body


# ───────────────────────── ITEM 2 — my-entitlements rollup ─────────────────────────
class TestMyEntitlements:
    def test_my_entitlements_shape(self, fresh_user):
        r = requests.get(
            f"{API}/store/my-entitlements",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert "entitlements" in body
        assert isinstance(body["entitlements"], list)
        # New user has none; structure still must be list
        for ent in body["entitlements"]:
            for k in ("sku_code", "balance", "granted_qty", "consumed_qty"):
                assert k in ent, f"Missing field {k} in entitlement: {ent}"


# ───────────────────────── ITEM 3 — WhatsApp OTP ─────────────────────────
class TestWhatsAppOtp:
    def test_send_otp_unauthenticated_401(self):
        r = requests.post(
            f"{API}/auth/whatsapp/send-otp",
            json={"phone_number": "+919876543210"},
            timeout=20,
        )
        assert r.status_code == 401, f"{r.status_code} {r.text}"

    def test_send_then_verify_flow(self, fresh_user):
        # Send OTP
        r = requests.post(
            f"{API}/auth/whatsapp/send-otp",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            json={"phone_number": "+919876543210"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("success") is True
        assert "dev_code" in body
        assert "cooldown_seconds" in body
        dev_code = body["dev_code"]
        assert isinstance(dev_code, str) and len(dev_code) == 6

        # Resend within cooldown -> 429
        r2 = requests.post(
            f"{API}/auth/whatsapp/send-otp",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            json={"phone_number": "+919876543210"},
            timeout=20,
        )
        assert r2.status_code == 429, f"expected 429, got {r2.status_code} {r2.text}"

        # Wrong code -> 400
        r3 = requests.post(
            f"{API}/auth/whatsapp/verify-otp",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            json={"code": "000000" if dev_code != "000000" else "111111"},
            timeout=20,
        )
        assert r3.status_code == 400, f"{r3.status_code} {r3.text}"

        # Correct code -> success
        r4 = requests.post(
            f"{API}/auth/whatsapp/verify-otp",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            json={"code": dev_code},
            timeout=20,
        )
        assert r4.status_code == 200, f"{r4.status_code} {r4.text}"
        v = r4.json()
        assert v.get("success") is True
        assert v.get("whatsapp_verified") is True

        # Status reflects verified
        r5 = requests.get(
            f"{API}/auth/whatsapp/status",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            timeout=20,
        )
        assert r5.status_code == 200, f"{r5.status_code} {r5.text}"
        s = r5.json()
        assert s.get("whatsapp_verified") is True
        assert s.get("whatsapp_number")

        # /api/auth/me returns whatsapp_verified True
        me = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {fresh_user['token']}"},
            timeout=20,
        )
        assert me.status_code == 200
        assert me.json().get("whatsapp_verified") is True
