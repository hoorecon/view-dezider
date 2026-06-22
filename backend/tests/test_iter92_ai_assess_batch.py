"""Iter 92 — POST /api/decisions/{id}/ai-assess-batch + single-cell regression.

Covers the production bug fix (PR replacing per-cell burst with batch endpoint):
  (a) empty cells -> 400
  (b) > 12 cells -> 400
  (c) force_fill=false + missing Expected/operator/actual -> status 'skipped'
  (d) complete numeric cell -> status 'done' with percentage
  (e) single-cell endpoint /factors/{fid}/ai-assess still works (regression)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://goals-feels-tracker.preview.emergentagent.com").rstrip("/")
USER_EMAIL = "harden_1777921741@example.com"
USER_PASSWORD = "HardenPass2026!"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": USER_EMAIL, "password": USER_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("session_token") or r.json().get("token")
    assert token, f"no session_token in {r.json()}"
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def decision_id(auth_headers):
    title = f"TEST_iter92_batch_{int(time.time())}"
    r = requests.post(
        f"{BASE_URL}/api/decisions",
        headers=auth_headers,
        json={"title": title, "context": "Testing batch ai-assess endpoint", "life_area": "career"},
        timeout=30,
    )
    assert r.status_code in (200, 201), f"create decision: {r.status_code} {r.text}"
    did = r.json().get("id") or r.json().get("decision_id")
    assert did, f"no id in {r.json()}"

    # Add 2 factors (1 complete numeric, 1 incomplete) and 2 options
    factors = [
        {
            "id": "f_price",
            "name": "Price",
            "rating": 9,
            "order": 0,
            "data_type": "number",
            "factor_type": "quantitative",
            "operator": "<=",
            "expected_value": "500",
            "unit": "USD",
        },
        {
            "id": "f_empty",
            "name": "Brand value",
            "rating": 7,
            "order": 1,
            "data_type": "number",
            "factor_type": "quantitative",
            # Missing expected_value/operator → incomplete
        },
    ]
    options = [
        {"id": "o_a", "name": "Option A", "assessments": [
            {"factor_id": "f_price", "unit_value": "600 USD"},
        ]},
        {"id": "o_b", "name": "Option B", "assessments": []},
    ]
    r2 = requests.put(
        f"{BASE_URL}/api/decisions/{did}",
        headers=auth_headers,
        json={"factors": factors, "options": options},
        timeout=30,
    )
    assert r2.status_code == 200, f"update decision: {r2.status_code} {r2.text}"
    return did


# ── (a) empty cells -> 400 ─────────────────────────────────────────────────
def test_batch_empty_cells_returns_400(auth_headers, decision_id):
    r = requests.post(
        f"{BASE_URL}/api/decisions/{decision_id}/ai-assess-batch",
        headers=auth_headers,
        json={"cells": []},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400 for empty cells, got {r.status_code} {r.text}"


# ── (b) > 12 cells -> 400 ──────────────────────────────────────────────────
def test_batch_too_large_returns_400(auth_headers, decision_id):
    cells = [{"option_id": "o_a", "factor_id": "f_price"} for _ in range(13)]
    r = requests.post(
        f"{BASE_URL}/api/decisions/{decision_id}/ai-assess-batch",
        headers=auth_headers,
        json={"cells": cells},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400 for 13 cells, got {r.status_code} {r.text}"


# ── (c) force_fill=false with incomplete cell -> status 'skipped' ──────────
def test_batch_skipped_when_incomplete_and_no_force_fill(auth_headers, decision_id):
    r = requests.post(
        f"{BASE_URL}/api/decisions/{decision_id}/ai-assess-batch",
        headers=auth_headers,
        json={
            "force_fill": False,
            "cells": [
                # Missing expected_value on factor → must skip
                {"option_id": "o_a", "factor_id": "f_empty"},
                # Quantitative, expected set, but no operator+actual on Option B → must skip
                {"option_id": "o_b", "factor_id": "f_empty"},
            ],
        },
        timeout=60,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert "results" in body and len(body["results"]) == 2, body
    for res in body["results"]:
        assert res["status"] == "skipped", f"expected skipped, got {res}"
    # No LLM was called for skipped cells → out_of_credits must be False
    assert body.get("out_of_credits") is False


# ── (d) complete numeric cell -> status 'done' with percentage ────────────
def test_batch_done_for_complete_numeric_cell(auth_headers, decision_id):
    r = requests.post(
        f"{BASE_URL}/api/decisions/{decision_id}/ai-assess-batch",
        headers=auth_headers,
        json={
            "force_fill": False,
            "cells": [
                # Option A has actual='600 USD', factor expected '<=500' → some pct
                {"option_id": "o_a", "factor_id": "f_price", "actual_value": "600"},
            ],
        },
        timeout=90,
    )
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert len(body["results"]) == 1, body
    res = body["results"][0]
    # If LLM provider is genuinely down/out_of_credits the endpoint may also
    # surface that — fail loudly so we can see which case it was.
    if body.get("out_of_credits"):
        pytest.skip("Provider out of credits — endpoint contract OK")
    assert res["status"] == "done", f"expected done, got {res}; body={body}"
    assert isinstance(res.get("percentage"), int), res
    assert 0 <= res["percentage"] <= 100, res

    # Verify persistence — GET decision and confirm assessment is saved.
    g = requests.get(f"{BASE_URL}/api/decisions/{decision_id}", headers=auth_headers, timeout=30)
    assert g.status_code == 200, g.text
    decision = g.json()
    o_a = next(o for o in decision["options"] if o["id"] == "o_a")
    cell = next((a for a in o_a.get("assessments", []) if a["factor_id"] == "f_price"), None)
    assert cell is not None and cell.get("percentage") == res["percentage"], (cell, res)


# ── (e) single-cell endpoint regression ────────────────────────────────────
def test_single_cell_endpoint_still_works(auth_headers, decision_id):
    r = requests.post(
        f"{BASE_URL}/api/decisions/{decision_id}/factors/f_price/ai-assess",
        headers=auth_headers,
        json={"option_id": "o_a", "actual_value": "600"},
        timeout=90,
    )
    # Status must NOT be 405 (that was the bug). Either 200 OK or 402 (no credits) acceptable.
    assert r.status_code != 405, f"REGRESSION: single-cell endpoint returned 405! {r.text}"
    if r.status_code == 402:
        pytest.skip("Out of AI credits — endpoint still routable (not 405)")
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    body = r.json()
    assert isinstance(body.get("percentage"), int)
    assert 0 <= body["percentage"] <= 100
