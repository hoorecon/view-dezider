"""Backend regression tests for the Pros & Cons PDF report collection-name bug fix.

Bug: routes/decision_reports.py was reading `pros_cons_analyses` but the Pros &
Cons module stores in `pros_cons`. Fix changed the lookup to `db.pros_cons`.

Tests:
  1. POST /api/pros-cons → create analysis as owner
  2. GET  /api/reports/pros_cons/{id}/info as owner → 200 (NOT 404)
  3. GET  /api/reports/pros_cons/{id}.pdf as owner → NOT 404 (either 200 or 402)
  4. Regression: GET /api/reports/dezider/{id}/info for a PRR decision
  5. Regression: GET /api/reports/swot/{id}/info for a SWOT analysis
  6. Negative: GET /api/reports/pros_cons/{random_id}/info → 404
"""

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
if not BASE_URL:
    # Local fallback for in-container testing
    BASE_URL = "http://localhost:8001"
BASE_URL = BASE_URL.rstrip("/")

USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"


# ────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_headers(session):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def pros_cons_id(session, auth_headers):
    """Create a Pros & Cons analysis owned by the test user."""
    payload = {
        "title": f"TEST_PnC_ReportFix_{uuid.uuid4().hex[:8]}",
        "context": "Regression test for collection name fix",
        "life_area": "career",
        "decision_type": "career",
    }
    r = session.post(
        f"{BASE_URL}/api/pros-cons",
        json=payload,
        headers=auth_headers,
        timeout=20,
    )
    assert r.status_code in (200, 201), f"Create PnC failed: {r.status_code} {r.text}"
    body = r.json()
    pc_id = body.get("id")
    assert pc_id, f"No id in create response: {body}"
    yield pc_id
    # Cleanup: move to trash (best effort)
    try:
        session.delete(
            f"{BASE_URL}/api/pros-cons/{pc_id}",
            headers=auth_headers,
            timeout=10,
        )
    except Exception:
        pass


# ────────────────────────────────────────────────────────────────────
# Bug-fix: Pros & Cons report endpoint reads from `pros_cons`
# ────────────────────────────────────────────────────────────────────
class TestProsConsReportBugFix:
    """The lookup must now hit db.pros_cons (previously db.pros_cons_analyses)."""

    def test_info_endpoint_owner_returns_200(self, session, auth_headers, pros_cons_id):
        r = session.get(
            f"{BASE_URL}/api/reports/pros_cons/{pros_cons_id}/info",
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 200, (
            f"Expected 200, got {r.status_code}: {r.text}\n"
            "This is the bug — owner should be able to see report info."
        )
        data = r.json()
        # Validate response shape
        assert data.get("module") == "pros_cons"
        assert data.get("decision_id") == pros_cons_id
        assert "unlocked" in data
        assert "l1_balance" in data
        assert "l2_balance" in data

    def test_pdf_endpoint_owner_no_longer_404(self, session, auth_headers, pros_cons_id):
        """Owner should NOT get 404 'Pros & Cons analysis not found'.
        Acceptable outcomes:
          - 200 (PDF returned directly to owner — if owner == free pass)
          - 402 (Payment Required because no L1/L2 entitlement)
        UNACCEPTABLE:
          - 404 with detail 'Pros & Cons analysis not found' (the original bug)
        """
        r = session.get(
            f"{BASE_URL}/api/reports/pros_cons/{pros_cons_id}.pdf",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code != 404, (
            f"Got 404 — bug NOT fixed. Body: {r.text}"
        )
        assert r.status_code in (200, 402), (
            f"Unexpected status {r.status_code}: {r.text}"
        )
        if r.status_code == 402:
            # The 402 must be the entitlement check, NOT the analysis-not-found
            try:
                detail = r.json().get("detail", "")
            except Exception:
                detail = r.text
            assert "not found" not in str(detail).lower(), (
                f"402 body should be entitlement-related, got: {detail}"
            )

    def test_negative_random_id_returns_404(self, session, auth_headers):
        random_id = str(uuid.uuid4())
        r = session.get(
            f"{BASE_URL}/api/reports/pros_cons/{random_id}/info",
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 404, (
            f"Expected 404 for nonexistent id, got {r.status_code}: {r.text}"
        )


# ────────────────────────────────────────────────────────────────────
# Regression: dezider + swot still resolve correctly
# ────────────────────────────────────────────────────────────────────
class TestRegressionOtherModules:
    """Ensure the fix did not break the other two module branches."""

    def test_dezider_info_for_existing_decision(self, session, auth_headers):
        # Find any PRR decision owned by this user
        r = session.get(
            f"{BASE_URL}/api/decisions",
            headers=auth_headers,
            timeout=20,
        )
        if r.status_code != 200:
            pytest.skip(f"GET /api/decisions failed: {r.status_code}")
        decisions = r.json() if isinstance(r.json(), list) else r.json().get("decisions", [])
        if not decisions:
            # Create a tiny PRR decision so we can run the regression check
            create = session.post(
                f"{BASE_URL}/api/decisions",
                json={"title": f"TEST_DeziderReport_{uuid.uuid4().hex[:6]}",
                      "context": "regression"},
                headers=auth_headers,
                timeout=20,
            )
            if create.status_code not in (200, 201):
                pytest.skip(f"Could not create a PRR decision: {create.status_code} {create.text}")
            decisions = [create.json()]

        decision_id = decisions[0].get("id") or decisions[0].get("decision_id")
        assert decision_id, f"No decision id in {decisions[0]}"

        info = session.get(
            f"{BASE_URL}/api/reports/dezider/{decision_id}/info",
            headers=auth_headers,
            timeout=20,
        )
        assert info.status_code == 200, (
            f"Dezider info regression failed: {info.status_code} {info.text}"
        )
        body = info.json()
        assert body.get("module") == "dezider"
        assert body.get("decision_id") == decision_id

    def test_swot_info_for_existing_swot(self, session, auth_headers):
        # List SWOT analyses
        r = session.get(
            f"{BASE_URL}/api/swot",
            headers=auth_headers,
            timeout=20,
        )
        if r.status_code != 200:
            pytest.skip(f"GET /api/swot failed: {r.status_code}")

        swots = r.json() if isinstance(r.json(), list) else r.json().get("swot_analyses", [])
        if not swots:
            # Create a SWOT analysis
            create = session.post(
                f"{BASE_URL}/api/swot",
                json={"title": f"TEST_SwotReport_{uuid.uuid4().hex[:6]}",
                      "context": "regression"},
                headers=auth_headers,
                timeout=20,
            )
            if create.status_code not in (200, 201):
                pytest.skip(f"Could not create a SWOT analysis: {create.status_code} {create.text}")
            created = create.json()
            swot_id = created.get("id") or created.get("swot_id")
        else:
            swot_id = swots[0].get("id") or swots[0].get("swot_id")

        assert swot_id, "No SWOT id available for regression"

        info = session.get(
            f"{BASE_URL}/api/reports/swot/{swot_id}/info",
            headers=auth_headers,
            timeout=20,
        )
        assert info.status_code == 200, (
            f"SWOT info regression failed: {info.status_code} {info.text}"
        )
        body = info.json()
        assert body.get("module") == "swot"
        assert body.get("decision_id") == swot_id
