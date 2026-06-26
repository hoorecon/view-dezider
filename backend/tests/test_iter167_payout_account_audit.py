"""
Iter 167: Seller Payout Account flow + Admin Payouts Audit Log.

Covers:
  • GET /api/earnings/account-types
  • GET /api/earnings/ifsc/{ifsc}     (valid HDFC0000001, invalid XXXX0000001)
  • POST /api/earnings/payout-account  (validation paths + success)
  • GET /api/earnings/summary          (account_verified, eligible_for_payout)
  • POST /api/admin/payouts/run        (manual_idfc → audit row 'success';
                                        razorpayx unconfigured → 400 + 'aborted';
                                        invalid channel → 400 + 'error')
  • GET  /api/admin/payouts/audit-log
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL") or "").rstrip("/")
assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL / EXPO_BACKEND_URL is required"

SUPER_ADMIN_EMAIL = "super@test.com"
SUPER_ADMIN_PASSWORD = "SuperPass2026!"


def _login(session: requests.Session, email: str, password: str) -> str:
    r = session.post(f"{BASE_URL}/api/auth/login",
                     json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    token = r.json().get("session_token")
    assert token, f"no session_token: {r.text}"
    session.headers.update({"Authorization": f"Bearer {token}"})
    return token


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    _login(s, SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    return s


@pytest.fixture(scope="module")
def user_session():
    """Register a fresh seller user for the payout-account tests."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"TEST_payout_{uuid.uuid4().hex[:10]}@example.com"
    password = "TestPass2026!"
    r = s.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": password, "name": "TEST Payout Seller",
    }, timeout=20)
    if r.status_code not in (200, 201):
        pytest.skip(f"could not register test user: {r.status_code} {r.text}")
    body = r.json()
    token = body.get("session_token") or body.get("token")
    if not token:
        # fallback: login
        _login(s, email, password)
    else:
        s.headers.update({"Authorization": f"Bearer {token}"})
    s.test_email = email  # type: ignore
    return s


# ---------- /earnings/account-types ----------------------------------------
class TestAccountTypes:
    def test_returns_india_list(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/earnings/account-types", timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert "account_types" in data
        types = data["account_types"]
        assert isinstance(types, list) and len(types) >= 5
        # core ones expected
        for must in ("Savings", "Current"):
            assert must in types, f"missing '{must}' in account_types: {types}"
        # NRE / NRO must exist (substring match — exact label has parens suffix)
        joined = " | ".join(types)
        assert "NRE" in joined and "NRO" in joined, joined


# ---------- /earnings/ifsc/{ifsc} ------------------------------------------
class TestIfscLookup:
    def test_valid_ifsc_returns_bank_branch(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/earnings/ifsc/HDFC0000001", timeout=20)
        if r.status_code != 200:
            pytest.skip(f"Razorpay IFSC API unreachable in env: {r.status_code} {r.text[:120]}")
        data = r.json()
        assert data.get("bank"), f"no bank returned: {data}"
        assert data.get("branch"), f"no branch returned: {data}"
        assert (data.get("ifsc") or "").upper() == "HDFC0000001"

    def test_invalid_ifsc_returns_404(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/earnings/ifsc/XXXX0000001", timeout=20)
        assert r.status_code == 404, f"{r.status_code} {r.text}"


# ---------- /earnings/payout-account ---------------------------------------
class TestPayoutAccountValidation:
    BASE_GOOD = {
        "vpa": "testseller@oksbi",
        "account_number": "123456789012",
        "ifsc": "HDFC0000001",
        "beneficiary_name": "Test Seller",
        "account_type": "Savings",
    }

    def _post(self, user_session, payload):
        return user_session.post(f"{BASE_URL}/api/earnings/payout-account",
                                 json=payload, timeout=25)

    def test_missing_vpa_rejected(self, user_session):
        body = dict(self.BASE_GOOD); body["vpa"] = ""
        r = self._post(user_session, body)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        assert "upi" in (r.json().get("detail") or "").lower()

    def test_bad_vpa_format_rejected(self, user_session):
        body = dict(self.BASE_GOOD); body["vpa"] = "notavpa"
        r = self._post(user_session, body)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        assert "upi" in (r.json().get("detail") or "").lower()

    def test_missing_bank_fields_rejected(self, user_session):
        body = dict(self.BASE_GOOD); body["account_number"] = ""
        r = self._post(user_session, body)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        assert "bank" in (r.json().get("detail") or "").lower() \
            or "ifsc" in (r.json().get("detail") or "").lower()

    def test_invalid_account_type_rejected(self, user_session):
        body = dict(self.BASE_GOOD); body["account_type"] = "Crypto"
        r = self._post(user_session, body)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        assert "account_type" in (r.json().get("detail") or "").lower() \
            or "Savings" in (r.json().get("detail") or "")

    def test_missing_account_type_rejected(self, user_session):
        body = dict(self.BASE_GOOD); body["account_type"] = ""
        r = self._post(user_session, body)
        assert r.status_code == 400, f"{r.status_code} {r.text}"

    def test_invalid_ifsc_rejected(self, user_session):
        body = dict(self.BASE_GOOD); body["ifsc"] = "XXXX0000001"
        r = self._post(user_session, body)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        assert "ifsc" in (r.json().get("detail") or "").lower()

    def test_success_with_full_payload(self, user_session):
        r = self._post(user_session, self.BASE_GOOD)
        if r.status_code != 200:
            pytest.skip(f"likely IFSC API unreachable: {r.status_code} {r.text[:160]}")
        data = r.json()
        assert data.get("ok") is True, data
        assert data.get("verified") is True, data
        ifsc_info = data.get("ifsc_info") or {}
        assert ifsc_info.get("bank"), f"ifsc_info.bank missing: {data}"
        assert ifsc_info.get("branch"), f"ifsc_info.branch missing: {data}"
        pd = data.get("bank_pennydrop") or {}
        # RazorpayX is not live in this env → must be skipped
        assert pd.get("status") == "skipped_rzx_inactive", f"unexpected pennydrop: {pd}"
        acct = data.get("payout_account") or {}
        assert acct.get("vpa") == self.BASE_GOOD["vpa"]
        assert acct.get("account_type") == "Savings"
        assert acct.get("bank_name")
        assert acct.get("branch")


# ---------- /earnings/summary (after saving account) -----------------------
class TestSummaryAfterSave:
    def test_summary_reflects_verified_account(self, user_session):
        # ensure account saved first (may already be from previous test class)
        save_r = user_session.post(f"{BASE_URL}/api/earnings/payout-account", json={
            "vpa": "testseller@oksbi", "account_number": "123456789012",
            "ifsc": "HDFC0000001", "beneficiary_name": "Test Seller",
            "account_type": "Savings",
        }, timeout=25)
        if save_r.status_code != 200:
            pytest.skip(f"account save failed: {save_r.status_code} {save_r.text[:120]}")

        r = user_session.get(f"{BASE_URL}/api/earnings/summary", timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data.get("account_verified") is True, data
        assert data.get("has_payout_account") is True
        # eligibility = balance threshold AND account_verified
        assert data.get("eligible_for_payout") == \
            (bool(data.get("balance_eligible")) and bool(data.get("account_verified"))), data
        # required shape
        for k in ("available_inr", "min_payout_inr", "payout_weekday", "next_payout_eta"):
            assert k in data


# ---------- Admin payouts run → audit log ----------------------------------
class TestAdminPayoutsAudit:
    def test_manual_idfc_writes_success_audit(self, admin_session):
        # snapshot
        eligible = admin_session.get(f"{BASE_URL}/api/admin/payouts/eligible-summary",
                                     timeout=15).json()
        r = admin_session.post(f"{BASE_URL}/api/admin/payouts/run",
                               json={"channel": "manual_idfc"}, timeout=25)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        time.sleep(0.4)
        log = admin_session.get(f"{BASE_URL}/api/admin/payouts/audit-log",
                                timeout=15)
        assert log.status_code == 200, f"{log.status_code} {log.text}"
        items = log.json().get("items") or []
        assert items, "audit-log returned no items"
        latest = items[0]
        assert latest.get("channel") == "manual_idfc", latest
        assert latest.get("outcome") == "success", latest
        assert latest.get("actor_email") == SUPER_ADMIN_EMAIL, latest
        assert "eligible_before" in latest and "total_inr_before" in latest, latest
        # cross-check snapshot value sanity
        assert latest.get("eligible_before") == eligible.get("eligible"), \
            f"snapshot drift: {latest} vs {eligible}"

    def test_razorpayx_unconfigured_writes_aborted_audit(self, admin_session):
        eligible = admin_session.get(f"{BASE_URL}/api/admin/payouts/eligible-summary",
                                     timeout=15).json()
        if eligible.get("razorpayx_active"):
            pytest.skip("RazorpayX is active in env; cannot test abort path")
        r = admin_session.post(f"{BASE_URL}/api/admin/payouts/run",
                               json={"channel": "razorpayx"}, timeout=20)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        time.sleep(0.4)
        items = admin_session.get(f"{BASE_URL}/api/admin/payouts/audit-log",
                                  timeout=15).json().get("items") or []
        # find the latest razorpayx row
        rzx = next((x for x in items if x.get("channel") == "razorpayx"), None)
        assert rzx is not None, f"no razorpayx audit row found: {items[:3]}"
        assert rzx.get("outcome") == "aborted", rzx

    def test_invalid_channel_writes_error_audit(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/payouts/run",
                               json={"channel": "stripe"}, timeout=15)
        assert r.status_code == 400, f"{r.status_code} {r.text}"
        time.sleep(0.4)
        items = admin_session.get(f"{BASE_URL}/api/admin/payouts/audit-log",
                                  timeout=15).json().get("items") or []
        err = next((x for x in items if x.get("channel") == "stripe"
                    and x.get("outcome") == "error"), None)
        assert err is not None, f"no error-outcome audit row for invalid channel: {items[:5]}"
