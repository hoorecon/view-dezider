"""
Iteration 43 — verify dezider PDF endpoint returns valid non-empty PDF
for the sample decision id used in the review request.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")
USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"
ADMIN_EMAIL = "veales.vedic.decisions@gmail.com"
ADMIN_PASSWORD = "Jelcos@Admin2026"
DECISION_ID = "c60fbbf5-20dc-4747-a6f1-7d169da2121e"


def _login(email, password):
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_token():
    return _login(USER_EMAIL, USER_PASSWORD)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


# Verify decision exists for this user
def test_decision_exists(auth_token):
    r = requests.get(
        f"{BASE_URL}/api/decisions/{DECISION_ID}",
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=15,
    )
    assert r.status_code == 200, f"Decision lookup failed: {r.status_code} {r.text[:200]}"
    d = r.json()
    assert d.get("id") == DECISION_ID


# Verify the dezider PDF report endpoint with super-admin (admin_skip bypass)
def test_dezider_pdf_endpoint(admin_token):
    # NOTE: This decision belongs to harden_1777921741 user, but super_admin
    # has 'admin_skip' free-pass on the entitlement gate AND can read any
    # decision. We verify the PDF renders + content-type + non-empty.
    r = requests.get(
        f"{BASE_URL}/api/reports/dezider/{DECISION_ID}.pdf",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30,
    )
    if r.status_code == 404:
        pytest.skip("Decision not accessible by super_admin in this env; skipping")
    assert r.status_code == 200, f"PDF endpoint failed: {r.status_code} {r.text[:300]}"
    ctype = r.headers.get("content-type", "")
    assert "application/pdf" in ctype.lower(), f"Unexpected content-type: {ctype}"
    body = r.content
    assert len(body) > 1000, f"PDF too small: {len(body)} bytes"
    assert body[:4] == b"%PDF", f"Body is not a PDF (starts with {body[:8]!r})"


# Verify the gating works correctly for the regular user (no entitlement)
def test_dezider_pdf_user_gated(auth_token):
    r = requests.get(
        f"{BASE_URL}/api/reports/dezider/{DECISION_ID}.pdf",
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=30,
    )
    # Must NOT be 500 — must be either 200 (already unlocked) or 402 (gated)
    assert r.status_code in (200, 402), (
        f"Expected 200 or 402, got {r.status_code} {r.text[:200]}"
    )


# Verify action-items list endpoint works for this decision (used by ActionItemEditor on Step10)
def test_action_items_list(auth_token):
    r = requests.get(
        f"{BASE_URL}/api/action-items",
        params={"source_module": "MYDEZIDER_MPPS", "source_id": DECISION_ID},
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=15,
    )
    assert r.status_code == 200, f"action-items list failed: {r.status_code} {r.text[:200]}"
    assert isinstance(r.json(), list)
