"""
Iter 53 — Admin Quota Editor + Decision-clone consumption fix
Tests for /api/admin/quota/* endpoints and clone path consumption.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL not set"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PASS = "Jelcos@Admin2026"
# Alternate super-admin that owns the WhatsApp number used as OTP recipient
SUPER2_EMAIL = "super@test.com"
SUPER2_PASS_CANDIDATES = ["SuperPass2026!", "AdminPass2026!", "Jelcos@Admin2026"]

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"

USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"

TARGET_EMAIL = "ad.shezhiyanraj@gmail.com"
TARGET_MOBILE = "919999900000"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        return None
    j = r.json()
    return j.get("access_token") or j.get("token") or j.get("session_token")


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def super_token():
    tok = _login(SUPER_EMAIL, SUPER_PASS)
    if not tok:
        pytest.skip("super admin login failed")
    return tok


@pytest.fixture(scope="module")
def admin_token():
    tok = _login(ADMIN_EMAIL, ADMIN_PASS)
    if not tok:
        pytest.skip("admin login failed")
    return tok


@pytest.fixture(scope="module")
def user_token():
    tok = _login(USER_EMAIL, USER_PASS)
    if not tok:
        pytest.skip("user login failed")
    return tok


# ─────────────────────── 1. permission endpoint ───────────────────────
class TestPermission:
    def test_super_admin_can_edit(self, super_token):
        r = requests.get(f"{API}/admin/quota/permission", headers=_hdr(super_token))
        assert r.status_code == 200, r.text
        assert r.json()["can_edit_quota"] is True

    def test_admin_initially_cannot(self, admin_token, super_token):
        # First make sure admin starts ungranted (revoke)
        requests.post(f"{API}/admin/quota/grant",
                      headers=_hdr(super_token),
                      json={"email": ADMIN_EMAIL, "grant": False})
        r = requests.get(f"{API}/admin/quota/permission", headers=_hdr(admin_token))
        assert r.status_code == 200
        assert r.json()["can_edit_quota"] is False

    def test_user_cannot(self, user_token):
        r = requests.get(f"{API}/admin/quota/permission", headers=_hdr(user_token))
        assert r.status_code == 200
        assert r.json()["can_edit_quota"] is False


# ─────────────────────── 2. grant flow ───────────────────────
class TestGrant:
    def test_admin_cannot_grant(self, admin_token):
        r = requests.post(f"{API}/admin/quota/grant",
                          headers=_hdr(admin_token),
                          json={"email": ADMIN_EMAIL, "grant": True})
        assert r.status_code == 403

    def test_super_can_grant(self, super_token, admin_token):
        r = requests.post(f"{API}/admin/quota/grant",
                          headers=_hdr(super_token),
                          json={"email": ADMIN_EMAIL, "grant": True})
        assert r.status_code == 200, r.text
        assert r.json()["can_edit_quota"] is True
        # admin should now see can_edit_quota=true
        r2 = requests.get(f"{API}/admin/quota/permission", headers=_hdr(admin_token))
        assert r2.status_code == 200
        assert r2.json()["can_edit_quota"] is True

    def test_grant_404_unknown(self, super_token):
        r = requests.post(f"{API}/admin/quota/grant",
                          headers=_hdr(super_token),
                          json={"email": "nonexistent_abc_xyz_999@example.com", "grant": True})
        assert r.status_code == 404


# ─────────────────────── 3. lookup ───────────────────────
class TestLookup:
    def test_lookup_happy(self, super_token):
        r = requests.post(f"{API}/admin/quota/lookup",
                          headers=_hdr(super_token),
                          json={"email": TARGET_EMAIL, "mobile": TARGET_MOBILE})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "user" in body and "skus" in body
        assert body["user"]["email"].lower() == TARGET_EMAIL.lower()
        # Find L1 sku row
        l1 = next((s for s in body["skus"] if s["sku_code"] == "L1"), None)
        assert l1, f"L1 not in skus: {body['skus']}"
        # Record current state for later cleanup if needed
        pytest.l1_balance = l1["balance"]
        pytest.l1_consumed = l1["consumed"]
        pytest.target_user_id = body["user"]["user_id"]
        # The seed says balance=1000000, consumed=3, but allow non-strict
        assert l1["balance"] >= 0
        assert l1["consumed"] >= 0

    def test_lookup_mismatched_mobile(self, super_token):
        r = requests.post(f"{API}/admin/quota/lookup",
                          headers=_hdr(super_token),
                          json={"email": TARGET_EMAIL, "mobile": "910000000000"})
        assert r.status_code == 404

    def test_lookup_email_not_found(self, super_token):
        r = requests.post(f"{API}/admin/quota/lookup",
                          headers=_hdr(super_token),
                          json={"email": "nobody_xxx_404@example.com", "mobile": TARGET_MOBILE})
        assert r.status_code == 404

    def test_lookup_blocked_for_user(self, user_token):
        r = requests.post(f"{API}/admin/quota/lookup",
                          headers=_hdr(user_token),
                          json={"email": TARGET_EMAIL, "mobile": TARGET_MOBILE})
        assert r.status_code == 403


# ─────────────────────── 4. OTP request ───────────────────────
class TestOtp:
    def test_request_otp(self, super_token):
        # Need target_user_id from previous lookup
        if not hasattr(pytest, "target_user_id"):
            r0 = requests.post(f"{API}/admin/quota/lookup",
                               headers=_hdr(super_token),
                               json={"email": TARGET_EMAIL, "mobile": TARGET_MOBILE})
            assert r0.status_code == 200
            pytest.target_user_id = r0.json()["user"]["user_id"]

        r = requests.post(f"{API}/admin/quota/request-otp",
                          headers=_hdr(super_token),
                          json={"target_user_id": pytest.target_user_id})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("otp_required") is True
        assert body.get("sent_to_masked")
        # WA_OTP_EXPOSE_DEV_CODE=true should expose code
        assert "dev_code" in body, f"dev_code missing — body: {body}"
        pytest.dev_code = body["dev_code"]

    def test_request_otp_blocked_for_user(self, user_token, super_token):
        if not hasattr(pytest, "target_user_id"):
            r0 = requests.post(f"{API}/admin/quota/lookup",
                               headers=_hdr(super_token),
                               json={"email": TARGET_EMAIL, "mobile": TARGET_MOBILE})
            pytest.target_user_id = r0.json()["user"]["user_id"]
        r = requests.post(f"{API}/admin/quota/request-otp",
                          headers=_hdr(user_token),
                          json={"target_user_id": pytest.target_user_id})
        assert r.status_code == 403


# ─────────────────────── 5. apply happy path + security ───────────────────────
class TestApply:
    def _ensure(self, super_token):
        if not hasattr(pytest, "target_user_id"):
            r0 = requests.post(f"{API}/admin/quota/lookup",
                               headers=_hdr(super_token),
                               json={"email": TARGET_EMAIL, "mobile": TARGET_MOBILE})
            pytest.target_user_id = r0.json()["user"]["user_id"]
            l1 = next(s for s in r0.json()["skus"] if s["sku_code"] == "L1")
            pytest.l1_consumed = l1["consumed"]

    def test_apply_negative_new_left(self, super_token):
        self._ensure(super_token)
        r = requests.post(f"{API}/admin/quota/apply",
                          headers=_hdr(super_token),
                          json={"target_user_id": pytest.target_user_id, "sku_code": "L1",
                                "new_left": -5, "reason": "neg test", "otp": "123456"})
        assert r.status_code == 422

    def test_apply_without_otp_request(self, admin_token, super_token):
        # admin had OTP requested? No, only super. Make sure no OTP exists for admin actor.
        self._ensure(super_token)
        # Try apply as admin (who has grant) without calling request-otp first as admin.
        r = requests.post(f"{API}/admin/quota/apply",
                          headers=_hdr(admin_token),
                          json={"target_user_id": pytest.target_user_id, "sku_code": "L1",
                                "new_left": 5, "reason": "no otp test", "otp": "000000"})
        # Should be 400 'Request an authorization OTP first.' (admin has perm now)
        assert r.status_code == 400, r.text

    def test_apply_wrong_otp(self, super_token):
        self._ensure(super_token)
        # Re-request OTP
        r0 = requests.post(f"{API}/admin/quota/request-otp",
                           headers=_hdr(super_token),
                           json={"target_user_id": pytest.target_user_id})
        assert r0.status_code == 200
        pytest.dev_code = r0.json()["dev_code"]

        r = requests.post(f"{API}/admin/quota/apply",
                          headers=_hdr(super_token),
                          json={"target_user_id": pytest.target_user_id, "sku_code": "L1",
                                "new_left": 5, "reason": "wrong otp test", "otp": "000000"})
        assert r.status_code == 401

    def test_apply_as_user_forbidden(self, user_token):
        r = requests.post(f"{API}/admin/quota/apply",
                          headers=_hdr(user_token),
                          json={"target_user_id": pytest.target_user_id, "sku_code": "L1",
                                "new_left": 5, "reason": "user denied", "otp": "123456"})
        assert r.status_code == 403

    def test_apply_happy(self, super_token):
        self._ensure(super_token)
        # Re-request OTP fresh (previous test consumed an attempt but didn't delete)
        r0 = requests.post(f"{API}/admin/quota/request-otp",
                           headers=_hdr(super_token),
                           json={"target_user_id": pytest.target_user_id})
        assert r0.status_code == 200
        code = r0.json()["dev_code"]

        r = requests.post(f"{API}/admin/quota/apply",
                          headers=_hdr(super_token),
                          json={"target_user_id": pytest.target_user_id, "sku_code": "L1",
                                "new_left": 5, "reason": "Corrected accidental over-allocation",
                                "otp": code})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["new_left"] == 5
        # response.skus should reflect new L1 row
        l1 = next(s for s in body["skus"] if s["sku_code"] == "L1")
        assert l1["balance"] == 5
        # granted = consumed + new_left
        assert l1["granted"] == l1["consumed"] + 5

    def test_apply_persisted_via_relookup(self, super_token):
        r = requests.post(f"{API}/admin/quota/lookup",
                          headers=_hdr(super_token),
                          json={"email": TARGET_EMAIL, "mobile": TARGET_MOBILE})
        assert r.status_code == 200
        l1 = next(s for s in r.json()["skus"] if s["sku_code"] == "L1")
        assert l1["balance"] == 5, f"persisted balance != 5: {l1}"

    def test_audit_log_has_entry(self, super_token):
        r = requests.get(f"{API}/admin/quota/log", headers=_hdr(super_token))
        assert r.status_code == 200
        logs = r.json().get("logs") or []
        assert any(
            (lg.get("target_email") or "").lower() == TARGET_EMAIL.lower() and lg.get("sku_code") == "L1" and lg.get("new_left") == 5
            for lg in logs
        ), f"no matching log entry: {logs[:3]}"


# ─────────────────────── 6. Consumption regression — clone path ───────────────────────
class TestConsumeOnClone:
    def _topup_via_admin(self, super_token, target_uid, new_left=5):
        """Use the new admin/quota/apply (which can insert rows from scratch) to
        ensure the test user has at least `new_left` reports on L1."""
        r0 = requests.post(f"{API}/admin/quota/request-otp",
                           headers=_hdr(super_token),
                           json={"target_user_id": target_uid})
        if r0.status_code != 200:
            return False
        code = r0.json().get("dev_code")
        if not code:
            return False
        r1 = requests.post(f"{API}/admin/quota/apply",
                           headers=_hdr(super_token),
                           json={"target_user_id": target_uid, "sku_code": "L1",
                                 "new_left": new_left,
                                 "reason": "TEST_iter53 top-up for clone consumption regression",
                                 "otp": code})
        return r1.status_code == 200

    def test_clone_consumes_entitlement(self, user_token, super_token):
        # Get harden user's user_id
        r_me = requests.get(f"{API}/auth/me", headers=_hdr(user_token))
        assert r_me.status_code == 200
        harden_uid = r_me.json()["user_id"]
        # Top up via admin
        ok = self._topup_via_admin(super_token, harden_uid, new_left=5)
        assert ok, "admin top-up failed"

        # Read current entitlements
        r0 = requests.get(f"{API}/store/my-entitlements", headers=_hdr(user_token))
        if r0.status_code != 200:
            pytest.skip(f"my-entitlements failed: {r0.status_code} {r0.text[:200]}")
        ents0 = r0.json()
        # Find a row with balance>0 for L1 or L2
        def _balance(ents, code):
            if isinstance(ents, dict):
                # different shapes
                rows = ents.get("skus") or ents.get("entitlements") or []
            else:
                rows = ents
            for s in rows:
                if s.get("sku_code") == code:
                    return int(s.get("balance") or 0), int(s.get("consumed") or s.get("consumed_qty") or 0)
            return 0, 0

        l1_bal_0, l1_con_0 = _balance(ents0, "L1")
        l2_bal_0, l2_con_0 = _balance(ents0, "L2")
        if l1_bal_0 + l2_bal_0 <= 1:
            pytest.skip(f"user has no spare quota to test clone consumption (L1={l1_bal_0}, L2={l2_bal_0})")

        # Create a decision
        r1 = requests.post(f"{API}/decisions",
                           headers=_hdr(user_token),
                           json={"title": "TEST_clone_consume_iter53", "context": "iter53 clone consumption test"})
        assert r1.status_code in (200, 201), r1.text
        decision_id = r1.json()["id"]

        # Check entitlement decreased by 1
        r2 = requests.get(f"{API}/store/my-entitlements", headers=_hdr(user_token))
        ents1 = r2.json()
        l1_bal_1, _ = _balance(ents1, "L1")
        l2_bal_1, _ = _balance(ents1, "L2")
        delta_create = (l1_bal_0 + l2_bal_0) - (l1_bal_1 + l2_bal_1)
        assert delta_create == 1, f"create did not consume 1; was {l1_bal_0+l2_bal_0}, now {l1_bal_1+l2_bal_1}"

        # Clone
        r3 = requests.post(f"{API}/decisions/{decision_id}/clone",
                           headers=_hdr(user_token),
                           json={"clone_level": "factors", "title": "TEST_clone_iter53_copy"})
        assert r3.status_code in (200, 201), r3.text
        clone_id = r3.json()["id"]

        # Check consumption again
        r4 = requests.get(f"{API}/store/my-entitlements", headers=_hdr(user_token))
        ents2 = r4.json()
        l1_bal_2, _ = _balance(ents2, "L1")
        l2_bal_2, _ = _balance(ents2, "L2")
        delta_clone = (l1_bal_1 + l2_bal_1) - (l1_bal_2 + l2_bal_2)
        assert delta_clone == 1, f"CLONE did not consume an entitlement (this is the iter-53 fix)"

        # cleanup
        requests.delete(f"{API}/decisions/{decision_id}", headers=_hdr(user_token))
        requests.delete(f"{API}/decisions/{clone_id}", headers=_hdr(user_token))
