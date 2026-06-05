"""Iteration 60 — My Dezider AI satisfaction assessment.

Tests for: POST /api/decisions/{decision_id}/factors/{factor_id}/ai-assess

Covers:
- 400 when no actual_value provided and none stored
- 404 for bad decision_id, factor_id, option_id
- 200 happy path: returns {percentage 0-100, source in ('ai','ratio')} and
  GET /api/decisions/{id} reflects option.assessments entry with
  percentage + unit_value + assessment_mode='custom'
- Sub-factor (parent_id) variant
- Regression: GET/PUT /api/decisions/{id} still 200
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://dashboard-rewire.preview.emergentagent.com",
).rstrip("/")
EMAIL = "harden_1777921741@example.com"
PASSWORD = "HardenPass2026!"


# ── auth fixtures ────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── decision seed ───────────────────────────────────────────────────
@pytest.fixture(scope="module")
def md(auth):
    ts = int(time.time())
    r = requests.post(
        f"{BASE_URL}/api/decisions",
        json={"title": f"TEST_iter60_md_{ts}", "context": "ctx-iter60"},
        headers=auth,
        timeout=15,
    )
    assert r.status_code == 200, r.text
    did = r.json()["id"]

    main_fid = "f-main-iter60"
    sub_fid = "f-sub-iter60"
    oid = "o-iter60"
    payload = {
        "factors": [
            {
                "id": main_fid,
                "name": "Cost",
                "category": "primary",
                "rating": 8,
                "order": 0,
                "expected_value": "1000",
                "unit": "INR",
                "operator": "<=",
                "factor_type": "quantitative",
                "data_type": "number",
            },
            {
                "id": sub_fid,
                "name": "Tax",
                "category": "primary",
                "rating": 5,
                "order": 1,
                "expected_value": "100",
                "unit": "INR",
                "operator": "<=",
                "factor_type": "quantitative",
                "data_type": "number",
                "parent_id": main_fid,
            },
        ],
        "options": [
            {"id": oid, "name": "OptA", "assessments": [], "worth_percentage": 0}
        ],
    }
    u = requests.put(
        f"{BASE_URL}/api/decisions/{did}", json=payload, headers=auth, timeout=15
    )
    assert u.status_code == 200, u.text

    yield {"did": did, "main_fid": main_fid, "sub_fid": sub_fid, "oid": oid}

    requests.delete(f"{BASE_URL}/api/decisions/{did}", headers=auth, timeout=15)


# ════════════════════════════════════════════════════════════════════
# Validation / 4xx errors
# ════════════════════════════════════════════════════════════════════
class TestAIAssessErrors:
    def test_400_when_no_actual_value(self, auth, md):
        """Endpoint must 400 when no actual_value provided and none stored."""
        r = requests.post(
            f"{BASE_URL}/api/decisions/{md['did']}/factors/{md['main_fid']}/ai-assess",
            json={"option_id": md["oid"]},
            headers=auth,
            timeout=30,
        )
        assert r.status_code == 400, r.text
        assert "actual" in r.text.lower()

    def test_404_bad_decision_id(self, auth, md):
        r = requests.post(
            f"{BASE_URL}/api/decisions/non-existent-decision/factors/{md['main_fid']}/ai-assess",
            json={"option_id": md["oid"], "actual_value": "900"},
            headers=auth,
            timeout=15,
        )
        assert r.status_code == 404

    def test_404_bad_factor_id(self, auth, md):
        r = requests.post(
            f"{BASE_URL}/api/decisions/{md['did']}/factors/non-existent-factor/ai-assess",
            json={"option_id": md["oid"], "actual_value": "900"},
            headers=auth,
            timeout=15,
        )
        assert r.status_code == 404

    def test_404_bad_option_id(self, auth, md):
        r = requests.post(
            f"{BASE_URL}/api/decisions/{md['did']}/factors/{md['main_fid']}/ai-assess",
            json={"option_id": "non-existent-option", "actual_value": "900"},
            headers=auth,
            timeout=15,
        )
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
# Happy path (main factor) + persistence
# ════════════════════════════════════════════════════════════════════
class TestAIAssessMainFactor:
    def test_200_returns_pct_and_persists(self, auth, md):
        r = requests.post(
            f"{BASE_URL}/api/decisions/{md['did']}/factors/{md['main_fid']}/ai-assess",
            json={"option_id": md["oid"], "actual_value": "900"},
            headers=auth,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "percentage" in body, body
        assert isinstance(body["percentage"], int)
        assert 0 <= body["percentage"] <= 100
        assert body.get("source") in ("ai", "ratio"), body

        # Persisted: GET decision and inspect option.assessments list
        g = requests.get(
            f"{BASE_URL}/api/decisions/{md['did']}", headers=auth, timeout=15
        )
        assert g.status_code == 200
        decision = g.json()
        opt = next(o for o in decision["options"] if o["id"] == md["oid"])
        by_fid = {a["factor_id"]: a for a in opt.get("assessments", [])}
        assert md["main_fid"] in by_fid, by_fid
        cell = by_fid[md["main_fid"]]
        assert cell["percentage"] == body["percentage"]
        assert "900" in str(cell.get("unit_value", ""))
        assert cell.get("assessment_mode") == "custom"


# ════════════════════════════════════════════════════════════════════
# Sub-factor variant
# ════════════════════════════════════════════════════════════════════
class TestAIAssessSubFactor:
    def test_200_subfactor_returns_pct_and_persists(self, auth, md):
        r = requests.post(
            f"{BASE_URL}/api/decisions/{md['did']}/factors/{md['sub_fid']}/ai-assess",
            json={"option_id": md["oid"], "actual_value": "80"},
            headers=auth,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert 0 <= body["percentage"] <= 100
        assert body.get("source") in ("ai", "ratio")

        g = requests.get(
            f"{BASE_URL}/api/decisions/{md['did']}", headers=auth, timeout=15
        )
        assert g.status_code == 200
        decision = g.json()
        opt = next(o for o in decision["options"] if o["id"] == md["oid"])
        by_fid = {a["factor_id"]: a for a in opt.get("assessments", [])}
        assert md["sub_fid"] in by_fid, by_fid
        cell = by_fid[md["sub_fid"]]
        assert cell["percentage"] == body["percentage"]
        assert "80" in str(cell.get("unit_value", ""))
        assert cell.get("assessment_mode") == "custom"

    def test_uses_stored_actual_when_omitted(self, auth, md):
        """After persisting an actual_value, a subsequent call without actual_value
        should re-use the stored unit_value and succeed (not 400)."""
        r = requests.post(
            f"{BASE_URL}/api/decisions/{md['did']}/factors/{md['sub_fid']}/ai-assess",
            json={"option_id": md["oid"]},
            headers=auth,
            timeout=60,
        )
        # We just stored an actual for sub_fid in the previous test → should succeed.
        assert r.status_code == 200, r.text
        body = r.json()
        assert 0 <= body["percentage"] <= 100


# ════════════════════════════════════════════════════════════════════
# Regression: GET / PUT still 200
# ════════════════════════════════════════════════════════════════════
class TestRegression:
    def test_get_decision_still_200(self, auth, md):
        r = requests.get(
            f"{BASE_URL}/api/decisions/{md['did']}", headers=auth, timeout=15
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == md["did"]
        assert len(body["factors"]) >= 2
        assert len(body["options"]) >= 1

    def test_put_decision_still_200(self, auth, md):
        g = requests.get(
            f"{BASE_URL}/api/decisions/{md['did']}", headers=auth, timeout=15
        ).json()
        # touch title; preserve factors/options
        new_title = g["title"] + " (touched)"
        r = requests.put(
            f"{BASE_URL}/api/decisions/{md['did']}",
            json={
                "title": new_title,
                "factors": g["factors"],
                "options": g["options"],
            },
            headers=auth,
            timeout=15,
        )
        assert r.status_code == 200, r.text
        # verify roundtrip
        g2 = requests.get(
            f"{BASE_URL}/api/decisions/{md['did']}", headers=auth, timeout=15
        ).json()
        assert g2["title"] == new_title
