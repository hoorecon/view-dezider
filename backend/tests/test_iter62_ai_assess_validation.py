"""Iter62 — AI Assist validation + actual-resolution rules.

Validates `/app/backend/core/ai_assess.py` (shared helper) via both routes:
  • My Dezider:  POST /api/decisions/{decision_id}/factors/{factor_id}/ai-assess
  • Pros & Cons: POST /api/pros-cons/{id}/factors/{factor_id}/ai-assess

Rules under test:
  * Quantitative (data_type='numeric' OR factor_type='objective')
      - Missing Expected             → 400 mentioning "Expected"
      - Missing Operator             → 400 mentioning "Operator"
      - Missing Actual (no data_source, no solution_id) → 400 mentioning "Actual"
      - All present                  → 200 with integer 0..100
  * Qualitative (data_type='text' OR factor_type='subjective')
      - Missing Expected             → 400 mentioning "Expected"
      - Expected present, Actual omitted → 200 with AI-inferred actual_value

Success response keys differ per flow:
  * My Dezider returns `percentage`
  * Pros & Cons returns `assessment_pct`
Both qualitative success responses must echo an inferred `actual_value`.
"""
import os
import time

import pytest
import requests


BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")
API = f"{BASE_URL}/api"

# Per review_request: super@test.com may 401 in dev — admin@test.com is canonical.
CREDS = [
    ("admin@test.com", "AdminPass2026!"),
    ("super@test.com", "AdminPass2026!"),
]

LLM_TIMEOUT = 90  # AI calls can take a while


# ── auth ────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    token = None
    for email, pw in CREDS:
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
        if r.status_code == 200:
            j = r.json()
            token = j.get("session_token") or j.get("token") or j.get("access_token")
            if token:
                print(f"[iter62] auth ok via {email}")
                break
    if not token:
        pytest.skip("Could not login with provided test credentials")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ════════════════════════════════════════════════════════════════════
# MY DEZIDER fixtures + cases
# ════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def md_ids(session):
    """Create a My-Dezider decision once for the module; teardown deletes it."""
    ts = int(time.time())
    r = session.post(
        f"{API}/decisions",
        json={"title": f"TEST_iter62_md_{ts}", "context": "iter62-validation"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    did = r.json()["id"]

    quant_fid = "f-quant-iter62"
    qual_fid = "f-qual-iter62"
    oid = "o-iter62"

    yield {"did": did, "quant_fid": quant_fid, "qual_fid": qual_fid, "oid": oid}

    try:
        session.delete(f"{API}/decisions/{did}", timeout=15)
    except Exception:
        pass


def _md_put_factors(session, did, factors, oid):
    """PUT the decision with the supplied factor list + a single option (no
    solution_id, no data_source) so the Actual-resolution chain has no
    alternative source besides the request body."""
    payload = {
        "factors": factors,
        "options": [{"id": oid, "name": "OptA", "assessments": [], "worth_percentage": 0}],
    }
    r = session.put(f"{API}/decisions/{did}", json=payload, timeout=30)
    assert r.status_code == 200, r.text


def _md_call_assess(session, did, fid, oid, actual=None, timeout=15):
    body = {"option_id": oid}
    if actual is not None:
        body["actual_value"] = actual
    return session.post(
        f"{API}/decisions/{did}/factors/{fid}/ai-assess",
        json=body, timeout=timeout,
    )


class TestMDValidation:
    """My Dezider — POST /api/decisions/{id}/factors/{fid}/ai-assess"""

    # ── Case 1: quantitative, operator MISSING ─────────────────────
    def test_md_case1_missing_operator_400(self, session, md_ids):
        factors = [{
            "id": md_ids["quant_fid"], "name": "Cost", "category": "primary",
            "rating": 8, "order": 0,
            "data_type": "numeric", "expected_value": "1000", "operator": "",
            "unit": "INR", "factor_type": "objective",
        }]
        _md_put_factors(session, md_ids["did"], factors, md_ids["oid"])
        r = _md_call_assess(session, md_ids["did"], md_ids["quant_fid"], md_ids["oid"],
                            actual="1200")
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "operator" in detail, f"detail should mention Operator: {detail!r}"

    # ── Case 2: quantitative, expected_value MISSING ───────────────
    def test_md_case2_missing_expected_400(self, session, md_ids):
        factors = [{
            "id": md_ids["quant_fid"], "name": "Cost", "category": "primary",
            "rating": 8, "order": 0,
            "data_type": "numeric", "expected_value": "", "operator": ">=",
            "unit": "INR", "factor_type": "objective",
        }]
        _md_put_factors(session, md_ids["did"], factors, md_ids["oid"])
        r = _md_call_assess(session, md_ids["did"], md_ids["quant_fid"], md_ids["oid"],
                            actual="1200")
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "expected" in detail, f"detail should mention Expected value: {detail!r}"

    # ── Case 3: quantitative complete, actual missing ──────────────
    def test_md_case3_missing_actual_400(self, session, md_ids):
        factors = [{
            "id": md_ids["quant_fid"], "name": "Cost", "category": "primary",
            "rating": 8, "order": 0,
            "data_type": "numeric", "expected_value": "1000", "operator": ">=",
            "unit": "INR", "factor_type": "objective",
        }]
        _md_put_factors(session, md_ids["did"], factors, md_ids["oid"])
        # NO actual_value in body, option has no solution_id, no data_source set
        r = _md_call_assess(session, md_ids["did"], md_ids["quant_fid"], md_ids["oid"],
                            actual=None)
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "actual" in detail, f"detail should mention Actual value: {detail!r}"

    # ── Case 4: quantitative complete + actual=1200 → 200 ──────────
    def test_md_case4_quant_happy_200(self, session, md_ids):
        factors = [{
            "id": md_ids["quant_fid"], "name": "Cost", "category": "primary",
            "rating": 8, "order": 0,
            "data_type": "numeric", "expected_value": "1000", "operator": ">=",
            "unit": "INR", "factor_type": "objective",
        }]
        _md_put_factors(session, md_ids["did"], factors, md_ids["oid"])
        r = _md_call_assess(session, md_ids["did"], md_ids["quant_fid"], md_ids["oid"],
                            actual="1200", timeout=LLM_TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "percentage" in body, body
        pct = body["percentage"]
        assert isinstance(pct, int) and 0 <= pct <= 100, body

    # ── Case 5: qualitative, expected_value MISSING ────────────────
    def test_md_case5_qual_missing_expected_400(self, session, md_ids):
        factors = [{
            "id": md_ids["qual_fid"], "name": "Team culture", "category": "primary",
            "rating": 7, "order": 0,
            "data_type": "text", "expected_value": "", "operator": "",
            "unit": "", "factor_type": "subjective",
        }]
        _md_put_factors(session, md_ids["did"], factors, md_ids["oid"])
        r = _md_call_assess(session, md_ids["did"], md_ids["qual_fid"], md_ids["oid"],
                            actual=None)
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "expected" in detail, f"detail should mention Expected value: {detail!r}"

    # ── Case 6: qualitative expected only → AI infers actual, 200 ──
    def test_md_case6_qual_inferred_actual_200(self, session, md_ids):
        factors = [{
            "id": md_ids["qual_fid"], "name": "Team culture", "category": "primary",
            "rating": 7, "order": 0,
            "data_type": "text", "expected_value": "Excellent culture",
            "operator": "", "unit": "", "factor_type": "subjective",
        }]
        _md_put_factors(session, md_ids["did"], factors, md_ids["oid"])
        r = _md_call_assess(session, md_ids["did"], md_ids["qual_fid"], md_ids["oid"],
                            actual=None, timeout=LLM_TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "percentage" in body, body
        pct = body["percentage"]
        assert isinstance(pct, int) and 0 <= pct <= 100, body
        assert "actual_value" in body, body
        assert body["actual_value"] not in (None, ""), \
            f"AI should have inferred a non-empty actual_value: {body!r}"


# ════════════════════════════════════════════════════════════════════
# PROS & CONS fixtures + cases
# ════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def pc_ids(session):
    ts = int(time.time())
    r = session.post(
        f"{API}/pros-cons",
        json={"title": f"TEST_iter62_pc_{ts}", "context": "iter62-validation"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    aid = r.json()["id"]

    # add option (no solution_id → forces the actual-resolution chain to body)
    r2 = session.post(f"{API}/pros-cons/{aid}/options", json={"name": "Opt A"}, timeout=30)
    assert r2.status_code == 200, r2.text
    oid = r2.json()["id"]

    # add a quant factor + a qual factor (we'll patch their metadata per-case)
    rq = session.post(f"{API}/pros-cons/{aid}/factors",
                      json={"name": "Cost"}, timeout=30)
    assert rq.status_code == 200, rq.text
    quant_fid = rq.json()["id"]

    rqu = session.post(f"{API}/pros-cons/{aid}/factors",
                       json={"name": "Team culture"}, timeout=30)
    assert rqu.status_code == 200, rqu.text
    qual_fid = rqu.json()["id"]

    yield {"aid": aid, "oid": oid, "quant_fid": quant_fid, "qual_fid": qual_fid}

    try:
        session.delete(f"{API}/pros-cons/{aid}", timeout=15)
    except Exception:
        pass


def _pc_set_meta(session, aid, fid, **meta):
    r = session.put(f"{API}/pros-cons/{aid}/factors/{fid}", json=meta, timeout=30)
    assert r.status_code == 200, r.text


def _pc_call_assess(session, aid, fid, oid, actual=None, timeout=15):
    body = {"option_id": oid}
    if actual is not None:
        body["actual_value"] = actual
    return session.post(
        f"{API}/pros-cons/{aid}/factors/{fid}/ai-assess",
        json=body, timeout=timeout,
    )


class TestPCValidation:
    """Pros & Cons — POST /api/pros-cons/{id}/factors/{fid}/ai-assess"""

    # ── Case 1: quantitative, operator MISSING ─────────────────────
    def test_pc_case1_missing_operator_400(self, session, pc_ids):
        _pc_set_meta(session, pc_ids["aid"], pc_ids["quant_fid"],
                     data_type="numeric", expected_value="1000",
                     operator="", unit="INR")
        r = _pc_call_assess(session, pc_ids["aid"], pc_ids["quant_fid"], pc_ids["oid"],
                            actual="1200")
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "operator" in detail, f"detail should mention Operator: {detail!r}"

    # ── Case 2: quantitative, expected_value MISSING ───────────────
    def test_pc_case2_missing_expected_400(self, session, pc_ids):
        _pc_set_meta(session, pc_ids["aid"], pc_ids["quant_fid"],
                     data_type="numeric", expected_value="",
                     operator=">=", unit="INR")
        r = _pc_call_assess(session, pc_ids["aid"], pc_ids["quant_fid"], pc_ids["oid"],
                            actual="1200")
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "expected" in detail, f"detail should mention Expected value: {detail!r}"

    # ── Case 3: quantitative complete, actual missing ──────────────
    def test_pc_case3_missing_actual_400(self, session, pc_ids):
        _pc_set_meta(session, pc_ids["aid"], pc_ids["quant_fid"],
                     data_type="numeric", expected_value="1000",
                     operator=">=", unit="INR",
                     data_source={"type": "manual"})
        r = _pc_call_assess(session, pc_ids["aid"], pc_ids["quant_fid"], pc_ids["oid"],
                            actual=None)
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "actual" in detail, f"detail should mention Actual value: {detail!r}"

    # ── Case 4: quantitative complete + actual=1200 → 200 ──────────
    def test_pc_case4_quant_happy_200(self, session, pc_ids):
        _pc_set_meta(session, pc_ids["aid"], pc_ids["quant_fid"],
                     data_type="numeric", expected_value="1000",
                     operator=">=", unit="INR")
        r = _pc_call_assess(session, pc_ids["aid"], pc_ids["quant_fid"], pc_ids["oid"],
                            actual="1200", timeout=LLM_TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        # Pros & Cons returns `assessment_pct` (not `percentage`)
        assert "assessment_pct" in body, body
        pct = body["assessment_pct"]
        assert isinstance(pct, int) and 0 <= pct <= 100, body

    # ── Case 5: qualitative, expected_value MISSING ────────────────
    def test_pc_case5_qual_missing_expected_400(self, session, pc_ids):
        _pc_set_meta(session, pc_ids["aid"], pc_ids["qual_fid"],
                     data_type="text", expected_value="",
                     operator="", unit="")
        r = _pc_call_assess(session, pc_ids["aid"], pc_ids["qual_fid"], pc_ids["oid"],
                            actual=None)
        assert r.status_code == 400, r.text
        detail = (r.json().get("detail") or "").lower()
        assert "expected" in detail, f"detail should mention Expected value: {detail!r}"

    # ── Case 6: qualitative expected only → AI infers actual, 200 ──
    def test_pc_case6_qual_inferred_actual_200(self, session, pc_ids):
        _pc_set_meta(session, pc_ids["aid"], pc_ids["qual_fid"],
                     data_type="text",
                     expected_value="Excellent culture",
                     operator="", unit="")
        r = _pc_call_assess(session, pc_ids["aid"], pc_ids["qual_fid"], pc_ids["oid"],
                            actual=None, timeout=LLM_TIMEOUT)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "assessment_pct" in body, body
        pct = body["assessment_pct"]
        assert isinstance(pct, int) and 0 <= pct <= 100, body
        assert body.get("actual_value") not in (None, ""), \
            f"AI should have inferred a non-empty actual_value: {body!r}"
