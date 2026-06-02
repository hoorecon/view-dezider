"""Iteration 35 — Backend regression for the admin-skip-payment PDF download fix.

Bug: Admin enabled global skip-payment toggle, but downloading the Pros & Cons
PDF still showed paywall (.pdf returned 402). Root cause: decision_reports.py
omitted 'admin_skip' from the free-pass branch in
_check_access_and_maybe_consume and report_info.

Fix verified here:
  1. /api/admin/payment-settings PUT { skip_payment_all_flows: true }
  2. As a NO-ENTITLEMENT user:
       a. POST /api/pros-cons          → /reports/pros_cons/{id}.pdf  → 200
                                       → /reports/pros_cons/{id}/info → unlocked=true, via='admin_skip'
       b. POST /api/decisions (dezider)→ /reports/dezider/{id}.pdf    → 200
                                       → /reports/dezider/{id}/info   → unlocked=true, via='admin_skip'
       c. POST /api/swot              → /reports/swot/{id}.pdf       → 200
                                       → /reports/swot/{id}/info      → unlocked=true, via='admin_skip'
  3. Negative: set skip_payment_all_flows=false → .pdf must return 402 and
     /info must return unlocked=false (gate still protects when toggle OFF).
  4. ALWAYS restores the toggle to its ORIGINAL state at teardown (default OFF).
"""

import os
import uuid
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────
def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token


def _set_skip_payment(admin_headers: dict, flag: bool, reason: str = "qa"):
    payload = {"skip_payment_all_flows": flag, "skip_payment_reason": reason if flag else ""}
    r = requests.put(
        f"{BASE_URL}/api/admin/payment-settings",
        json=payload,
        headers=admin_headers,
        timeout=20,
    )
    assert r.status_code == 200, f"Set skip-payment ({flag}) failed: {r.status_code} {r.text}"
    body = r.json()
    assert bool(body.get("skip_payment_all_flows")) is flag
    # Confirm via GET
    g = requests.get(
        f"{BASE_URL}/api/admin/payment-settings", headers=admin_headers, timeout=20
    )
    assert g.status_code == 200
    assert bool(g.json().get("skip_payment_all_flows")) is flag


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_headers():
    token = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_headers():
    token = _login(USER_EMAIL, USER_PASSWORD)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def original_toggle(admin_headers):
    """Capture the toggle's original state and restore it at the end (default OFF)."""
    r = requests.get(
        f"{BASE_URL}/api/admin/payment-settings", headers=admin_headers, timeout=20
    )
    assert r.status_code == 200, f"GET payment-settings failed: {r.text}"
    original = bool(r.json().get("skip_payment_all_flows", False))
    yield original
    # Teardown: restore
    _set_skip_payment(admin_headers, original, reason="restore_after_iter35")


@pytest.fixture(scope="module")
def pros_cons_id(user_headers):
    r = requests.post(
        f"{BASE_URL}/api/pros-cons",
        json={
            "title": f"TEST_iter35_PnC_{uuid.uuid4().hex[:8]}",
            "context": "iter35 admin_skip test",
            "life_area": "career",
            "decision_type": "career",
        },
        headers=user_headers,
        timeout=20,
    )
    assert r.status_code in (200, 201), f"Create PnC failed: {r.status_code} {r.text}"
    pid = r.json().get("id")
    assert pid
    yield pid
    try:
        requests.delete(f"{BASE_URL}/api/pros-cons/{pid}", headers=user_headers, timeout=10)
    except Exception:
        pass


@pytest.fixture(scope="module")
def dezider_id(user_headers):
    r = requests.post(
        f"{BASE_URL}/api/decisions",
        json={
            "title": f"TEST_iter35_Dez_{uuid.uuid4().hex[:8]}",
            "context": "iter35 admin_skip test",
        },
        headers=user_headers,
        timeout=20,
    )
    assert r.status_code in (200, 201), f"Create decision failed: {r.status_code} {r.text}"
    did = r.json().get("id") or r.json().get("decision_id")
    assert did
    yield did
    try:
        requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=user_headers, timeout=10)
    except Exception:
        pass


@pytest.fixture(scope="module")
def swot_id(user_headers):
    r = requests.post(
        f"{BASE_URL}/api/swot",
        json={
            "title": f"TEST_iter35_Swot_{uuid.uuid4().hex[:8]}",
            "context": "iter35 admin_skip test",
        },
        headers=user_headers,
        timeout=20,
    )
    assert r.status_code in (200, 201), f"Create SWOT failed: {r.status_code} {r.text}"
    sid = r.json().get("id") or r.json().get("swot_id")
    assert sid
    yield sid
    try:
        requests.delete(f"{BASE_URL}/api/swot/{sid}", headers=user_headers, timeout=10)
    except Exception:
        pass


# ────────────────────────────────────────────────────────────────────
# Tests — Skip-payment ON branch (admin_skip free pass)
# ────────────────────────────────────────────────────────────────────
class TestAdminSkipPaymentON:
    """With skip_payment_all_flows=ON, the no-entitlement user must:
      • GET /info → 200, unlocked=true, unlocked_via='admin_skip'
      • GET .pdf  → 200, PDF body, X-Report-Access-Via='admin_skip'
    """

    def test_aa_enable_toggle(self, admin_headers, original_toggle):
        _set_skip_payment(admin_headers, True, reason="iter35-qa")

    # Pros & Cons
    def test_ab_pros_cons_info_unlocked_admin_skip(self, user_headers, pros_cons_id):
        r = requests.get(
            f"{BASE_URL}/api/reports/pros_cons/{pros_cons_id}/info",
            headers=user_headers, timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("module") == "pros_cons"
        assert body.get("decision_id") == pros_cons_id
        assert body.get("unlocked") is True, f"unlocked must be true: {body}"
        assert body.get("unlocked_via") == "admin_skip", f"via must be admin_skip: {body}"

    def test_ac_pros_cons_pdf_returns_200(self, user_headers, pros_cons_id):
        r = requests.get(
            f"{BASE_URL}/api/reports/pros_cons/{pros_cons_id}.pdf",
            headers=user_headers, timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), \
            f"Wrong content-type: {r.headers.get('content-type')}"
        assert r.content[:4] == b"%PDF", "Body is not a PDF"
        # X-Report-Access-Via SHOULD be 'admin_skip' on first unlock.
        # If the unlock was recorded earlier by /info, it could be 'prior_unlock'
        # but the current code only inserts the unlock row in the .pdf path,
        # so for first call we expect 'admin_skip'.
        via = r.headers.get("X-Report-Access-Via", "")
        assert via in ("admin_skip", "prior_unlock"), f"Unexpected via header: {via}"

    # Dezider
    def test_ad_dezider_info_unlocked_admin_skip(self, user_headers, dezider_id):
        r = requests.get(
            f"{BASE_URL}/api/reports/dezider/{dezider_id}/info",
            headers=user_headers, timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("unlocked") is True
        assert body.get("unlocked_via") == "admin_skip"

    def test_ae_dezider_pdf_returns_200(self, user_headers, dezider_id):
        r = requests.get(
            f"{BASE_URL}/api/reports/dezider/{dezider_id}.pdf",
            headers=user_headers, timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        assert r.content[:4] == b"%PDF"

    # SWOT
    def test_af_swot_info_unlocked_admin_skip(self, user_headers, swot_id):
        r = requests.get(
            f"{BASE_URL}/api/reports/swot/{swot_id}/info",
            headers=user_headers, timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("unlocked") is True
        assert body.get("unlocked_via") == "admin_skip"

    def test_ag_swot_pdf_returns_200(self, user_headers, swot_id):
        r = requests.get(
            f"{BASE_URL}/api/reports/swot/{swot_id}.pdf",
            headers=user_headers, timeout=30,
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        assert r.content[:4] == b"%PDF"


# ────────────────────────────────────────────────────────────────────
# Tests — Skip-payment OFF branch (gate still protects)
# ────────────────────────────────────────────────────────────────────
class TestAdminSkipPaymentOFFNegative:
    """With skip_payment_all_flows=OFF, the no-entitlement user must:
      • GET .pdf → 402 (gate restored)
      • Already-unlocked items remain unlocked (prior_unlock) — so we
        validate the negative path on a freshly-created decision that
        has no prior_unlock row.
    """

    def test_ba_disable_toggle(self, admin_headers, original_toggle):
        _set_skip_payment(admin_headers, False, reason="")

    def test_bb_new_pros_cons_pdf_returns_402_when_off(self, user_headers):
        # Create a fresh PnC (no prior unlock row) and confirm gate fires
        r = requests.post(
            f"{BASE_URL}/api/pros-cons",
            json={
                "title": f"TEST_iter35_Neg_PnC_{uuid.uuid4().hex[:8]}",
                "context": "iter35 OFF negative",
                "life_area": "career",
                "decision_type": "career",
            },
            headers=user_headers, timeout=20,
        )
        assert r.status_code in (200, 201), r.text
        pid = r.json()["id"]
        try:
            info = requests.get(
                f"{BASE_URL}/api/reports/pros_cons/{pid}/info",
                headers=user_headers, timeout=20,
            )
            assert info.status_code == 200, info.text
            body = info.json()
            assert body.get("unlocked") is False, f"Should be locked when toggle OFF: {body}"
            assert body.get("unlocked_via") in (None, ""), f"via should be None: {body}"

            pdf = requests.get(
                f"{BASE_URL}/api/reports/pros_cons/{pid}.pdf",
                headers=user_headers, timeout=30,
            )
            assert pdf.status_code == 402, (
                f"Expected 402 with toggle OFF, got {pdf.status_code}: {pdf.text[:300]}"
            )
            # Detail must be entitlement-related, not 'analysis not found'
            try:
                detail = pdf.json().get("detail", "")
            except Exception:
                detail = pdf.text
            assert "not found" not in str(detail).lower(), \
                f"402 detail must be entitlement, got: {detail}"
        finally:
            try:
                requests.delete(f"{BASE_URL}/api/pros-cons/{pid}", headers=user_headers, timeout=10)
            except Exception:
                pass


# ────────────────────────────────────────────────────────────────────
# Regression — pros_cons collection-name fix (iter34) still holds
# ────────────────────────────────────────────────────────────────────
class TestProsConsCollectionRegression:
    def test_owner_info_resolves_no_404(self, user_headers, pros_cons_id):
        # NOTE: This may execute under either toggle state depending on order.
        # We only assert the lookup resolves (not 404).
        r = requests.get(
            f"{BASE_URL}/api/reports/pros_cons/{pros_cons_id}/info",
            headers=user_headers, timeout=20,
        )
        assert r.status_code != 404, \
            f"Regression failure — owner should NOT get 404 for own PnC: {r.text}"
        assert r.status_code == 200
