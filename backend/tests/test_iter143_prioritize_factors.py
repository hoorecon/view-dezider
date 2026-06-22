"""
Iteration 143 — Step 4 "Prioritize with AI" + AI touchpoint toggles regression.

Backend was already curl-verified per main agent; this is a light pytest regression to confirm:
  - GET /api/ai-wallet/estimates exposes `touchpoints` map + features.factor_prioritize (~11).
  - POST /api/ai/prioritize-factors with <2 factors → 422.
  - POST /api/ai/prioritize-factors when touchpoint OFF → 403; back ON → success.
  - Super admin can toggle tp_prioritize_factors via PUT /api/admin/ai-wallet/config.
  - Plain admin gets 403 when writing to /api/admin/ai-wallet/config.
"""

import os
import time
import uuid

import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE:
    # Fallback: read frontend/.env directly
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("EXPO_PUBLIC_BACKEND_URL"):
                BASE = ln.split("=", 1)[1].strip().rstrip("/")

SUPER_EMAIL = "super@test.com"
SUPER_PASS = "SuperPass2026!"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    tok = body.get("session_token") or body.get("access_token") or body.get("token")
    assert tok, f"no token in login response for {email}: {body}"
    return tok, body.get("user") or {}


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def super_token():
    tok, _ = _login(SUPER_EMAIL, SUPER_PASS)
    yield tok
    # Always restore all 4 touchpoints ON at the end.
    requests.put(f"{BASE}/api/admin/ai-wallet/config", headers=_h(tok),
                 json={"tp_best_factors": True, "tp_prioritize_factors": True,
                       "tp_best_options": True, "tp_assess_all": True}, timeout=20)


@pytest.fixture(scope="module")
def admin_token():
    tok, _ = _login(ADMIN_EMAIL, ADMIN_PASS)
    return tok


@pytest.fixture(scope="module")
def user_session():
    """Register a fresh disposable user with seeded credits + 2 factors decision."""
    email = f"iter143_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    pw = "TestPass2026!"
    r = requests.post(f"{BASE}/api/auth/register",
                      json={"email": email, "password": pw, "name": "Iter143 Tester", "full_name": "Iter143 Tester"}, timeout=20)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")
    assert tok
    # Create base decision (factors are added via PUT)
    base = {"title": "TEST_Iter143 prioritize", "context": "Test decision for AI prioritise",
            "life_area": "career", "decision_type": "single_choice"}
    r = requests.post(f"{BASE}/api/decisions", headers=_h(tok), json=base, timeout=20)
    assert r.status_code in (200, 201), f"decision create failed: {r.status_code} {r.text}"
    dec_id = r.json().get("id") or r.json().get("decision_id")
    assert dec_id
    # Patch with 2 top-level factors
    factors = [
        {"id": uuid.uuid4().hex, "name": "Salary", "category": "primary", "order": 1, "rating": 20,
         "factor_type": "quantitative", "priority": 7},
        {"id": uuid.uuid4().hex, "name": "Work-life balance", "category": "primary", "order": 2, "rating": 10,
         "factor_type": "qualitative", "priority": 5},
    ]
    rp = requests.put(f"{BASE}/api/decisions/{dec_id}", headers=_h(tok), json={"factors": factors}, timeout=20)
    assert rp.status_code == 200, f"factor patch failed: {rp.status_code} {rp.text}"
    yield {"token": tok, "decision_id": dec_id, "email": email}
    # cleanup
    try:
        requests.delete(f"{BASE}/api/decisions/{dec_id}", headers=_h(tok), timeout=10)
    except Exception:
        pass


# ── Estimates endpoint ────────────────────────────────────────────────────────
def test_estimates_exposes_touchpoints_and_factor_prioritize(user_session):
    r = requests.get(f"{BASE}/api/ai-wallet/estimates", headers=_h(user_session["token"]), timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "features" in body
    assert "factor_prioritize" in body["features"], f"missing factor_prioritize in {body['features']}"
    # ~11 cr per main agent context
    fp_est = body["features"]["factor_prioritize"]
    assert 5 <= fp_est <= 20, f"factor_prioritize estimate out of range: {fp_est}"
    assert "touchpoints" in body, "estimates must expose touchpoints map"
    tps = body["touchpoints"]
    for k in ("tp_best_factors", "tp_prioritize_factors", "tp_best_options", "tp_assess_all"):
        assert k in tps, f"missing touchpoint {k}"
        assert isinstance(tps[k], bool)


# ── Super admin can write touchpoint; plain admin gets 403 ────────────────────
def test_plain_admin_cannot_write_ai_wallet_config(admin_token):
    r = requests.put(f"{BASE}/api/admin/ai-wallet/config", headers=_h(admin_token),
                     json={"tp_prioritize_factors": True}, timeout=15)
    assert r.status_code == 403, f"plain admin should be 403, got {r.status_code} {r.text}"


def test_super_admin_can_toggle_touchpoint(super_token):
    # Turn OFF
    r = requests.put(f"{BASE}/api/admin/ai-wallet/config", headers=_h(super_token),
                     json={"tp_prioritize_factors": False}, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json().get("tp_prioritize_factors") is False
    # Verify via GET estimates
    r2 = requests.get(f"{BASE}/api/ai-wallet/estimates", timeout=15,
                      headers={"Authorization": f"Bearer {super_token}"})
    assert r2.status_code == 200
    assert r2.json()["touchpoints"]["tp_prioritize_factors"] is False
    # Turn back ON
    r = requests.put(f"{BASE}/api/admin/ai-wallet/config", headers=_h(super_token),
                     json={"tp_prioritize_factors": True}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("tp_prioritize_factors") is True


# ── Prioritize-factors gating ────────────────────────────────────────────────
def test_prioritize_factors_422_when_too_few(user_session):
    # Create a single-factor decision and verify 422
    payload = {"title": "TEST_Iter143 single", "context": "x",
               "life_area": "career", "decision_type": "single_choice"}
    r = requests.post(f"{BASE}/api/decisions", headers=_h(user_session["token"]), json=payload, timeout=15)
    assert r.status_code in (200, 201)
    sid = r.json().get("id") or r.json().get("decision_id")
    # Patch a single factor
    factors = [{"id": uuid.uuid4().hex, "name": "Solo", "category": "primary",
                "order": 1, "factor_type": "qualitative", "priority": 5}]
    requests.put(f"{BASE}/api/decisions/{sid}", headers=_h(user_session["token"]),
                 json={"factors": factors}, timeout=15)
    try:
        r2 = requests.post(f"{BASE}/api/ai/prioritize-factors", headers=_h(user_session["token"]),
                           json={"decision_id": sid}, timeout=30)
        assert r2.status_code == 422, f"expected 422 got {r2.status_code} {r2.text}"
    finally:
        requests.delete(f"{BASE}/api/decisions/{sid}", headers=_h(user_session["token"]), timeout=10)


def test_prioritize_factors_403_when_disabled(super_token, user_session):
    # Disable
    r = requests.put(f"{BASE}/api/admin/ai-wallet/config", headers=_h(super_token),
                     json={"tp_prioritize_factors": False}, timeout=15)
    assert r.status_code == 200
    try:
        r2 = requests.post(f"{BASE}/api/ai/prioritize-factors", headers=_h(user_session["token"]),
                           json={"decision_id": user_session["decision_id"]}, timeout=30)
        assert r2.status_code == 403, f"expected 403 got {r2.status_code} {r2.text}"
    finally:
        # restore
        requests.put(f"{BASE}/api/admin/ai-wallet/config", headers=_h(super_token),
                     json={"tp_prioritize_factors": True}, timeout=15)


def test_prioritize_factors_success_returns_ranked(user_session):
    r = requests.post(f"{BASE}/api/ai/prioritize-factors", headers=_h(user_session["token"]),
                      json={"decision_id": user_session["decision_id"]}, timeout=60)
    assert r.status_code == 200, f"expected 200 got {r.status_code} {r.text}"
    body = r.json()
    assert "factors" in body
    assert len(body["factors"]) >= 2
    ranks = sorted(int(f["rank"]) for f in body["factors"])
    assert ranks == list(range(1, len(ranks) + 1)), f"ranks not 1..N: {ranks}"
    for f in body["factors"]:
        assert "id" in f and "name" in f and "rank" in f
    # provider + credits keys present (may be None on free tier)
    assert "provider" in body
    assert "credits" in body
