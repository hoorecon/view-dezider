"""Tests for the new POST /api/ai/find-best-options endpoint (iteration 30).

Covers:
 - Success path (decision with factors) → 200 with options + used_model + store_match_count
 - Graceful fallback when decision has NO factors (life_area only) → 200 with options
 - Auth required: missing Bearer → 401/403
 - Invalid decision_id for the user → 404
 - Response contract: each option has name/source/ai_rationale; <=5; dedupe vs existing options
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://dashboard-rewire.preview.emergentagent.com").rstrip("/")

USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": USER_EMAIL, "password": USER_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("session_token") or data.get("token") or data.get("access_token")
    assert tok, f"no token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _create_decision(auth_headers, *, with_factors: bool):
    payload = {
        "title": "TEST_FindBestOptions Buying a laptop",
        "context": "Need a laptop for software dev, travel-friendly, 16GB RAM, good battery.",
        "life_area": "knowledge_skills",
        "decision_type": "product_purchase",
    }
    r = requests.post(f"{BASE_URL}/api/decisions", json=payload, headers=auth_headers, timeout=30)
    assert r.status_code in (200, 201), f"create decision: {r.status_code} {r.text[:200]}"
    dec = r.json()
    dec_id = dec.get("id") or dec.get("decision_id")
    assert dec_id

    if with_factors:
        factors = [
            {"id": "f1", "name": "Battery life", "category": "primary", "rating": 90, "order": 0, "unit": "hours", "expected_value": 10, "operator": ">="},
            {"id": "f2", "name": "RAM", "category": "primary", "rating": 80, "order": 1, "unit": "GB", "expected_value": 16, "operator": ">="},
            {"id": "f3", "name": "Price", "category": "primary", "rating": 70, "order": 2, "unit": "USD", "expected_value": 1500, "operator": "<="},
            {"id": "f4", "name": "Weight", "category": "secondary", "rating": 50, "order": 3, "unit": "kg", "expected_value": 1.5, "operator": "<="},
        ]
        upd = requests.put(f"{BASE_URL}/api/decisions/{dec_id}", json={"factors": factors},
                            headers=auth_headers, timeout=30)
        assert upd.status_code in (200, 204), f"update factors: {upd.status_code} {upd.text[:200]}"
    return dec_id


@pytest.fixture(scope="module")
def decision_with_factors(auth):
    return _create_decision(auth, with_factors=True)


@pytest.fixture(scope="module")
def decision_no_factors(auth):
    return _create_decision(auth, with_factors=False)


# ── 1. Auth required ─────────────────────────────────────────────
def test_requires_auth():
    r = requests.post(f"{BASE_URL}/api/ai/find-best-options",
                      json={"decision_id": "anything"}, timeout=15)
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text[:200]}"


# ── 2. Invalid decision id → 404 ─────────────────────────────────
def test_invalid_decision_id(auth):
    r = requests.post(f"{BASE_URL}/api/ai/find-best-options",
                      json={"decision_id": "decision-does-not-exist-xyz"}, headers=auth, timeout=60)
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text[:200]}"


# ── 3. Happy path: with factors ──────────────────────────────────
def test_find_best_options_with_factors(auth, decision_with_factors):
    r = requests.post(f"{BASE_URL}/api/ai/find-best-options",
                      json={"decision_id": decision_with_factors, "limit": 5},
                      headers=auth, timeout=120)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    body = r.json()
    assert "options" in body
    assert "used_model" in body
    assert "store_match_count" in body
    assert isinstance(body["options"], list)
    assert len(body["options"]) <= 5, f"options must be ≤5, got {len(body['options'])}"
    # Must return at least 1 option (AI or store)
    assert len(body["options"]) >= 1, f"expected ≥1 options, got 0. Body: {body}"

    seen = set()
    for opt in body["options"]:
        assert "name" in opt and opt["name"].strip(), f"option missing name: {opt}"
        assert "source" in opt and opt["source"] in ("ai", "store"), f"bad source: {opt}"
        assert "ai_rationale" in opt, f"option missing ai_rationale: {opt}"
        # No duplicates
        key = opt["name"].lower()
        assert key not in seen, f"duplicate option name: {opt['name']}"
        seen.add(key)
        # Store-sourced items must have solution_id
        if opt["source"] == "store":
            assert opt.get("solution_id"), f"store-source missing solution_id: {opt}"

    # used_model should be one of the two configured
    assert body["used_model"] in ("claude-sonnet-4-5-20250929", "gpt-4.1-mini"), \
        f"unexpected used_model: {body['used_model']}"


# ── 4. Graceful fallback: no factors ─────────────────────────────
def test_find_best_options_no_factors(auth, decision_no_factors):
    r = requests.post(f"{BASE_URL}/api/ai/find-best-options",
                      json={"decision_id": decision_no_factors},
                      headers=auth, timeout=120)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    body = r.json()
    assert isinstance(body.get("options"), list)
    # AI-only is acceptable. We just require structure.
    for opt in body["options"]:
        assert "name" in opt and opt["name"].strip()
        assert opt.get("source") in ("ai", "store")
        assert "ai_rationale" in opt
    assert len(body["options"]) <= 5


# ── 5. Dedupe vs existing options ────────────────────────────────
def test_dedupes_against_existing_options(auth, decision_with_factors):
    # First add a pre-existing option to the decision named "MacBook Pro 16"
    dec_get = requests.get(f"{BASE_URL}/api/decisions/{decision_with_factors}", headers=auth, timeout=30)
    assert dec_get.status_code == 200
    existing_opts = dec_get.json().get("options", []) or []
    pre = list(existing_opts) + [{
        "id": "preopt-1",
        "name": "MacBook Pro 16",
        "assessments": [],
        "worth_percentage": 0,
    }]
    upd = requests.put(f"{BASE_URL}/api/decisions/{decision_with_factors}",
                        json={"options": pre}, headers=auth, timeout=30)
    assert upd.status_code in (200, 204), f"update options failed: {upd.status_code} {upd.text[:200]}"

    r = requests.post(f"{BASE_URL}/api/ai/find-best-options",
                      json={"decision_id": decision_with_factors, "limit": 5},
                      headers=auth, timeout=120)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    body = r.json()
    names = [o["name"].lower() for o in body["options"]]
    assert "macbook pro 16" not in names, f"endpoint should dedupe against existing options. Got: {names}"
