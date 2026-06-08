"""Iteration 91 — URL Analyse + Screener-to-Decision + PMSBazaar demo page.

Covers:
  • POST /api/url-analyze consent gate (accepted=false, invalid eligibility,
    custom missing note, valid happy-path with local http://localhost:9777/funds.html)
  • Created MyDezider has factors (rating + operator) + options with assessments
    + computed worth_percentage
  • Pros & Cons path → current_step==7 with factors/options/assessments
  • POST /api/embed/screener/run + /to-decision + /to-pros-cons
  • GET /api/embed/demo-host/pmsbazaar-demo?flow=screener
"""
from __future__ import annotations

import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
LOCAL_CRAWL_URL = "http://localhost:9777/funds.html"
PARTNER_SLUG = "pmsbazaar-demo"

USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"
ADMIN_EMAIL = "veales.vedic.decisions@gmail.com"
ADMIN_PASS = "Jelcos@Admin2026"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def user_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": USER_EMAIL, "password": USER_PASS}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"No session token in response: {r.text}"
    # Pass whatsapp verify gate if needed (it doesn't block API access, but for completeness)
    return tok


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("token")
    assert tok, f"No admin token: {r.text}"
    return tok


def auth_hdrs(tok: str):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# URL-Analyze consent gate (negative cases)
# ---------------------------------------------------------------------------
class TestUrlAnalyzeConsentGate:
    def test_accepted_false_returns_400(self, user_token):
        r = requests.post(f"{BASE_URL}/api/url-analyze",
                          headers=auth_hdrs(user_token),
                          json={"url": LOCAL_CRAWL_URL, "eligibility_type": "own",
                                "accepted": False, "target": "mydezider"},
                          timeout=20)
        assert r.status_code == 400, r.text
        assert "disclaimer" in r.text.lower() or "accept" in r.text.lower()

    def test_invalid_eligibility_returns_400(self, user_token):
        r = requests.post(f"{BASE_URL}/api/url-analyze",
                          headers=auth_hdrs(user_token),
                          json={"url": LOCAL_CRAWL_URL, "eligibility_type": "bogus",
                                "accepted": True, "target": "mydezider"},
                          timeout=20)
        assert r.status_code == 400, r.text
        assert "eligibility" in r.text.lower() or "valid" in r.text.lower()

    def test_custom_without_note_returns_400(self, user_token):
        r = requests.post(f"{BASE_URL}/api/url-analyze",
                          headers=auth_hdrs(user_token),
                          json={"url": LOCAL_CRAWL_URL, "eligibility_type": "custom",
                                "custom_note": "", "accepted": True, "target": "mydezider"},
                          timeout=20)
        assert r.status_code == 400, r.text
        assert "custom" in r.text.lower() or "describe" in r.text.lower()


# ---------------------------------------------------------------------------
# URL-Analyze happy paths
# ---------------------------------------------------------------------------
class TestUrlAnalyzeMyDezider:
    decision_id = None

    def test_create_mydezider_from_url(self, user_token):
        r = requests.post(f"{BASE_URL}/api/url-analyze",
                          headers=auth_hdrs(user_token),
                          json={"url": LOCAL_CRAWL_URL, "eligibility_type": "free_public",
                                "accepted": True, "target": "mydezider",
                                "title": f"TEST_iter91_md_{uuid.uuid4().hex[:6]}"},
                          timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("target") == "mydezider"
        assert d.get("item_count") == 4, f"expected 4 funds, got {d}"
        assert d.get("factor_count") >= 2
        assert d.get("id")
        TestUrlAnalyzeMyDezider.decision_id = d["id"]

    def test_get_created_mydezider_has_assessments(self, user_token):
        did = TestUrlAnalyzeMyDezider.decision_id
        assert did, "create-mydezider test must run first"
        r = requests.get(f"{BASE_URL}/api/decisions/{did}",
                         headers=auth_hdrs(user_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        factors = d.get("factors") or []
        options = d.get("options") or []
        assert len(factors) >= 2, factors
        assert len(options) == 4, options
        # Each factor has rating + operator (numeric ones)
        for f in factors:
            assert f.get("rating") is not None
            if f.get("data_type") == "numeric":
                assert f.get("operator") in (">=", "<="), f
        # Each option has assessments + computed worth_percentage
        for opt in options:
            assert isinstance(opt.get("assessments"), list)
            assert len(opt["assessments"]) >= 1, f"no assessments for {opt.get('name')}"
            wp = opt.get("worth_percentage")
            assert wp is not None and 0 <= float(wp) <= 100, f"bad worth: {wp}"


class TestUrlAnalyzeProsCons:
    pros_cons_id = None

    def test_create_pros_cons_from_url(self, user_token):
        r = requests.post(f"{BASE_URL}/api/url-analyze",
                          headers=auth_hdrs(user_token),
                          json={"url": LOCAL_CRAWL_URL, "eligibility_type": "own",
                                "accepted": True, "target": "pros_cons",
                                "title": f"TEST_iter91_pc_{uuid.uuid4().hex[:6]}"},
                          timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("target") == "pros_cons"
        assert d.get("item_count") == 4
        TestUrlAnalyzeProsCons.pros_cons_id = d["id"]

    def test_get_pros_cons_current_step_7(self, user_token):
        pid = TestUrlAnalyzeProsCons.pros_cons_id
        assert pid
        r = requests.get(f"{BASE_URL}/api/pros-cons/{pid}",
                         headers=auth_hdrs(user_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("current_step") == 7, f"current_step={d.get('current_step')}"
        assert len(d.get("factors") or []) >= 2
        assert len(d.get("options") or []) == 4
        assert d.get("assessments"), "assessments dict empty"


# ---------------------------------------------------------------------------
# Screener run → converters
# ---------------------------------------------------------------------------
class TestScreenerConverters:
    run_id = None

    def test_create_screener_run(self, admin_token):
        candidates = [
            {"name": "Alpha", "attributes": {"1Y": 44.39, "AUM": 121.47, "Expense": 0.85}},
            {"name": "Beta", "attributes": {"1Y": 31.90, "AUM": 212.00, "Expense": 1.10}},
            {"name": "Gamma", "attributes": {"1Y": 52.10, "AUM": 88.30, "Expense": 1.45}},
            {"name": "Delta", "attributes": {"1Y": 28.40, "AUM": 540.00, "Expense": 0.20}},
        ]
        factors = [
            {"name": "1Y", "weight": 60, "direction": "higher", "data_type": "numeric"},
            {"name": "Expense", "weight": 40, "direction": "lower", "data_type": "numeric"},
        ]
        r = requests.post(f"{BASE_URL}/api/embed/screener/run",
                          headers=auth_hdrs(admin_token),
                          json={"partner": PARTNER_SLUG, "candidates": candidates,
                                "factors": factors, "finalists": 4, "use_ai": False},
                          timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("run_id"), d
        assert d.get("candidate_count") == 4
        TestScreenerConverters.run_id = d["run_id"]

    def test_to_decision(self, admin_token):
        rid = TestScreenerConverters.run_id
        assert rid
        r = requests.post(f"{BASE_URL}/api/embed/screener/run/{rid}/to-decision",
                          headers=auth_hdrs(admin_token),
                          json={"title": f"TEST_iter91_screener_md_{uuid.uuid4().hex[:6]}"},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("target") == "mydezider"
        assert d.get("finalists") == 4
        # Verify decision exists
        get_r = requests.get(f"{BASE_URL}/api/decisions/{d['id']}",
                             headers=auth_hdrs(admin_token), timeout=15)
        assert get_r.status_code == 200
        doc = get_r.json()
        assert len(doc.get("options") or []) == 4
        assert len(doc.get("factors") or []) >= 2

    def test_to_pros_cons(self, admin_token):
        rid = TestScreenerConverters.run_id
        assert rid
        r = requests.post(f"{BASE_URL}/api/embed/screener/run/{rid}/to-pros-cons",
                          headers=auth_hdrs(admin_token),
                          json={"title": f"TEST_iter91_screener_pc_{uuid.uuid4().hex[:6]}"},
                          timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("target") == "pros_cons"
        # Verify pros_cons exists at step 7
        get_r = requests.get(f"{BASE_URL}/api/pros-cons/{d['id']}",
                             headers=auth_hdrs(admin_token), timeout=15)
        assert get_r.status_code == 200
        doc = get_r.json()
        assert doc.get("current_step") == 7
        assert len(doc.get("options") or []) == 4


# ---------------------------------------------------------------------------
# Phase D — demo host page for partner ranking engine
# ---------------------------------------------------------------------------
class TestPhaseDDemoHost:
    def test_demo_host_screener_flow(self):
        r = requests.get(f"{BASE_URL}/api/embed/demo-host/{PARTNER_SLUG}?flow=screener",
                         timeout=15)
        assert r.status_code == 200, r.text
        body = r.text.lower()
        assert "ranking engine" in body, "headline missing 'ranking engine'"
        assert "rank these for me" in body, "CTA missing 'Rank these for me'"
