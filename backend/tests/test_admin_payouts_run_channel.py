"""
Tests for the new POST /api/admin/payouts/run channel selector behaviour.
Verifies channel enforcement (no silent fallback to manual when RazorpayX
is unconfigured) and validates the eligible-summary endpoint.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")

SUPER_ADMIN_EMAIL = "super@test.com"
SUPER_ADMIN_PASSWORD = "SuperPass2026!"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD
    }, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token")
    assert token, "No session_token in login response"
    # Add bearer token (some apps use header, some cookie). Both supported.
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --- Eligible summary -------------------------------------------------------
class TestEligibleSummary:
    def test_eligible_summary_shape(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/payouts/eligible-summary", timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        for k in ("eligible", "total_inr", "min_payout_inr", "razorpayx_active"):
            assert k in data, f"missing '{k}' in eligible-summary response: {data}"
        assert isinstance(data["eligible"], int)
        assert isinstance(data["total_inr"], int)
        assert isinstance(data["min_payout_inr"], int)
        assert isinstance(data["razorpayx_active"], bool)


# --- Run batch — manual_idfc ------------------------------------------------
class TestRunManualIdfc:
    def test_manual_idfc_returns_ok_with_counters(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/payouts/run",
                               json={"channel": "manual_idfc"}, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("channel") == "manual_idfc"
        # counters must be present even when zero (no eligible sellers in test env)
        for k in ("created", "bank", "upi", "skipped"):
            assert k in data, f"missing counter '{k}' in run response: {data}"
            assert isinstance(data[k], int), f"counter '{k}' must be int"


# --- Run batch — razorpayx (expected NOT configured) ------------------------
class TestRunRazorpayX:
    def test_razorpayx_aborts_with_400_when_not_configured(self, admin_session):
        # First, check if it's configured. If it is, skip (env-dependent).
        s = admin_session.get(f"{BASE_URL}/api/admin/payouts/eligible-summary", timeout=15).json()
        if s.get("razorpayx_active"):
            pytest.skip("RazorpayX is configured in this env — cannot test the abort path")
        r = admin_session.post(f"{BASE_URL}/api/admin/payouts/run",
                               json={"channel": "razorpayx"}, timeout=20)
        assert r.status_code == 400, f"Expected 400 hard-error, got {r.status_code}: {r.text}"
        body = r.json()
        msg = (body.get("detail") or "").lower()
        assert "razorpayx" in msg and ("not configured" in msg or "aborting" in msg), \
            f"Error message should mention RazorpayX not configured / aborting. Got: {body}"


# --- Run batch — invalid channel -------------------------------------------
class TestRunInvalidChannel:
    def test_empty_channel_returns_400(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/payouts/run",
                               json={"channel": ""}, timeout=15)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        body = r.json()
        msg = (body.get("detail") or "").lower()
        assert "channel" in msg, f"Expected channel validation error. Got: {body}"

    def test_unknown_channel_returns_400(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/payouts/run",
                               json={"channel": "stripe"}, timeout=15)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        body = r.json()
        msg = (body.get("detail") or "").lower()
        assert "channel" in msg
        # Per implementation, message should mention both options
        assert "razorpayx" in msg and "manual_idfc" in msg, f"Got: {body}"

    def test_missing_channel_field_returns_422_or_400(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/payouts/run",
                               json={}, timeout=15)
        # FastAPI/pydantic returns 422 when required field missing
        assert r.status_code in (400, 422), f"{r.status_code} {r.text}"


# --- Run batch — auth guard -------------------------------------------------
class TestRunRequiresAdmin:
    def test_unauth_returns_401_or_403(self):
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{BASE_URL}/api/admin/payouts/run",
                   json={"channel": "manual_idfc"}, timeout=15)
        assert r.status_code in (401, 403), f"{r.status_code} {r.text}"
