"""End-to-end test for the AI Assess All (batched) bug-fix verification.

Creates a fresh decision (small: 5 factors x 2 options = 10 cells) and confirms
that POST /api/decisions/{id}/ai-assess-all-batched fills EVERY cell with
status='done', persists assessments, and never silently leaves cells empty.

Run: cd /app/backend && python -m pytest tests/test_ai_assess_all_batched_e2e.py -q
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") \
    or os.environ.get("EXPO_BACKEND_URL") \
    or "https://modal-responsive-fix.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")

EMAIL = "harden_1777921741@example.com"
PASSWORD = "HardenPass2026!"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json().get("session_token") or r.json().get("token")
    assert token, f"No token in login response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def fresh_decision(auth_session):
    payload = {
        "title": "TEST_BatchAssess_Phone",
        "context": "Choosing a smartphone for daily work and travel",
    }
    r = auth_session.post(f"{BASE_URL}/api/decisions", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"Create decision failed: {r.status_code} {r.text}"
    dec = r.json()
    did = dec["id"]

    factors = [
        {"id": "f_battery", "name": "Battery life",
         "factor_type": "quantitative", "data_type": "numeric",
         "expected_value": "5000", "operator": ">=", "unit": "mAh",
         "category": "primary", "rating": 8},
        {"id": "f_camera", "name": "Camera quality",
         "factor_type": "qualitative", "data_type": "text",
         "expected_value": "excellent", "category": "primary", "rating": 7},
        {"id": "f_price", "name": "Price",
         "factor_type": "quantitative", "data_type": "numeric",
         "expected_value": "60000", "operator": "<=", "unit": "INR",
         "category": "primary", "rating": 9},
        {"id": "f_brand", "name": "Brand reputation",
         "factor_type": "qualitative", "data_type": "text",
         "expected_value": "well-trusted", "category": "secondary", "rating": 6},
        {"id": "f_software", "name": "Software updates",
         "factor_type": "qualitative", "data_type": "text",
         "expected_value": "long-term support", "category": "secondary", "rating": 7},
    ]
    options = [
        {"id": "o_iphone", "name": "iPhone 15", "assessments": []},
        {"id": "o_pixel", "name": "Google Pixel 8", "assessments": []},
    ]
    r = auth_session.put(f"{BASE_URL}/api/decisions/{did}",
                          json={"factors": factors, "options": options}, timeout=30)
    assert r.status_code == 200, f"Update decision failed: {r.status_code} {r.text}"

    yield {"id": did, "factors": factors, "options": options}

    # Cleanup
    try:
        auth_session.delete(f"{BASE_URL}/api/decisions/{did}", timeout=20)
    except Exception:
        pass


def test_ai_assess_all_batched_fills_every_cell(auth_session, fresh_decision):
    did = fresh_decision["id"]
    cells = [
        {"option_id": o["id"], "factor_id": f["id"]}
        for o in fresh_decision["options"] for f in fresh_decision["factors"]
    ]
    assert len(cells) == 10

    t0 = time.time()
    r = auth_session.post(
        f"{BASE_URL}/api/decisions/{did}/ai-assess-all-batched",
        json={"cells": cells, "force_fill": True},
        timeout=180,
    )
    elapsed = time.time() - t0
    print(f"\nai-assess-all-batched returned in {elapsed:.1f}s — status {r.status_code}")
    assert r.status_code == 200, f"Endpoint failed: {r.status_code} {r.text[:400]}"
    data = r.json()
    print(f"out_of_credits={data.get('out_of_credits')} ai_unavailable={data.get('ai_unavailable')}")
    if data.get("ai_unavailable"):
        pytest.skip("LLM provider chain unavailable (ai_unavailable=true) — not the bug under test.")
    if data.get("out_of_credits"):
        pytest.skip("Test user out of AI credits — refill required to run this E2E.")

    results = data.get("results", [])
    assert len(results) == len(cells), f"Expected {len(cells)} results, got {len(results)}"
    error_cells = [r for r in results if r.get("status") == "error"]
    skipped_cells = [r for r in results if r.get("status") == "skipped"]
    done_cells = [r for r in results if r.get("status") == "done"]
    print(f"done={len(done_cells)} skipped={len(skipped_cells)} error={len(error_cells)}")
    if error_cells:
        print(f"Error cells sample: {error_cells[:3]}")

    # PRIMARY ASSERTION FOR THE BUG: NO cells should be left as 'error'
    assert not error_cells, f"{len(error_cells)} cells errored (bug regression): {error_cells[:3]}"
    assert not skipped_cells, f"force_fill=true should leave no skipped cells, got {skipped_cells[:3]}"
    assert len(done_cells) == len(cells)

    for r in done_cells:
        pct = r.get("percentage")
        assert isinstance(pct, int) and 0 <= pct <= 100, f"Bad pct: {r}"
        assert r.get("actual_value") not in (None, ""), f"Missing actual: {r}"


def test_assessments_persisted_after_batched_run(auth_session, fresh_decision):
    did = fresh_decision["id"]
    r = auth_session.get(f"{BASE_URL}/api/decisions/{did}", timeout=20)
    assert r.status_code == 200, r.text
    dec = r.json()
    opts = dec.get("options", [])
    assert len(opts) == 2
    factor_ids = {f["id"] for f in fresh_decision["factors"]}
    for o in opts:
        assessments = o.get("assessments") or []
        a_fids = {a.get("factor_id") for a in assessments}
        missing = factor_ids - a_fids
        assert not missing, f"Option {o['name']} missing assessments for {missing}"
        for a in assessments:
            pct = a.get("percentage")
            assert isinstance(pct, int) and 0 <= pct <= 100, f"Bad persisted pct: {a}"
